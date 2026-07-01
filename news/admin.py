"""
Django admin registrations for the News Application.

Registers all four models (CustomUser, Publisher, Article, Newsletter) with
custom ModelAdmin classes that provide useful list displays, filters, search
fields and inline many-to-many widgets.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Article, CustomUser, Newsletter, Publisher


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin configuration for the CustomUser model.

    Extends Django's built-in UserAdmin with the custom ``role`` field and
    the reader-only subscription M2M fields (subscriptions_publishers and
    subscriptions_journalists). The role and subscription fields are grouped
    in a separate fieldset labelled "Role & Subscriptions".
    """

    fieldsets = UserAdmin.fieldsets + (
        ("Role & Subscriptions", {
            "fields": (
                "role",
                "subscriptions_publishers",
                "subscriptions_journalists",
            ),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)
    filter_horizontal = UserAdmin.filter_horizontal + (
        "subscriptions_publishers",
        "subscriptions_journalists",
    )


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Publisher model.

    Provides a searchable list of publishers with horizontal filter widgets
    for assigning editors and journalists. Editors can also manage publishers
    through the front-end publisher management views.
    """

    list_display = ("name",)
    filter_horizontal = ("editors", "journalists")
    search_fields = ("name",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Article model.

    Shows key fields at a glance in the list view and supports filtering by
    approval status and publisher. The author and approved_by FKs use
    autocomplete to handle large user tables efficiently.
    """

    list_display = ("title", "author", "publisher", "approved", "created_at")
    list_filter = ("approved", "publisher")
    search_fields = ("title", "content", "author__username")
    autocomplete_fields = ("author", "approved_by")


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Newsletter model.

    Provides a searchable list of newsletters with a horizontal filter widget
    for selecting the articles included in each newsletter.
    """

    list_display = ("title", "author", "created_at")
    search_fields = ("title", "author__username")
    filter_horizontal = ("articles",)
