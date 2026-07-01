"""
Models for the News Application capstone project.

Roles
-----
Every user has exactly one role: Reader, Editor or Journalist. The role
drives which Django auth Group the user belongs to and which custom fields
are active:

* Readers     -> subscriptions_publishers / subscriptions_journalists
* Journalists -> articles_authored / newsletters_authored (reverse relations)
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.

    Each user has exactly one role (Reader, Editor or Journalist). The role
    controls Django auth Group membership and activates the correct fields.
    Email is required and unique so subscription notifications reach one inbox.
    """

    READER = "reader"
    EDITOR = "editor"
    JOURNALIST = "journalist"
    ROLE_CHOICES = [
        (READER, "Reader"),
        (EDITOR, "Editor"),
        (JOURNALIST, "Journalist"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=READER,
        help_text="Determines the user's group membership and permissions.",
    )

    # Unique email required for subscription notification delivery.
    email = models.EmailField(
        unique=True,
        help_text="Required. Must be unique. Subscription emails are sent here.",
    )

    # Reader-only subscription fields.
    subscriptions_publishers = models.ManyToManyField(
        "Publisher",
        blank=True,
        related_name="reader_subscribers",
        help_text="Publishers this reader subscribes to.",
    )
    subscriptions_journalists = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="subscribed_by_readers",
        limit_choices_to={"role": JOURNALIST},
        help_text="Journalists this reader follows.",
    )

    def __str__(self):
        """Return username and role as the string representation."""
        return f"{self.username} ({self.get_role_display()})"

    def is_reader(self):
        """Return True if this user has the Reader role."""
        return self.role == self.READER

    def is_editor(self):
        """Return True if this user has the Editor role."""
        return self.role == self.EDITOR

    def is_journalist(self):
        """Return True if this user has the Journalist role."""
        return self.role == self.JOURNALIST

    @property
    def published_articles(self):
        """Return articles authored by this journalist, or empty queryset for other roles."""
        if self.role != self.JOURNALIST:
            return Article.objects.none()
        return self.articles_authored.all()

    @property
    def published_newsletters(self):
        """Return newsletters authored by this journalist, or empty queryset for other roles."""
        if self.role != self.JOURNALIST:
            return Newsletter.objects.none()
        return self.newsletters_authored.all()

    def save(self, *args, **kwargs):
        """Save the user and sync role group membership and subscription fields."""
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if not is_new:
            self._clear_fields_not_relevant_to_role()
        self._sync_role_group()

    def _clear_fields_not_relevant_to_role(self):
        """Clear Reader subscription fields when a user becomes a Journalist."""
        if self.role == self.JOURNALIST:
            self.subscriptions_publishers.clear()
            self.subscriptions_journalists.clear()

    def _sync_role_group(self):
        """Ensure the user belongs to exactly one role-based auth Group."""
        target_group_name = self.get_role_display()
        target_group, _ = Group.objects.get_or_create(name=target_group_name)
        all_role_group_names = [label for _, label in self.ROLE_CHOICES]
        stale_groups = Group.objects.filter(
            name__in=all_role_group_names
        ).exclude(pk=target_group.pk)
        self.groups.remove(*stale_groups)
        self.groups.add(target_group)


class Publisher(models.Model):
    """
    A curated publication grouping editors and journalists under one brand.

    Editors create and manage publishers via the front-end publisher views.
    Readers subscribe to publishers to receive approved article notifications.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    editors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="editor_publishers",
        limit_choices_to={"role": CustomUser.EDITOR},
        help_text="Editors who work for this publisher.",
    )
    journalists = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="journalist_publishers",
        limit_choices_to={"role": CustomUser.JOURNALIST},
        help_text="Journalists affiliated with this publisher.",
    )

    class Meta:
        """Order publishers alphabetically by name."""

        ordering = ["name"]

    def __str__(self):
        """Return the publisher name as the string representation."""
        return self.name


class Article(models.Model):
    """
    A news article written by a journalist.

    Articles start unapproved. When an Editor approves one, a Django signal
    emails subscribers and POSTs to the internal /api/approved/ endpoint.
    An article with no publisher is an independent piece by the journalist.
    """

    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles_authored",
        limit_choices_to={"role": CustomUser.JOURNALIST},
        help_text="The journalist who wrote this article.",
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        help_text="Leave blank for an independent article.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(
        default=False,
        help_text="Whether this article has been approved by an editor.",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles_approved",
        limit_choices_to={"role": CustomUser.EDITOR},
        help_text="The editor who approved this article.",
    )

    class Meta:
        """Order articles newest first."""

        ordering = ["-created_at"]

    def __str__(self):
        """Return the article title as the string representation."""
        return self.title

    def clean(self):
        """Validate that author is a Journalist and approved_by is an Editor."""
        super().clean()
        if self.author_id and self.author.role != CustomUser.JOURNALIST:
            raise ValidationError(
                "Only users with the Journalist role may author articles."
            )
        if self.approved_by_id and self.approved_by.role != CustomUser.EDITOR:
            raise ValidationError(
                "Only users with the Editor role may approve articles."
            )


class Newsletter(models.Model):
    """
    A curated collection of approved articles assembled by a journalist.

    Viewable by all authenticated users. Created and managed by Journalists
    and Editors.
    """

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="newsletters_authored",
        limit_choices_to={"role": CustomUser.JOURNALIST},
        help_text="The journalist who created this newsletter.",
    )
    articles = models.ManyToManyField(
        Article,
        blank=True,
        related_name="newsletters",
        help_text="Approved articles included in this newsletter.",
    )

    class Meta:
        """Order newsletters newest first."""

        ordering = ["-created_at"]

    def __str__(self):
        """Return the newsletter title as the string representation."""
        return self.title

    def clean(self):
        """Validate that only a Journalist may author a newsletter."""
        super().clean()
        if self.author_id and self.author.role != CustomUser.JOURNALIST:
            raise ValidationError(
                "Only users with the Journalist role may author newsletters."
            )
