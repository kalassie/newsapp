"""
DRF serializers for the News Application REST API.

Serializer responsibilities
---------------------------
* ``PublisherSerializer`` – read-only representation of a Publisher.
* ``UserSerializer``      – safe representation of a CustomUser (no password).
* ``ArticleSerializer``   – full CRUD; enforces that the author is always the
                            requesting journalist and that only editors may
                            flip the ``approved`` flag.
* ``NewsletterSerializer``– full CRUD; author is always the requesting user.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Article, Newsletter, Publisher

User = get_user_model()


class PublisherSerializer(serializers.ModelSerializer):
    """
    Serializer for the Publisher model.

    Exposes the publisher's id, name and description. Used in API responses
    where a full publisher object is embedded alongside an article.
    """

    class Meta:
        """Serialize id, name and description fields."""

        model = Publisher
        fields = ["id", "name", "description"]


class UserSerializer(serializers.ModelSerializer):
    """
    Read-safe serializer for the CustomUser model.

    Intentionally excludes the password and all sensitive auth fields.
    Used when embedding user information in article or newsletter responses.
    The ``role`` field is read-only; roles are assigned at registration and
    can only be changed by a superuser via the admin.
    """

    class Meta:
        """Serialize id, username, email and role; mark id and role read-only."""

        model = User
        fields = ["id", "username", "email", "role"]
        read_only_fields = ["id", "role"]


class ArticleSerializer(serializers.ModelSerializer):
    """
    Serializer for the Article model.

    Extra read-only fields
    ----------------------
    ``author_username``  – the username of the journalist who wrote the article.
    ``publisher_name``   – the name of the associated publisher, if any.

    Create behaviour
    ----------------
    The ``author`` field is read-only in the serializer. On creation the
    author is set to the authenticated journalist from the request context
    (see ``create``), so a journalist cannot submit an article under another
    name.

    Update / approval behaviour
    ---------------------------
    Only an Editor may flip ``approved`` from False to True. If a Journalist
    attempts to set ``approved=True`` in the request body, the field is
    silently dropped during ``update``. When an Editor does approve, the
    ``approved_at`` timestamp and ``approved_by`` FK are set automatically.
    """

    author_username = serializers.ReadOnlyField(source="author.username")
    publisher_name = serializers.ReadOnlyField(source="publisher.name")

    class Meta:
        """
        Expose article fields; make author, approval metadata and timestamps read-only.
        """

        model = Article
        fields = [
            "id",
            "title",
            "content",
            "author",
            "author_username",
            "publisher",
            "publisher_name",
            "created_at",
            "approved",
            "approved_at",
        ]
        read_only_fields = ["id", "created_at", "author", "approved", "approved_at"]

    def create(self, validated_data):
        """
        Create a new article, setting the author to the current request user.

        The ``author`` field is read-only in the serializer output but must
        be injected here during creation so the correct journalist is recorded
        without exposing an author-override vulnerability.

        Parameters
        ----------
        validated_data : dict
            Cleaned and validated data from the incoming request body.

        Returns
        -------
        Article
            The newly created Article instance.
        """
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Update an article, enforcing the editor-only approval rule.

        If the request body contains ``approved=True`` but the requesting user
        is not an Editor, the ``approved`` key is removed from ``validated_data``
        before the update proceeds, silently preventing self-approval by a
        journalist.

        When an Editor does legitimately approve, ``approved_at`` and
        ``approved_by`` are stamped on the instance before the parent
        ``update`` writes everything to the database.

        Parameters
        ----------
        instance : Article
            The existing Article instance to be updated.
        validated_data : dict
            Cleaned and validated data from the incoming request body.

        Returns
        -------
        Article
            The updated Article instance.
        """
        request = self.context["request"]
        if "approved" in self.initial_data and request.user.role != "editor":
            validated_data.pop("approved", None)
        if validated_data.get("approved") and not instance.approved:
            from django.utils import timezone

            instance.approved_at = timezone.now()
            instance.approved_by = request.user
        return super().update(instance, validated_data)


class NewsletterSerializer(serializers.ModelSerializer):
    """
    Serializer for the Newsletter model.

    Extra read-only field
    ---------------------
    ``author_username`` – username of the journalist who created the newsletter.

    Create behaviour
    ----------------
    The ``author`` is always set to the requesting user (see ``create``), so a
    journalist cannot create a newsletter attributed to someone else.
    """

    author_username = serializers.ReadOnlyField(source="author.username")

    class Meta:
        """Expose newsletter fields; mark id, created_at and author as read-only."""

        model = Newsletter
        fields = [
            "id",
            "title",
            "description",
            "created_at",
            "author",
            "author_username",
            "articles",
        ]
        read_only_fields = ["id", "created_at", "author"]

    def create(self, validated_data):
        """
        Create a new newsletter, setting the author to the current request user.

        Parameters
        ----------
        validated_data : dict
            Cleaned and validated data from the incoming request body.

        Returns
        -------
        Newsletter
            The newly created Newsletter instance.
        """
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
