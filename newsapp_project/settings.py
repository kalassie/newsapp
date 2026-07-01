"""
Django settings for the News Application capstone project.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a .env file in the project root, if one exists.
# This lets you keep DB_PASSWORD, SECRET_KEY etc. out of source control.
# See .env.example for the variables this project understands.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-only-secret-key-change-this-before-deploying"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    # Local
    "news",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "newsapp_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "newsapp_project.wsgi.application"

# --- Database -----------------------------------------------------------
# This project is required (per the capstone brief) to run on MariaDB.
#
#   1. Install the MariaDB/MySQL client library:  pip install mysqlclient
#      (on Windows this is usually easiest via a prebuilt wheel - see the
#      README for troubleshooting tips).
#   2. Create a database and user in MariaDB, e.g.:
#        CREATE DATABASE newsapp_db CHARACTER SET utf8mb4;
#        CREATE USER 'newsapp_user'@'localhost' IDENTIFIED BY 'yourpassword';
#        GRANT ALL PRIVILEGES ON newsapp_db.* TO 'newsapp_user'@'localhost';
#   3. Copy .env.example to .env (or just export the variables) with your
#      own DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT.
#
# For quick local testing without MariaDB installed (e.g. to just run the
# automated test suite), set the environment variable DB_ENGINE=sqlite3 and
# the project will fall back to a local SQLite file instead.
DB_ENGINE = os.environ.get("DB_ENGINE", "mysql")

if DB_ENGINE == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "newsapp_db"),
            "USER": os.environ.get("DB_USER", "newsapp_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                "charset": "utf8mb4",
            },
        }
    }

# --- Custom user model -----------------------------------------------------
AUTH_USER_MODEL = "news.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "news" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework --------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# --- Email -------------------------------------------------------------------
# Defaults to printing emails to the console so the project works out of
# the box. Point EMAIL_BACKEND at django.core.mail.backends.smtp.EmailBackend
# (and fill in the EMAIL_HOST_* variables) to send real emails.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 25))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False") == "True"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "news@example.com")

# --- Internal "external" API used to simulate sharing approved articles ----
# The Article post-approval signal POSTs here using the `requests` module.
APPROVED_ARTICLE_API_URL = os.environ.get(
    "APPROVED_ARTICLE_API_URL", "http://127.0.0.1:8000/api/approved/"
)
