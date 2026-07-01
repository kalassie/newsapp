"""
Article-approval side effects, implemented with Django signals (Option 1).

When an Article's ``approved`` field transitions from False to True, two
things happen automatically:

1. **Subscriber email** – every Reader who is subscribed to either the
   article's journalist (``subscriptions_journalists``) or its publisher
   (``subscriptions_publishers``) receives a notification email containing
   the article title and full content.

2. **Internal API POST** – the approved article is POSTed (via Python's
   ``requests`` module) to this project's own ``/api/approved/`` endpoint,
   simulating the act of sharing the article with an external system while
   keeping the integration fully self-contained.

Signal pair
-----------
``pre_save``  – stashes the current value of ``approved`` on the instance
                before the row is written, so the post_save handler can
                compare old vs new.
``post_save`` – compares the stashed value to the new ``approved`` field
                and fires the side effects only on the False → True
                transition, preventing duplicate emails/POSTs on subsequent
                saves of an already-approved article.

Both email sending and the HTTP POST are wrapped in try/except blocks and
logged on failure. This ensures that a broken mail server or an unreachable
API endpoint never blocks the editor's approval action.
"""

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Article

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Article)
def stash_previous_approval_state(sender, instance, **kwargs):
    """
    Record the article's approval state before the current save.

    Reads the ``approved`` value from the database (or defaults to False for
    brand-new instances) and stores it on the instance as
    ``_previous_approved``. The ``post_save`` handler reads this attribute to
    determine whether this save represents a fresh approval event.

    Parameters
    ----------
    sender : type
        The model class (Article).
    instance : Article
        The Article instance about to be saved.
    **kwargs
        Additional keyword arguments passed by Django's signal machinery.
    """
    if instance.pk:
        try:
            instance._previous_approved = Article.objects.get(pk=instance.pk).approved
        except Article.DoesNotExist:
            instance._previous_approved = False
    else:
        instance._previous_approved = False


@receiver(post_save, sender=Article)
def handle_article_approval(sender, instance, created, **kwargs):
    """
    Fire approval side effects on the False → True transition of ``approved``.

    Reads the ``_previous_approved`` attribute set by ``stash_previous_approval_state``
    and calls the email and API helpers only when the article has just been
    approved for the first time. Re-saving an already-approved article has no
    effect on subscribers or the API log.

    Parameters
    ----------
    sender : type
        The model class (Article).
    instance : Article
        The Article instance that was just saved.
    created : bool
        True if this was an INSERT (new row), False if an UPDATE.
    **kwargs
        Additional keyword arguments passed by Django's signal machinery.
    """
    was_approved_before = getattr(instance, "_previous_approved", False)
    if instance.approved and not was_approved_before:
        email_subscribers_about_article(instance)
        post_article_to_approved_api(instance)


def get_subscribers_for_article(article):
    """
    Return a queryset of Reader users who should be notified about this article.

    A reader qualifies if they are subscribed to the article's journalist
    author OR (when the article has a publisher) to that publisher. The
    ``distinct()`` call prevents duplicate rows when a reader happens to
    subscribe to both.

    Parameters
    ----------
    article : Article
        The newly-approved article whose subscribers are needed.

    Returns
    -------
    QuerySet[CustomUser]
        All Reader-role users subscribed to this article's author or publisher.
    """
    User = article.author.__class__
    filters = Q(subscriptions_journalists=article.author)
    if article.publisher_id:
        filters |= Q(subscriptions_publishers=article.publisher)
    return User.objects.filter(filters, role=User.READER).distinct()


def email_subscribers_about_article(article):
    """
    Send a notification email to every subscriber of the approved article.

    Collects the email addresses of all qualifying readers (see
    ``get_subscribers_for_article``), skips any without a stored email address,
    and sends a single ``send_mail`` call per approval event. Failures are
    caught and logged so a broken mail server never surfaces as an HTTP 500
    for the approving editor.

    Parameters
    ----------
    article : Article
        The newly-approved article to notify subscribers about.
    """
    subscribers = get_subscribers_for_article(article)
    recipients = [user.email for user in subscribers if user.email]
    if not recipients:
        return
    try:
        send_mail(
            subject=f"New article published: {article.title}",
            message=(
                f"{article.title}\n\n"
                f"By {article.author.get_full_name() or article.author.username}\n\n"
                f"{article.content}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to email subscribers for article id=%s", article.pk
        )


def post_article_to_approved_api(article):
    """
    POST the approved article payload to the internal ``/api/approved/`` endpoint.

    Uses Python's ``requests`` module to simulate sharing the article with an
    external system. The target URL is read from ``settings.APPROVED_ARTICLE_API_URL``
    so it can be overridden per environment without changing code. Failures are
    caught and logged.

    Parameters
    ----------
    article : Article
        The newly-approved article whose metadata will be posted.
    """
    payload = {
        "id": article.id,
        "title": article.title,
        "author": article.author.username,
        "publisher": article.publisher.name if article.publisher else None,
        "approved_at": (
            article.approved_at.isoformat() if article.approved_at else None
        ),
    }
    try:
        requests.post(settings.APPROVED_ARTICLE_API_URL, json=payload, timeout=5)
    except requests.RequestException:
        logger.exception(
            "Failed to POST approved article id=%s to internal API", article.pk
        )
