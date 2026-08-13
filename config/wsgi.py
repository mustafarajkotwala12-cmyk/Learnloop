"""WSGI entry point used by Gunicorn and Vercel's Python runtime."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Vercel's Python runtime commonly looks for ``app`` while Django's WSGI
# setting uses ``application``. Keeping both names makes the module work in
# local development and in the deployment configuration.
app = application
