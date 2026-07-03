"""
Unit tests for the News Application model layer.

Covers:
* CustomUser role/group synchronisation.
* CustomUser field clearing on role change.
* CustomUser convenience properties.
* Article model constraints and string representation.
* Newsletter model relationships.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from news.models import Article, Newsletter, Publisher

User = get_user_model()


class CustomUserRoleTests(TestCase):
    """Tests for CustomUser role-to-group synchronisation and field clearing."""

    def test_new_journalist_is_added_to_journalist_group(self):
        """A newly created Journalist user should belong to the Journalist group."""
        user = User.objects.create_user(
            username="jess", password="pass1234",
            email="jess@example.com", role=User.JOURNALIST
        )
        self.assertIn("Journalist", user.groups.values_list("name", flat=True))

    def test_new_reader_is_added_to_reader_group(self):
        """A newly created Reader user should belong to the Reader group."""
        user = User.objects.create_user(
            username="ray", password="pass1234",
            email="ray@example.com", role=User.READER
        )
        self.assertIn("Reader", user.groups.values_list("name", flat=True))

    def test_changing_role_moves_user_to_new_group(self):
        """Changing a user's role should remove them from the old group and add them to the new one."""
        user = User.objects.create_user(
            username="pat", password="pass1234",
            email="pat@example.com", role=User.READER
        )
        self.assertIn("Reader", user.groups.values_list("name", flat=True))

        user.role = User.EDITOR
        user.save()
        group_names = list(user.groups.values_list("name", flat=True))
        self.assertIn("Editor", group_names)
        self.assertNotIn("Reader", group_names)

    def test_journalist_role_clears_reader_subscription_fields(self):
        """When a Reader is changed to Journalist, their subscriptions should be cleared."""
        publisher = Publisher.objects.create(name="Daily Times")
        journalist = User.objects.create_user(
            username="indie", password="pass1234",
            email="indie@example.com", role=User.JOURNALIST
        )
        reader = User.objects.create_user(
            username="sub", password="pass1234",
            email="sub@example.com", role=User.READER
        )
        reader.subscriptions_publishers.add(publisher)
        reader.subscriptions_journalists.add(journalist)
        self.assertEqual(reader.subscriptions_publishers.count(), 1)

        reader.role = User.JOURNALIST
        reader.save()
        reader.refresh_from_db()
        self.assertEqual(reader.subscriptions_publishers.count(), 0)
        self.assertEqual(reader.subscriptions_journalists.count(), 0)

    def test_published_articles_property_empty_for_non_journalist(self):
        """published_articles should return an empty queryset for non-journalists."""
        reader = User.objects.create_user(
            username="r1", password="pass1234",
            email="r1@example.com", role=User.READER
        )
        self.assertEqual(reader.published_articles.count(), 0)

    def test_published_articles_property_for_journalist(self):
        """published_articles should return the journalist's own articles."""
        journalist = User.objects.create_user(
            username="j1", password="pass1234",
            email="j1@example.com", role=User.JOURNALIST
        )
        Article.objects.create(title="Story", content="...", author=journalist)
        self.assertEqual(journalist.published_articles.count(), 1)

    def test_reader_role_clears_journalist_followers(self):
        """When a Journalist is changed to Reader, readers following them should be cleared."""
        journalist = User.objects.create_user(
            username="wasjourno", password="pass1234",
            email="wasjourno@example.com", role=User.JOURNALIST
        )
        follower = User.objects.create_user(
            username="follower", password="pass1234",
            email="follower@example.com", role=User.READER
        )
        follower.subscriptions_journalists.add(journalist)
        self.assertEqual(journalist.subscribed_by_readers.count(), 1)

        journalist.role = User.READER
        journalist.save()
        journalist.refresh_from_db()
        follower.refresh_from_db()
        self.assertEqual(journalist.subscribed_by_readers.count(), 0)
        self.assertEqual(follower.subscriptions_journalists.count(), 0)

    def test_editor_role_has_empty_reader_and_journalist_fields(self):
        """An Editor should have empty Reader fields and no Reader followers."""
        editor = User.objects.create_user(
            username="ed1", password="pass1234",
            email="ed1@example.com", role=User.EDITOR
        )
        self.assertEqual(editor.subscriptions_publishers.count(), 0)
        self.assertEqual(editor.subscriptions_journalists.count(), 0)
        self.assertEqual(editor.subscribed_by_readers.count(), 0)

    def test_email_must_be_unique(self):
        """Creating two users with the same email address should raise an IntegrityError."""
        from django.db import IntegrityError
        User.objects.create_user(
            username="u1", password="pass1234",
            email="shared@example.com", role=User.READER
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="u2", password="pass1234",
                email="shared@example.com", role=User.READER
            )


class ArticleModelTests(TestCase):
    """Tests for the Article model constraints and string representation."""

    def setUp(self):
        """Create a journalist, a reader and a publisher for use in tests."""
        self.journalist = User.objects.create_user(
            username="j", password="pass1234",
            email="journalist@example.com", role=User.JOURNALIST
        )
        self.reader = User.objects.create_user(
            username="r", password="pass1234",
            email="reader@example.com", role=User.READER
        )
        self.publisher = Publisher.objects.create(name="The Herald")

    def test_independent_article_has_no_publisher(self):
        """An article created without a publisher should have publisher=None."""
        article = Article.objects.create(
            title="Indie story", content="text", author=self.journalist
        )
        self.assertIsNone(article.publisher)
        self.assertEqual(article.author, self.journalist)

    def test_publisher_article(self):
        """An article can be associated with a publisher."""
        article = Article.objects.create(
            title="Herald story", content="text",
            author=self.journalist, publisher=self.publisher
        )
        self.assertEqual(article.publisher, self.publisher)

    def test_non_journalist_author_fails_validation(self):
        """A Reader set as the article author should fail model-level validation."""
        article = Article(title="Bad", content="text", author=self.reader)
        with self.assertRaises(ValidationError):
            article.full_clean()

    def test_string_representation(self):
        """__str__ should return the article title."""
        article = Article.objects.create(
            title="My Title", content="text", author=self.journalist
        )
        self.assertEqual(str(article), "My Title")


class NewsletterModelTests(TestCase):
    """Tests for the Newsletter model relationships."""

    def setUp(self):
        """Create a journalist for use in tests."""
        self.journalist = User.objects.create_user(
            username="j", password="pass1234",
            email="journalist@example.com", role=User.JOURNALIST
        )

    def test_newsletter_can_hold_multiple_articles(self):
        """A newsletter's M2M articles relation should accept multiple articles."""
        a1 = Article.objects.create(title="A1", content="x", author=self.journalist)
        a2 = Article.objects.create(title="A2", content="y", author=self.journalist)
        newsletter = Newsletter.objects.create(
            title="Weekly Roundup", author=self.journalist
        )
        newsletter.articles.add(a1, a2)
        self.assertEqual(newsletter.articles.count(), 2)
