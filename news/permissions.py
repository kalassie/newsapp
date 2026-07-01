"""
Role-based DRF permission classes for the News Application REST API.

Role rules (per the brief)
--------------------------
* Readers    – GET only; can only retrieve approved articles.
* Journalists – GET always; POST to create articles/newsletters; PUT/PATCH/DELETE
               only on resources they authored themselves.
* Editors    – Full access: GET, POST, PUT, PATCH, DELETE on any resource;
               the only role permitted to flip ``approved=True`` on an article.
"""

from rest_framework import permissions


class IsReader(permissions.BasePermission):
    """Allow access only to authenticated users with the Reader role."""

    def has_permission(self, request, view):
        """Return True if the requesting user is an authenticated Reader."""
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "reader"
        )


class IsEditor(permissions.BasePermission):
    """Allow access only to authenticated users with the Editor role."""

    def has_permission(self, request, view):
        """Return True if the requesting user is an authenticated Editor."""
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "editor"
        )


class IsJournalist(permissions.BasePermission):
    """Allow access only to authenticated users with the Journalist role."""

    def has_permission(self, request, view):
        """Return True if the requesting user is an authenticated Journalist."""
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "journalist"
        )


class IsEditorOrJournalist(permissions.BasePermission):
    """Allow access to authenticated Editors and Journalists."""

    def has_permission(self, request, view):
        """Return True if the requesting user is an authenticated Editor or Journalist."""
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("editor", "journalist")
        )


class ArticlePermission(permissions.BasePermission):
    """
    Composite permission class for article endpoints.

    Permission matrix
    -----------------
    +-------------------+---------+--------+------------+
    | HTTP method       | Reader  | Editor | Journalist |
    +-------------------+---------+--------+------------+
    | GET (list/detail) | ✓ *     | ✓      | ✓          |
    | POST (create)     | ✗       | ✗      | ✓          |
    | PUT/PATCH (update)| ✗       | ✓ any  | ✓ own only |
    | DELETE            | ✗       | ✓ any  | ✓ own only |
    +-------------------+---------+--------+------------+
    * Readers are further limited to approved articles at the queryset level
      in the view (``ArticleListCreateView.get_queryset``), and at object
      level via ``has_object_permission`` below.
    """

    def has_permission(self, request, view):
        """
        Check request-level permission (before a specific object is identified).

        Returns False for unauthenticated requests.  For authenticated users,
        enforces the role/method matrix at the view level.
        """
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method == "POST":
            return user.role == "journalist"
        if request.method in ("PUT", "PATCH", "DELETE"):
            return user.role in ("editor", "journalist")
        return True  # GET / HEAD / OPTIONS allowed for all authenticated roles

    def has_object_permission(self, request, view, obj):
        """
        Check object-level permission once the specific article is known.

        Readers may only view approved articles.  Journalists may only
        mutate articles they authored.  Editors may mutate any article.
        """
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            if user.role == "reader":
                return obj.approved
            return True
        if user.role == "editor":
            return True
        if user.role == "journalist":
            return obj.author_id == user.id
        return False


class NewsletterPermission(permissions.BasePermission):
    """
    Composite permission class for newsletter endpoints.

    Permission matrix
    -----------------
    +-------------------+---------+--------+------------+
    | HTTP method       | Reader  | Editor | Journalist |
    +-------------------+---------+--------+------------+
    | GET (list/detail) | ✓       | ✓      | ✓          |
    | POST (create)     | ✗       | ✓      | ✓          |
    | PUT/PATCH (update)| ✗       | ✓ any  | ✓ own only |
    | DELETE            | ✗       | ✓ any  | ✓ own only |
    +-------------------+---------+--------+------------+
    """

    def has_permission(self, request, view):
        """
        Check request-level permission for newsletter endpoints.

        All authenticated users may perform safe (read-only) requests.
        POST, PUT, PATCH and DELETE require Editor or Journalist role.
        """
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method == "POST":
            return user.role in ("journalist", "editor")
        if request.method in ("PUT", "PATCH", "DELETE"):
            return user.role in ("editor", "journalist")
        return True

    def has_object_permission(self, request, view, obj):
        """
        Check object-level permission once the specific newsletter is known.

        Editors may mutate any newsletter.  Journalists may only mutate
        newsletters they authored.  Readers are read-only.
        """
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return True
        if user.role == "editor":
            return True
        if user.role == "journalist":
            return obj.author_id == user.id
        return False
