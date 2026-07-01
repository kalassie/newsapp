"""
Forms for the News Application.

Covers user registration, article creation/editing, newsletter
creation/editing, and publisher management (editor-only).
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Article, CustomUser, Newsletter, Publisher


class CustomUserCreationForm(UserCreationForm):
    """
    Registration form extending Django's UserCreationForm.

    Adds a required unique email field and a role selector.
    The clean_email method blocks duplicate email addresses with a
    clear inline error message before the database is reached.
    """

    email = forms.EmailField(
        required=True,
        help_text="Required. Must be unique. Subscription emails are sent here.",
    )
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        required=True,
        help_text="Choose your role on the platform.",
    )

    class Meta(UserCreationForm.Meta):
        """Use CustomUser and expose username, email and role."""

        model = CustomUser
        fields = ("username", "email", "role")

    def clean_email(self):
        """
        Validate that the email address is not already registered.

        Normalises to lowercase and strips whitespace before checking.
        Raises ValidationError with a clear message if a duplicate is found.
        """
        raw_email = self.cleaned_data.get("email", "")
        if not raw_email:
            raise ValidationError("An email address is required.")
        normalised = raw_email.strip().lower()
        if CustomUser.objects.filter(email__iexact=normalised).exists():
            raise ValidationError(
                "An account with this email address already exists. "
                "Please use a different email address or log in."
            )
        return normalised


class ArticleForm(forms.ModelForm):
    """
    Form for creating and editing an Article.

    The author field is excluded and set in the view so a journalist
    cannot submit an article under another journalist's name.
    """

    class Meta:
        """Expose title, content and publisher fields."""

        model = Article
        fields = ["title", "content", "publisher"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 10}),
        }


class NewsletterForm(forms.ModelForm):
    """
    Form for creating and editing a Newsletter.

    Filters the articles queryset at instantiation:
    Journalists see only their own approved articles.
    Editors see all approved articles.
    """

    class Meta:
        """Expose title, description and articles fields."""

        model = Newsletter
        fields = ["title", "description", "articles"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, author=None, **kwargs):
        """
        Initialise and filter the articles queryset by the author's role.

        Parameters
        ----------
        author : CustomUser or None
            If a Journalist, only their approved articles are shown.
            If an Editor or None, all approved articles are shown.
        """
        super().__init__(*args, **kwargs)
        if author is not None and author.role == CustomUser.JOURNALIST:
            self.fields["articles"].queryset = Article.objects.filter(
                approved=True, author=author
            )
        else:
            self.fields["articles"].queryset = Article.objects.filter(approved=True)


class PublisherForm(forms.ModelForm):
    """
    Form for creating and editing a Publisher.

    The editors and journalists fields are declared explicitly as
    ModelMultipleChoiceField with CheckboxSelectMultiple widgets so that
    the widget and queryset are bound together correctly from the start.
    The querysets are restricted to users with the correct roles in __init__.
    """

    # Declared explicitly so the widget and queryset stay in sync.
    editors = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="Select editors to assign to this publisher.",
    )
    journalists = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="Select journalists to assign to this publisher.",
    )

    class Meta:
        """Expose name, description, editors and journalists fields."""

        model = Publisher
        fields = ["name", "description", "editors", "journalists"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        """
        Initialise and set the correct querysets for editors and journalists.

        Sets editors queryset to all Editor-role users and journalists
        queryset to all Journalist-role users. This runs after the field
        declarations above so it correctly overrides the empty querysets.
        """
        super().__init__(*args, **kwargs)
        self.fields["editors"].queryset = CustomUser.objects.filter(
            role=CustomUser.EDITOR
        ).order_by("username")
        self.fields["journalists"].queryset = CustomUser.objects.filter(
            role=CustomUser.JOURNALIST
        ).order_by("username")
