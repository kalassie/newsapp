"""
Management command: ``create_roles``

Creates (or refreshes) the three Django auth Groups used by this project —
Reader, Editor and Journalist — and assigns each group the correct model-level
permissions on the Article and Newsletter models, per the brief:

    Reader     -> view only
    Editor     -> view, change, delete
    Journalist -> add, view, change, delete

Run this command once after the first ``migrate``, and again any time you
reset the database or add new content types:

    python manage.py create_roles
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from news.models import Article, Newsletter


class Command(BaseCommand):
    """
    Django management command that sets up role-based auth Groups.

    Each group is created with ``get_or_create`` so the command is
    idempotent — running it multiple times is safe and will simply
    overwrite the permission sets with the correct values.
    """

    help = (
        "Creates the Reader, Editor and Journalist groups and assigns "
        "the correct Article/Newsletter permissions to each."
    )

    def handle(self, *args, **options):
        """
        Execute the command.

        Fetches the ContentType records for Article and Newsletter, then
        builds permission querysets for each CRUD action. Each group is
        created or retrieved and its permissions are set (replacing any
        previous set), then a success message is written to stdout.

        Parameters
        ----------
        *args
            Positional arguments passed by Django's management framework
            (not used).
        **options
            Keyword arguments passed by Django's management framework
            (not used).
        """
        content_types = [
            ContentType.objects.get_for_model(Article),
            ContentType.objects.get_for_model(Newsletter),
        ]

        def perms(action):
            """Return permissions matching ``action`` for the relevant content types."""
            return Permission.objects.filter(
                content_type__in=content_types,
                codename__startswith=f"{action}_",
            )

        view_perms = perms("view")
        add_perms = perms("add")
        change_perms = perms("change")
        delete_perms = perms("delete")

        # Reader: view only
        reader_group, _ = Group.objects.get_or_create(name="Reader")
        reader_group.permissions.set(view_perms)

        # Editor: view, change, delete (no add — editors review, not author)
        editor_group, _ = Group.objects.get_or_create(name="Editor")
        editor_group.permissions.set(
            list(view_perms) + list(change_perms) + list(delete_perms)
        )

        # Journalist: full CRUD
        journalist_group, _ = Group.objects.get_or_create(name="Journalist")
        journalist_group.permissions.set(
            list(view_perms) + list(add_perms) + list(change_perms) + list(delete_perms)
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Reader, Editor and Journalist groups created/updated "
                "with their correct permissions."
            )
        )
