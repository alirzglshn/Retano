# Retano/celery.py
#
# Standard Django + Celery bootstrap. Redis is used as both the broker and
# the result backend -- for this workload (upload jobs whose real state of
# record is the UploadJob Postgres row, not the Celery result backend)
# Redis-as-result-backend is mainly useful for task retries/introspection,
# not for progress reporting itself. Progress reporting is read by the
# frontend from UploadJob via the DRF status endpoint, not from Celery's
# result backend, so a frontend never talks to Redis directly.

import os

from celery import Celery

# This project's settings live at config/settings/{base,development,production}.py
# (confirmed via ROOT_URLCONF = "Retano.urls" / WSGI_APPLICATION =
# "Retano.wsgi.application" in config/settings/base.py -- "Retano" is the
# actual Django project package, "config" is just where the settings
# module lives). manage.py and wsgi.py already set DJANGO_SETTINGS_MODULE
# explicitly per environment (development vs production) -- this
# setdefault here is only a safety-net fallback in case celery is invoked
# directly without that env var already set, so it matches whichever
# value manage.py itself defaults to. Check manage.py's own
# os.environ.setdefault(...) call and mirror that exact string here --
# it is almost certainly "config.settings.development" for local runs.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("retano")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


