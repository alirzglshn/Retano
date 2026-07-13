# Retano/wsgi.py
"""
WSGI config for the Retano project.

Exposes the WSGI callable as a module-level variable named ``application``.
The DJANGO_SETTINGS_MODULE environment variable must be set before this
module is imported (done by Gunicorn's --env flag or the deployment system).
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.production",
)

application = get_wsgi_application()
