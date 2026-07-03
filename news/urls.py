"""
URL configuration for the server-rendered front end.

All paths are relative to the project root (newsapp_project/urls.py).
"""

from django.urls import path

from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Authentication
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Articles
    path("articles/", views.article_list, name="article-list"),
    path("articles/new/", views.article_create, name="article-create"),
    path("articles/<int:pk>/", views.article_detail, name="article-detail"),
    path("articles/<int:pk>/edit/", views.article_edit, name="article-edit"),
    path("articles/<int:pk>/delete/", views.article_delete, name="article-delete"),

    # Editor review / approval
    path("pending-articles/", views.pending_articles, name="pending-articles"),
    path(
        "pending-articles/<int:pk>/approve/",
        views.approve_article,
        name="article-approve",
    ),

    # Newsletters
    path("newsletters/", views.newsletter_list, name="newsletter-list"),
    path("newsletters/new/", views.newsletter_create, name="newsletter-create"),
    path("newsletters/<int:pk>/", views.newsletter_detail, name="newsletter-detail"),
    path("newsletters/<int:pk>/edit/", views.newsletter_edit, name="newsletter-edit"),
    path(
        "newsletters/<int:pk>/delete/",
        views.newsletter_delete,
        name="newsletter-delete",
    ),

    # Publishers (create/edit/delete restricted to editors via view guards)
    path("publishers/", views.publisher_list, name="publisher-list"),
    path("publishers/new/", views.publisher_create, name="publisher-create"),
    path("publishers/<int:pk>/", views.publisher_detail, name="publisher-detail"),
    path("publishers/<int:pk>/edit/", views.publisher_edit, name="publisher-edit"),
    path(
        "publishers/<int:pk>/delete/",
        views.publisher_delete,
        name="publisher-delete",
    ),
    path(
        "publishers/<int:pk>/subscribe/",
        views.toggle_publisher_subscription,
        name="publisher-subscribe-toggle",
    ),

    # Journalists (browse + subscribe, Reader-facing)
    path("journalists/", views.journalist_list, name="journalist-list"),
    path(
        "journalists/<int:pk>/subscribe/",
        views.toggle_journalist_subscription,
        name="journalist-subscribe-toggle",
    ),
]
