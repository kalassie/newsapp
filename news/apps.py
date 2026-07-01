"""
AppConfig for the ``news`` application.

Registers the application with Django and connects signal handlers once the
app registry is fully populated (in the ``ready`` hook).
"""

from django.apps import AppConfig


class NewsConfig(AppConfig):
    """
    Configuration class for the news Django application.

    Sets the default primary-key type to BigAutoField and imports the
    ``news.signals`` module in ``ready()`` so that the article-approval
    signal handlers are connected before any requests are processed.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "news"

    def ready(self):
        """
        Connect signal handlers when the application registry is ready.

        Importing ``news.signals`` here (rather than at module level) avoids
        circular-import issues that arise if signals.py imports from models.py
        before the app registry has finished loading.
        """
        import news.signals  # noqa: F401
