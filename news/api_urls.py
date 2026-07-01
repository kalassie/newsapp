"""
URL configuration for the News Application REST API.

All paths are relative to the ``/api/`` prefix defined in
``newsapp_project/urls.py``.

Authentication
--------------
Clients obtain a token by POSTing credentials to ``/api/token/`` (or the
alias ``/api/login/``).  All subsequent requests include the token in the
``Authorization: Token <key>`` header.

Ordering note
-------------
``articles/subscribed/`` is registered *before* ``articles/<int:pk>/`` so
that Django's URL resolver matches the literal string "subscribed" rather
than attempting to cast it to an integer primary key.
"""

from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import api_views

urlpatterns = [
    # --- Token authentication -----------------------------------------------
    path("token/", obtain_auth_token, name="api-token-auth"),
    path("login/", obtain_auth_token, name="api-login"),

    # --- Articles -----------------------------------------------------------
    path("articles/", api_views.ArticleListCreateView.as_view(), name="api-article-list"),
    path(
        "articles/subscribed/",
        api_views.SubscribedArticlesView.as_view(),
        name="api-article-subscribed",
    ),
    path(
        "articles/<int:pk>/",
        api_views.ArticleDetailView.as_view(),
        name="api-article-detail",
    ),

    # --- Newsletters --------------------------------------------------------
    path(
        "newsletters/",
        api_views.NewsletterListCreateView.as_view(),
        name="api-newsletter-list",
    ),
    path(
        "newsletters/<int:pk>/",
        api_views.NewsletterDetailView.as_view(),
        name="api-newsletter-detail",
    ),

    # --- Internal approval log ----------------------------------------------
    path("approved/", api_views.ApprovedArticleLogView.as_view(), name="api-approved-log"),
]
