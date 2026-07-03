"""
Server-rendered views for the News Application.

Groups:
* Authentication  - register, login, logout
* Dashboard       - role-specific landing page
* Articles        - list, detail, create, edit, delete, pending, approve
* Newsletters     - list, detail, create, edit, delete
* Publishers      - list, detail, create, edit, delete (editor only)
"""

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ArticleForm, CustomUserCreationForm, NewsletterForm, PublisherForm
from .models import Article, CustomUser, Newsletter, Publisher


# ---------------------------------------------------------------------------
# Role-check helpers
# ---------------------------------------------------------------------------

def is_editor(user):
    """Return True if the user is authenticated and has the Editor role."""
    return user.is_authenticated and user.role == "editor"


def is_journalist(user):
    """Return True if the user is authenticated and has the Journalist role."""
    return user.is_authenticated and user.role == "journalist"


def is_editor_or_journalist(user):
    """Return True if the user is authenticated and has the Editor or Journalist role."""
    return user.is_authenticated and user.role in ("editor", "journalist")


def is_reader(user):
    """Return True if the user is authenticated and has the Reader role."""
    return user.is_authenticated and user.role == "reader"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def register(request):
    """
    Display and process the user registration form.

    On a valid POST the user is created, logged in and redirected to the
    dashboard. Invalid submissions re-render the form with inline errors.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Welcome! Your account has been created.")
            return redirect("dashboard")
    else:
        form = CustomUserCreationForm()
    return render(request, "news/register.html", {"form": form})


def login_view(request):
    """
    Display and process the login form.

    Authenticated users are redirected straight to the dashboard.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect("dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "news/login.html", {"form": form})


@login_required
def logout_view(request):
    """Log the current user out and redirect to the login page."""
    auth_logout(request)
    return redirect("login")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """
    Role-specific landing page shown after login.

    Editors see pending article count and publisher count.
    Journalists see their article and newsletter counts.
    Readers see navigation cards.
    """
    context = {}
    if request.user.role == "editor":
        context["pending_count"] = Article.objects.filter(approved=False).count()
        context["publisher_count"] = Publisher.objects.count()
    elif request.user.role == "journalist":
        context["my_article_count"] = request.user.published_articles.count()
        context["my_newsletter_count"] = request.user.published_newsletters.count()
    return render(request, "news/dashboard.html", context)


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

@login_required
def article_list(request):
    """
    Display articles visible to the current user.

    Readers see only approved articles. Editors and Journalists see all.
    """
    if request.user.role == "reader":
        articles = Article.objects.filter(approved=True)
    else:
        articles = Article.objects.all()
    return render(request, "news/article_list.html", {"articles": articles})


@login_required
def article_detail(request, pk):
    """
    Display a single article.

    Readers are redirected if the article has not been approved yet.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.user.role == "reader" and not article.approved:
        messages.error(request, "This article has not been approved yet.")
        return redirect("article-list")
    return render(request, "news/article_detail.html", {"article": article})


@login_required
@user_passes_test(is_journalist, login_url="dashboard")
def article_create(request):
    """
    Allow a journalist to submit a new article for editorial review.

    The author is set to the current user in the view, not from the form.
    """
    if request.method == "POST":
        form = ArticleForm(request.POST)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            messages.success(request, "Article submitted for editorial review.")
            return redirect("article-detail", pk=article.pk)
    else:
        form = ArticleForm()
    return render(request, "news/article_form.html", {"form": form, "mode": "create"})


@login_required
@user_passes_test(is_editor_or_journalist, login_url="dashboard")
def article_edit(request, pk):
    """
    Allow an editor or the article's author to edit an article.

    A journalist who did not author the article is redirected with an error.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.user.role == "journalist" and article.author_id != request.user.id:
        messages.error(request, "You can only edit your own articles.")
        return redirect("article-list")
    if request.method == "POST":
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, "Article updated.")
            return redirect("article-detail", pk=article.pk)
    else:
        form = ArticleForm(instance=article)
    return render(
        request,
        "news/article_form.html",
        {"form": form, "mode": "edit", "article": article},
    )


@login_required
@user_passes_test(is_editor_or_journalist, login_url="dashboard")
def article_delete(request, pk):
    """
    Allow an editor or the article's author to delete an article.

    GET shows a confirmation page. POST performs the deletion.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.user.role == "journalist" and article.author_id != request.user.id:
        messages.error(request, "You can only delete your own articles.")
        return redirect("article-list")
    if request.method == "POST":
        article.delete()
        messages.success(request, "Article deleted.")
        return redirect("article-list")
    return render(request, "news/article_confirm_delete.html", {"article": article})


# ---------------------------------------------------------------------------
# Editor review / approval
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_editor, login_url="dashboard")
def pending_articles(request):
    """Display all unapproved articles for the editor to review."""
    articles = Article.objects.filter(approved=False)
    return render(request, "news/pending_articles.html", {"articles": articles})


@login_required
@user_passes_test(is_editor, login_url="dashboard")
def approve_article(request, pk):
    """
    Allow an editor to approve a pending article.

    GET shows a confirmation page. POST saves the approval, which triggers
    the Django signal that emails subscribers and POSTs to /api/approved/.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.method == "POST":
        article.approved = True
        article.approved_at = timezone.now()
        article.approved_by = request.user
        article.save()
        messages.success(request, f'"{article.title}" has been approved and published.')
        return redirect("pending-articles")
    return render(request, "news/article_approve_confirm.html", {"article": article})


# ---------------------------------------------------------------------------
# Newsletters
# ---------------------------------------------------------------------------

@login_required
def newsletter_list(request):
    """Display all newsletters. Accessible to every authenticated user."""
    newsletters = Newsletter.objects.all()
    return render(request, "news/newsletter_list.html", {"newsletters": newsletters})


@login_required
def newsletter_detail(request, pk):
    """Display a single newsletter and its articles."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(request, "news/newsletter_detail.html", {"newsletter": newsletter})


@login_required
@user_passes_test(is_editor_or_journalist, login_url="dashboard")
def newsletter_create(request):
    """Allow a journalist or editor to create a newsletter."""
    if request.method == "POST":
        form = NewsletterForm(request.POST, author=request.user)
        if form.is_valid():
            newsletter = form.save(commit=False)
            newsletter.author = request.user
            newsletter.save()
            form.save_m2m()
            messages.success(request, "Newsletter created.")
            return redirect("newsletter-detail", pk=newsletter.pk)
    else:
        form = NewsletterForm(author=request.user)
    return render(request, "news/newsletter_form.html", {"form": form, "mode": "create"})


@login_required
@user_passes_test(is_editor_or_journalist, login_url="dashboard")
def newsletter_edit(request, pk):
    """Allow an editor or the newsletter's author to edit it."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if request.user.role == "journalist" and newsletter.author_id != request.user.id:
        messages.error(request, "You can only edit your own newsletters.")
        return redirect("newsletter-list")
    if request.method == "POST":
        form = NewsletterForm(request.POST, instance=newsletter, author=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Newsletter updated.")
            return redirect("newsletter-detail", pk=newsletter.pk)
    else:
        form = NewsletterForm(instance=newsletter, author=request.user)
    return render(
        request,
        "news/newsletter_form.html",
        {"form": form, "mode": "edit", "newsletter": newsletter},
    )


@login_required
@user_passes_test(is_editor_or_journalist, login_url="dashboard")
def newsletter_delete(request, pk):
    """Allow an editor or the newsletter's author to delete it."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if request.user.role == "journalist" and newsletter.author_id != request.user.id:
        messages.error(request, "You can only delete your own newsletters.")
        return redirect("newsletter-list")
    if request.method == "POST":
        newsletter.delete()
        messages.success(request, "Newsletter deleted.")
        return redirect("newsletter-list")
    return render(
        request,
        "news/newsletter_confirm_delete.html",
        {"newsletter": newsletter},
    )


# ---------------------------------------------------------------------------
# Publishers (editor only for create / edit / delete)
# ---------------------------------------------------------------------------

@login_required
def publisher_list(request):
    """
    Display all publishers.

    All authenticated users can view publishers. Only editors see
    the Create and Edit buttons in the template.
    """
    publishers = Publisher.objects.prefetch_related("editors", "journalists")
    return render(request, "news/publisher_list.html", {"publishers": publishers})


@login_required
def publisher_detail(request, pk):
    """
    Display a single publisher with its affiliated editors, journalists and articles.

    Readers must not see any information about pending (unapproved) articles,
    including the title, so the article list is filtered to approved articles
    only before it ever reaches the template. Editors and Journalists still
    see every article, including pending ones, so they can review/manage them.
    """
    publisher = get_object_or_404(
        Publisher.objects.prefetch_related("editors", "journalists"), pk=pk
    )
    if request.user.role == "reader":
        articles = publisher.articles.filter(approved=True)
    else:
        articles = publisher.articles.all()

    is_subscribed = False
    if request.user.role == "reader":
        is_subscribed = publisher.reader_subscribers.filter(pk=request.user.pk).exists()

    return render(request, "news/publisher_detail.html", {
        "publisher": publisher,
        "articles": articles,
        "is_subscribed": is_subscribed,
    })


@login_required
@user_passes_test(is_reader, login_url="dashboard")
def toggle_publisher_subscription(request, pk):
    """
    Allow a Reader to subscribe to or unsubscribe from a Publisher.

    Subscribing means the Reader will receive an email once an article from
    this publisher is approved (handled by the post_save signal on Article).
    POST only; redirects back to the publisher detail page either way.
    """
    publisher = get_object_or_404(Publisher, pk=pk)
    if request.method == "POST":
        if publisher.reader_subscribers.filter(pk=request.user.pk).exists():
            request.user.subscriptions_publishers.remove(publisher)
            messages.success(request, f'Unsubscribed from "{publisher.name}".')
        else:
            request.user.subscriptions_publishers.add(publisher)
            messages.success(request, f'Subscribed to "{publisher.name}". You will be emailed when they publish an approved article.')
    return redirect("publisher-detail", pk=publisher.pk)


# ---------------------------------------------------------------------------
# Journalists (browse + subscribe, Reader-facing)
# ---------------------------------------------------------------------------

@login_required
def journalist_list(request):
    """
    Display all journalists so Readers can find and subscribe to them.

    For Readers, each journalist is annotated with whether the current user
    is already subscribed, so the template can render the correct
    Subscribe/Unsubscribe button state.
    """
    journalists = CustomUser.objects.filter(role=CustomUser.JOURNALIST).order_by("username")
    subscribed_ids = set()
    if request.user.role == "reader":
        subscribed_ids = set(
            request.user.subscriptions_journalists.values_list("id", flat=True)
        )
    return render(request, "news/journalist_list.html", {
        "journalists": journalists,
        "subscribed_ids": subscribed_ids,
    })


@login_required
@user_passes_test(is_reader, login_url="dashboard")
def toggle_journalist_subscription(request, pk):
    """
    Allow a Reader to subscribe to or unsubscribe from a Journalist.

    Subscribing means the Reader will receive an email once an article by
    this journalist is approved (handled by the post_save signal on Article).
    POST only; redirects back to the journalist list either way.
    """
    journalist = get_object_or_404(CustomUser, pk=pk, role=CustomUser.JOURNALIST)
    if request.method == "POST":
        if request.user.subscriptions_journalists.filter(pk=journalist.pk).exists():
            request.user.subscriptions_journalists.remove(journalist)
            messages.success(request, f"Unsubscribed from {journalist.username}.")
        else:
            request.user.subscriptions_journalists.add(journalist)
            messages.success(request, f"Subscribed to {journalist.username}. You will be emailed when they publish an approved article.")
    return redirect("journalist-list")


@login_required
@user_passes_test(is_editor, login_url="dashboard")
def publisher_create(request):
    """
    Allow an editor to create a new publisher and assign staff.

    Passes counts of available editors and journalists to the template
    so a helpful warning can be shown if no users of those roles exist yet.
    """
    available_editors = CustomUser.objects.filter(role=CustomUser.EDITOR)
    available_journalists = CustomUser.objects.filter(role=CustomUser.JOURNALIST)

    if request.method == "POST":
        form = PublisherForm(request.POST)
        if form.is_valid():
            publisher = form.save()
            messages.success(request, f'Publisher "{publisher.name}" created.')
            return redirect("publisher-detail", pk=publisher.pk)
    else:
        form = PublisherForm()

    return render(request, "news/publisher_form.html", {
        "form": form,
        "mode": "create",
        "available_editors": available_editors,
        "available_journalists": available_journalists,
    })


@login_required
@user_passes_test(is_editor, login_url="dashboard")
def publisher_edit(request, pk):
    """
    Allow an editor to update a publisher's details and staff.

    Passes counts of available editors and journalists to the template
    so a helpful warning can be shown if no users of those roles exist yet.
    """
    publisher = get_object_or_404(Publisher, pk=pk)
    available_editors = CustomUser.objects.filter(role=CustomUser.EDITOR)
    available_journalists = CustomUser.objects.filter(role=CustomUser.JOURNALIST)

    if request.method == "POST":
        form = PublisherForm(request.POST, instance=publisher)
        if form.is_valid():
            form.save()
            messages.success(request, f'Publisher "{publisher.name}" updated.')
            return redirect("publisher-detail", pk=publisher.pk)
    else:
        form = PublisherForm(instance=publisher)

    return render(request, "news/publisher_form.html", {
        "form": form,
        "mode": "edit",
        "publisher": publisher,
        "available_editors": available_editors,
        "available_journalists": available_journalists,
    })


@login_required
@user_passes_test(is_editor, login_url="dashboard")
def publisher_delete(request, pk):
    """
    Allow an editor to delete a publisher.

    Articles linked to this publisher will have their publisher set to NULL.
    GET shows a confirmation page. POST performs the deletion.
    """
    publisher = get_object_or_404(Publisher, pk=pk)
    if request.method == "POST":
        name = publisher.name
        publisher.delete()
        messages.success(request, f'Publisher "{name}" has been deleted.')
        return redirect("publisher-list")
    return render(
        request,
        "news/publisher_confirm_delete.html",
        {"publisher": publisher},
    )
