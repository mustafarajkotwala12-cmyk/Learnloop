"""Settings for the LearnLoop educational platform."""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes"}

raw_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
ALLOWED_HOSTS = [host.strip() for host in raw_hosts.split(",") if host.strip()]
if ".vercel.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Supabase provides a standard PostgreSQL connection URL. SQLite keeps a fresh
# clone useful without any cloud credentials.
def _parse_database_url(raw_url: str):
    """Safely sanitizes and parses the database URL, falling back gracefully to SQLite if invalid."""
    import re
    import urllib.parse

    url = (raw_url or "").strip().strip("\"'")
    if not url:
        return None

    # Handle accidental missing scheme or leading colon
    if url.startswith("://"):
        url = "postgresql" + url
    elif not any(url.startswith(s) for s in ("postgres://", "postgresql://", "sqlite://", "mysql://")):
        if "://" not in url and "@" in url:
            url = "postgresql://" + url

    # Auto-sanitize unescaped @ or bracket placeholders in password
    match = re.match(r"^(postgres(?:ql)?://)([^:]+):(.*)@([^@/:]+)(?::(\d+))?/(.*)$", url)
    if match:
        proto, user, pwd, host, port, dbname = match.groups()
        if pwd.startswith("[") and pwd.endswith("]"):
            pwd = pwd[1:-1]
        pwd = pwd.strip("\"'")
        quoted_pwd = urllib.parse.quote(urllib.parse.unquote(pwd))
        port_part = f":{port}" if port else ""
        url = f"{proto}{user}:{quoted_pwd}@{host}{port_part}/{dbname}"

    try:
        parsed = dj_database_url.parse(
            url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=os.environ.get("DB_SSL_REQUIRE", "true").lower()
            in {"1", "true", "yes"},
        )
        if os.environ.get("VERCEL"):
            if "OPTIONS" not in parsed:
                parsed["OPTIONS"] = {}
            parsed["OPTIONS"]["connect_timeout"] = 5
        return parsed
    except Exception as exc:
        # Gracefully handle any formatting error so serverless deployment does not crash
        return None

raw_database_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
parsed_db = _parse_database_url(raw_database_url)
if parsed_db:
    DATABASES = {"default": parsed_db}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = int(os.environ.get("DJANGO_SITE_ID", "1"))
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "portal_redirect"
LOGOUT_REDIRECT_URL = "landing"

# django-allauth handles the optional Google OAuth flow. A SocialApp for Google
# must be added in Django admin (or through a data migration) before it is live.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
SOCIALACCOUNT_AUTO_SIGNUP = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "false").lower() in {
    "1",
    "true",
    "yes",
}

