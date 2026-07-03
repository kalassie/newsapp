"""
Unit tests for the server-rendered front-end views.

Covers:
* Reader subscription to Publishers and Journalists (toggle views).
* Pending articles being hidden from Readers on the publisher detail page.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from news.models import Article, Publisher

User = get_user_model()


class PublisherSubscriptionTests(TestCase):
    """Tests for the Reader -> Publisher subscribe/unsubscribe toggle view."""

    def setUp(self):
        """Create a reader, a publisher, and log the reader in."""
        self.reader = User.objects.create_user(
            username="reader1", password="pass1234",
            email="reader1@example.com", role=User.READER
        )
        self.publisher = Publisher.objects.create(name="Daily Bugle")
        self.client.login(username="reader1", password="pass1234")

    def test_reader_can_subscribe_to_publisher(self):
        """POSTing to the toggle URL should add the publisher to the reader's subscriptions."""
        url = reverse("publisher-subscribe-toggle", args=[self.publisher.pk])
        self.client.post(url)
        self.assertTrue(
            self.reader.subscriptions_publishers.filter(pk=self.publisher.pk).exists()
        )

    def test_reader_can_unsubscribe_from_publisher(self):
        """Posting a second time should remove the subscription (toggle behaviour)."""
        self.reader.subscriptions_publishers.add(self.publisher)
        url = reverse("publisher-subscribe-toggle", args=[self.publisher.pk])
        self.client.post(url)
        self.assertFalse(
            self.reader.subscriptions_publishers.filter(pk=self.publisher.pk).exists()
        )

    def test_non_reader_cannot_subscribe_to_publisher(self):
        """A non-Reader user should be redirected away without subscribing."""
        self.client.logout()
        editor = User.objects.create_user(
            username="ed", password="pass1234",
            email="ed@example.com", role=User.EDITOR
        )
        self.client.login(username="ed", password="pass1234")
        url = reverse("publisher-subscribe-toggle", args=[self.publisher.pk])
        self.client.post(url)
        self.assertEqual(self.publisher.reader_subscribers.count(), 0)


class JournalistSubscriptionTests(TestCase):
    """Tests for the Reader -> Journalist subscribe/unsubscribe toggle view."""

    def setUp(self):
        """Create a reader, a journalist, and log the reader in."""
        self.reader = User.objects.create_user(
            username="reader2", password="pass1234",
            email="reader2@example.com", role=User.READER
        )
        self.journalist = User.objects.create_user(
            username="journo1", password="pass1234",
            email="journo1@example.com", role=User.JOURNALIST
        )
        self.client.login(username="reader2", password="pass1234")

    def test_reader_can_subscribe_to_journalist(self):
        """POSTing to the toggle URL should add the journalist to the reader's subscriptions."""
        url = reverse("journalist-subscribe-toggle", args=[self.journalist.pk])
        self.client.post(url)
        self.assertTrue(
            self.reader.subscriptions_journalists.filter(pk=self.journalist.pk).exists()
        )

    def test_reader_can_unsubscribe_from_journalist(self):
        """Posting a second time should remove the subscription (toggle behaviour)."""
        self.reader.subscriptions_journalists.add(self.journalist)
        url = reverse("journalist-subscribe-toggle", args=[self.journalist.pk])
        self.client.post(url)
        self.assertFalse(
            self.reader.subscriptions_journalists.filter(pk=self.journalist.pk).exists()
        )


class PublisherDetailPendingArticleVisibilityTests(TestCase):
    """Tests that Readers cannot see any info about pending articles on the publisher page."""

    def setUp(self):
        """Create a journalist, a publisher, an approved and a pending article."""
        self.journalist = User.objects.create_user(
            username="journo2", password="pass1234",
            email="journo2@example.com", role=User.JOURNALIST
        )
        self.publisher = Publisher.objects.create(name="City Press")
        self.approved_article = Article.objects.create(
            title="Approved Story", content="...", author=self.journalist,
            publisher=self.publisher, approved=True,
        )
        self.pending_article = Article.objects.create(
            title="Secret Pending Story", content="...", author=self.journalist,
            publisher=self.publisher, approved=False,
        )

    def test_reader_does_not_see_pending_article_title(self):
        """A Reader viewing the publisher page should not see the pending article's title."""
        reader = User.objects.create_user(
            username="reader3", password="pass1234",
            email="reader3@example.com", role=User.READER
        )
        self.client.login(username="reader3", password="pass1234")
        response = self.client.get(reverse("publisher-detail", args=[self.publisher.pk]))
        self.assertContains(response, "Approved Story")
        self.assertNotContains(response, "Secret Pending Story")

    def test_editor_does_see_pending_article_title(self):
        """An Editor viewing the publisher page should still see pending articles."""
        editor = User.objects.create_user(
            username="ed2", password="pass1234",
            email="ed2@example.com", role=User.EDITOR
        )
        self.client.login(username="ed2", password="pass1234")
        response = self.client.get(reverse("publisher-detail", args=[self.publisher.pk]))
        self.assertContains(response, "Approved Story")
        self.assertContains(response, "Secret Pending Story")
