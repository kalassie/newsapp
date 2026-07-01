"""
Unit tests for the article-approval signal logic.

Verifies that approving an Article triggers:
* A notification email to every subscribed Reader.
* A POST request to the internal ``/api/approved/`` endpoint.

Both external effects are mocked so the tests run quickly without requiring a
real mail server or network connection.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from news.models import Article, Publisher

User = get_user_model()


class ArticleApprovalSignalTests(TestCase):
    """Tests for the post_save signal handler that fires when an article is approved."""

    def setUp(self):
        """Create a journalist, a publisher, a subscribed reader and an article."""
        self.journalist = User.objects.create_user(
            username="journo", password="pass1234",
            email="journo@example.com", role=User.JOURNALIST
        )
        self.publisher = Publisher.objects.create(name="City Press")
        self.subscriber = User.objects.create_user(
            username="subscriber", password="pass1234",
            email="subscriber@example.com", role=User.READER
        )
        self.subscriber.subscriptions_journalists.add(self.journalist)

        self.article = Article.objects.create(
            title="Breaking News",
            content="Something happened.",
            author=self.journalist,
        )

    @patch("news.signals.requests.post")
    def test_approving_article_sends_email_to_subscribers(self, mock_post):
        """Approving an article should send a notification email to subscribed readers."""
        mock_post.return_value.status_code = 201
        self.article.approved = True
        self.article.approved_at = timezone.now()
        self.article.save()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.subscriber.email, mail.outbox[0].to)
        self.assertIn("Breaking News", mail.outbox[0].subject)

    @patch("news.signals.requests.post")
    def test_approving_article_posts_to_internal_api(self, mock_post):
        """Approving an article should POST its details to the internal /api/approved/ endpoint."""
        mock_post.return_value.status_code = 201
        self.article.approved = True
        self.article.approved_at = timezone.now()
        self.article.save()

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["id"], self.article.id)
        self.assertEqual(kwargs["json"]["title"], "Breaking News")

    @patch("news.signals.requests.post")
    def test_resaving_already_approved_article_does_not_resend(self, mock_post):
        """Re-saving an already-approved article must not trigger a second round of notifications."""
        mock_post.return_value.status_code = 201
        self.article.approved = True
        self.article.save()
        mail.outbox = []
        mock_post.reset_mock()

        self.article.title = "Breaking News (updated)"
        self.article.save()

        self.assertEqual(len(mail.outbox), 0)
        mock_post.assert_not_called()

    @patch("news.signals.requests.post")
    def test_no_email_sent_when_no_subscribers(self, mock_post):
        """When no readers are subscribed, no email should be sent but the API POST must still fire."""
        mock_post.return_value.status_code = 201
        lone_journalist = User.objects.create_user(
            username="solo", password="pass1234",
            email="solo@example.com", role=User.JOURNALIST
        )
        article = Article.objects.create(
            title="Quiet story", content="...", author=lone_journalist
        )
        article.approved = True
        article.save()

        self.assertEqual(len(mail.outbox), 0)
        mock_post.assert_called_once()

    @patch("news.signals.requests.post")
    def test_creating_pre_approved_article_fires_signal_once(self, mock_post):
        """A brand-new article saved with approved=True should trigger the signal exactly once."""
        mock_post.return_value.status_code = 201
        Article.objects.create(
            title="Pre-approved", content="x",
            author=self.journalist, approved=True
        )
        mock_post.assert_called_once()
