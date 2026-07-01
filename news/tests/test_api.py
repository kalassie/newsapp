"""
Automated tests for the News Application REST API.

Covers:
* Token authentication (obtain, invalid credentials, unauthenticated access).
* Role-based access control on article and newsletter endpoints.
* Reader subscription filtering (``/api/articles/subscribed/``).
* Newsletter creation and access rules.
* The internal ``/api/approved/`` log endpoint.

Both successful (2xx) and failed (4xx) request examples are included for
each rule to provide broad coverage per the brief's requirement.

The approval signal's outbound ``requests.post`` call is mocked in
``BaseAPITestCase.setUp`` to prevent real HTTP calls during the test run.
Signal-specific behaviour is tested separately in ``test_signals.py``.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from news.models import Article, Newsletter, Publisher

User = get_user_model()


class BaseAPITestCase(APITestCase):
    """
    Base test case that creates one user of each role, shared fixtures and
    mocks the outbound ``requests.post`` call made by the approval signal.
    """

    def setUp(self):
        """
        Set up shared test fixtures.

        Creates a publisher, one user of each role, two articles (one approved,
        one pending) and a DRF token for each user. Also patches the
        ``requests.post`` call inside the approval signal so tests do not make
        real outbound HTTP requests.
        """
        self._requests_post_patcher = patch("news.signals.requests.post")
        mock_post = self._requests_post_patcher.start()
        mock_post.return_value.status_code = 201
        self.addCleanup(self._requests_post_patcher.stop)

        self.publisher = Publisher.objects.create(name="Daily Wire News")

        self.journalist = User.objects.create_user(
            username="journalist1", password="pass1234",
            email="j1@example.com", role=User.JOURNALIST
        )
        self.other_journalist = User.objects.create_user(
            username="journalist2", password="pass1234",
            email="j2@example.com", role=User.JOURNALIST
        )
        self.editor = User.objects.create_user(
            username="editor1", password="pass1234",
            email="e1@example.com", role=User.EDITOR
        )
        self.reader = User.objects.create_user(
            username="reader1", password="pass1234",
            email="r1@example.com", role=User.READER
        )

        self.approved_article = Article.objects.create(
            title="Approved Story",
            content="Already approved content.",
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
        )
        self.pending_article = Article.objects.create(
            title="Pending Story",
            content="Awaiting review.",
            author=self.journalist,
        )

        self.journalist_token = Token.objects.create(user=self.journalist)
        self.other_journalist_token = Token.objects.create(user=self.other_journalist)
        self.editor_token = Token.objects.create(user=self.editor)
        self.reader_token = Token.objects.create(user=self.reader)

    def auth(self, token):
        """Set the Authorization header for subsequent client requests."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


class TokenAuthTests(BaseAPITestCase):
    """Tests for the /api/token/ authentication endpoint."""

    def test_obtain_token_with_valid_credentials_succeeds(self):
        """POST with correct credentials should return a token (HTTP 200)."""
        response = self.client.post(
            reverse("api-token-auth"),
            {"username": "reader1", "password": "pass1234"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_obtain_token_with_invalid_credentials_fails(self):
        """POST with wrong password should return HTTP 400."""
        response = self.client.post(
            reverse("api-token-auth"),
            {"username": "reader1", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_is_rejected(self):
        """A request with no token should receive HTTP 401."""
        response = self.client.get(reverse("api-article-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ArticleListTests(BaseAPITestCase):
    """Tests for GET /api/articles/ and POST /api/articles/."""

    def test_reader_only_sees_approved_articles(self):
        """A Reader's article list must exclude unapproved articles."""
        self.auth(self.reader_token)
        response = self.client.get(reverse("api-article-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a["title"] for a in response.data]
        self.assertIn("Approved Story", titles)
        self.assertNotIn("Pending Story", titles)

    def test_editor_sees_all_articles_including_pending(self):
        """An Editor should see both approved and pending articles."""
        self.auth(self.editor_token)
        response = self.client.get(reverse("api-article-list"))
        titles = [a["title"] for a in response.data]
        self.assertIn("Approved Story", titles)
        self.assertIn("Pending Story", titles)

    def test_journalist_create_article_succeeds(self):
        """A Journalist POST should create an article attributed to them (HTTP 201)."""
        self.auth(self.journalist_token)
        response = self.client.post(
            reverse("api-article-list"),
            {"title": "New Scoop", "content": "Big news.", "publisher": self.publisher.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Article.objects.get(title="New Scoop")
        self.assertEqual(created.author, self.journalist)
        self.assertFalse(created.approved)

    def test_reader_cannot_create_article(self):
        """A Reader POST to the article list must be rejected with HTTP 403."""
        self.auth(self.reader_token)
        response = self.client.post(
            reverse("api-article-list"),
            {"title": "Nope", "content": "Should fail."}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Article.objects.filter(title="Nope").exists())

    def test_editor_cannot_create_article(self):
        """An Editor POST to the article list must be rejected with HTTP 403."""
        self.auth(self.editor_token)
        response = self.client.post(
            reverse("api-article-list"),
            {"title": "Editor attempt", "content": "Should fail."}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ArticleDetailTests(BaseAPITestCase):
    """Tests for GET/PUT/PATCH/DELETE /api/articles/<id>/."""

    def test_retrieve_single_article_succeeds(self):
        """Any authenticated user should be able to retrieve an approved article."""
        self.auth(self.reader_token)
        response = self.client.get(
            reverse("api-article-detail", args=[self.approved_article.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Approved Story")

    def test_reader_cannot_view_unapproved_article(self):
        """A Reader trying to retrieve a pending article must receive HTTP 403."""
        self.auth(self.reader_token)
        response = self.client.get(
            reverse("api-article-detail", args=[self.pending_article.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_update_any_article(self):
        """An Editor should be able to PATCH any article regardless of authorship."""
        self.auth(self.editor_token)
        response = self.client.patch(
            reverse("api-article-detail", args=[self.pending_article.id]),
            {"title": "Edited by editor"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_article.refresh_from_db()
        self.assertEqual(self.pending_article.title, "Edited by editor")

    def test_journalist_can_update_own_article(self):
        """A Journalist should be able to PATCH their own article (HTTP 200)."""
        self.auth(self.journalist_token)
        response = self.client.patch(
            reverse("api-article-detail", args=[self.pending_article.id]),
            {"title": "Self edit"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_journalist_cannot_update_someone_elses_article(self):
        """A Journalist PATCHing another journalist's article must receive HTTP 403."""
        self.auth(self.other_journalist_token)
        response = self.client.patch(
            reverse("api-article-detail", args=[self.pending_article.id]),
            {"title": "Hijack attempt"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reader_cannot_update_article(self):
        """A Reader PATCH must be rejected with HTTP 403."""
        self.auth(self.reader_token)
        response = self.client.patch(
            reverse("api-article-detail", args=[self.approved_article.id]),
            {"title": "Reader edit"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_delete_article(self):
        """An Editor should be able to DELETE any article (HTTP 204)."""
        self.auth(self.editor_token)
        response = self.client.delete(
            reverse("api-article-detail", args=[self.pending_article.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Article.objects.filter(id=self.pending_article.id).exists())

    def test_reader_cannot_delete_article(self):
        """A Reader DELETE must be rejected with HTTP 403 and the article must survive."""
        self.auth(self.reader_token)
        response = self.client.delete(
            reverse("api-article-detail", args=[self.approved_article.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Article.objects.filter(id=self.approved_article.id).exists())

    def test_journalist_cannot_self_approve_via_serializer(self):
        """A Journalist setting approved=True in a PATCH body must be silently ignored."""
        self.auth(self.journalist_token)
        response = self.client.patch(
            reverse("api-article-detail", args=[self.pending_article.id]),
            {"approved": True}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_article.refresh_from_db()
        self.assertFalse(self.pending_article.approved)


class SubscribedArticlesTests(BaseAPITestCase):
    """Tests for GET /api/articles/subscribed/."""

    def setUp(self):
        """Extend base setUp with a second publisher and an unsubscribed article."""
        super().setUp()
        self.other_publisher = Publisher.objects.create(name="Unrelated Gazette")
        self.unsubscribed_article = Article.objects.create(
            title="Not subscribed",
            content="...",
            author=self.other_journalist,
            publisher=self.other_publisher,
            approved=True,
        )
        self.reader.subscriptions_publishers.add(self.publisher)

    def test_reader_sees_only_subscribed_content(self):
        """The subscribed endpoint should include subscribed articles and exclude others."""
        self.auth(self.reader_token)
        response = self.client.get(reverse("api-article-subscribed"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a["title"] for a in response.data]
        self.assertIn("Approved Story", titles)
        self.assertNotIn("Not subscribed", titles)

    def test_subscribed_endpoint_excludes_unapproved_articles(self):
        """Even subscribed pending articles must not appear in the subscribed endpoint."""
        self.reader.subscriptions_journalists.add(self.journalist)
        self.auth(self.reader_token)
        response = self.client.get(reverse("api-article-subscribed"))
        titles = [a["title"] for a in response.data]
        self.assertNotIn("Pending Story", titles)

    def test_non_reader_gets_empty_subscribed_list(self):
        """A Journalist calling the subscribed endpoint should receive an empty list."""
        self.auth(self.journalist_token)
        response = self.client.get(reverse("api-article-subscribed"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class NewsletterAPITests(BaseAPITestCase):
    """Tests for the newsletter API endpoints."""

    def test_journalist_can_create_newsletter(self):
        """A Journalist POST should create a newsletter attributed to them (HTTP 201)."""
        self.auth(self.journalist_token)
        response = self.client.post(
            reverse("api-newsletter-list"),
            {
                "title": "Weekly Digest",
                "description": "Top stories",
                "articles": [self.approved_article.id],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        newsletter = Newsletter.objects.get(title="Weekly Digest")
        self.assertEqual(newsletter.author, self.journalist)

    def test_reader_cannot_create_newsletter(self):
        """A Reader POST to the newsletter list must be rejected with HTTP 403."""
        self.auth(self.reader_token)
        response = self.client.post(
            reverse("api-newsletter-list"),
            {"title": "Should fail", "articles": []}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_any_authenticated_user_can_view_newsletters(self):
        """All authenticated roles should be able to GET the newsletter list."""
        Newsletter.objects.create(title="Existing", author=self.journalist)
        self.auth(self.reader_token)
        response = self.client.get(reverse("api-newsletter-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ApprovedArticleLogEndpointTests(BaseAPITestCase):
    """Tests for the internal POST /api/approved/ log endpoint."""

    def test_valid_payload_is_logged(self):
        """A payload with both 'id' and 'title' should be accepted (HTTP 201)."""
        response = self.client.post(
            reverse("api-approved-log"),
            {"id": 1, "title": "Some Article"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_missing_title_is_rejected(self):
        """A payload missing 'title' must be rejected with HTTP 400."""
        response = self.client.post(
            reverse("api-approved-log"),
            {"id": 1},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_id_is_rejected(self):
        """A payload missing 'id' must be rejected with HTTP 400."""
        response = self.client.post(
            reverse("api-approved-log"),
            {"title": "No ID article"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
