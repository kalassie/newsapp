"""
REST API views for the News Application.

Required endpoints (per the brief)
------------------------------------
GET    /api/articles/             – list all approved articles (all roles), or
                                    all articles for editors/journalists.
GET    /api/articles/subscribed/  – articles from a reader's subscriptions only.
GET    /api/articles/<id>/        – retrieve a single article.
POST   /api/articles/             – create an article (journalists only).
PUT    /api/articles/<id>/        – update an article (editors/journalists).
DELETE /api/articles/<id>/        – delete an article (editors/journalists).
POST   /api/token/                – obtain a token (DRF TokenAuthentication).
POST   /api/approved/             – internal endpoint called by the approval
                                    signal to log newly-approved articles.

Authentication
--------------
All endpoints except ``/api/approved/`` require a valid token supplied via
the ``Authorization: Token <key>`` header.
"""

from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Article, Newsletter
from .permissions import ArticlePermission, NewsletterPermission
from .serializers import ArticleSerializer, NewsletterSerializer


class ArticleListCreateView(generics.ListCreateAPIView):
    """
    List articles or create a new article.

    GET  – Returns approved articles for readers; all articles for editors
           and journalists.
    POST – Creates a new (unapproved) article. Restricted to journalists.
           The ``author`` field is set from the request user, not the body.
    """

    serializer_class = ArticleSerializer
    permission_classes = [ArticlePermission]

    def get_queryset(self):
        """
        Return the appropriate article queryset for the requesting user's role.

        Readers see only approved articles. Editors and Journalists see
        every article regardless of approval status.
        """
        user = self.request.user
        queryset = Article.objects.select_related("author", "publisher")
        if user.role == "reader":
            return queryset.filter(approved=True)
        return queryset

    def perform_create(self, serializer):
        """
        Persist the new article, setting the author to the requesting journalist.

        Parameters
        ----------
        serializer : ArticleSerializer
            The validated serializer instance ready to save.
        """
        serializer.save(author=self.request.user)


class ArticleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a single article.

    GET         – Any authenticated user (readers limited to approved articles
                  via ``ArticlePermission.has_object_permission``).
    PUT / PATCH – Editors (any article) or the journalist who authored it.
    DELETE      – Same rule as PUT/PATCH.
    """

    serializer_class = ArticleSerializer
    permission_classes = [ArticlePermission]
    queryset = Article.objects.select_related("author", "publisher")


class SubscribedArticlesView(generics.ListAPIView):
    """
    List approved articles from publishers/journalists the reader subscribes to.

    Only meaningful for users with the Reader role. Editors and Journalists
    receive an empty list because they do not have subscriptions.
    """

    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return approved articles that match the reader's subscription list.

        Builds a combined Q filter for publisher subscriptions and journalist
        subscriptions, then applies ``distinct()`` to prevent duplicate rows
        when a reader is subscribed to both the journalist and their publisher.
        Non-reader users always receive an empty queryset.
        """
        user = self.request.user
        if user.role != "reader":
            return Article.objects.none()
        publisher_ids = user.subscriptions_publishers.values_list("id", flat=True)
        journalist_ids = user.subscriptions_journalists.values_list("id", flat=True)
        return (
            Article.objects.filter(approved=True)
            .filter(Q(publisher_id__in=publisher_ids) | Q(author_id__in=journalist_ids))
            .distinct()
        )


class NewsletterListCreateView(generics.ListCreateAPIView):
    """
    List all newsletters or create a new one.

    GET  – All authenticated users.
    POST – Journalists and Editors only.
    """

    serializer_class = NewsletterSerializer
    permission_classes = [NewsletterPermission]
    queryset = Newsletter.objects.select_related("author").prefetch_related("articles")


class NewsletterDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a single newsletter.

    GET         – All authenticated users.
    PUT / PATCH – Editors (any newsletter) or the journalist who authored it.
    DELETE      – Same rule as PUT/PATCH.
    """

    serializer_class = NewsletterSerializer
    permission_classes = [NewsletterPermission]
    queryset = Newsletter.objects.select_related("author").prefetch_related("articles")


class ApprovedArticleLogView(APIView):
    """
    Internal endpoint that logs newly-approved articles.

    This endpoint is called by the Article post_save signal (via Python's
    ``requests`` module) immediately after an editor approves an article.
    It simulates publishing the article to an external system while keeping
    the entire integration inside this project.

    The in-memory ``approved_log`` list is intentionally simple: it is enough
    to demonstrate and unit-test the end-to-end signal → API flow without
    requiring a real external service or a persistent log table.

    Endpoints
    ---------
    POST /api/approved/ – Accepts ``{"id": <int>, "title": <str>, ...}`` and
                          appends the payload to the log.
    GET  /api/approved/ – Returns the current log (handy for manual inspection
                          in a browser or Postman during development).
    """

    permission_classes = [permissions.AllowAny]
    approved_log = []

    def post(self, request):
        """
        Accept and log an approved article payload.

        Validates that both ``id`` and ``title`` are present before appending
        to the log. Returns HTTP 400 if either field is missing.

        Parameters
        ----------
        request : Request
            The DRF request containing the article payload as JSON.

        Returns
        -------
        Response
            HTTP 201 on success, HTTP 400 if required fields are absent.
        """
        data = request.data
        if not data.get("id") or not data.get("title"):
            return Response(
                {"detail": "Both 'id' and 'title' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ApprovedArticleLogView.approved_log.append(dict(data))
        return Response(
            {"detail": "Article logged as approved."},
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        """
        Return the current approved-article log as a JSON array.

        Parameters
        ----------
        request : Request
            The incoming DRF request (no body required).

        Returns
        -------
        Response
            HTTP 200 with the list of logged article payloads.
        """
        return Response(ApprovedArticleLogView.approved_log)
