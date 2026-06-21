# Retano/urls.py  (root URL configuration)
"""
URL routing for the Retano project.

Structure:
    /admin/          — Django admin (kept in all environments)
    /api/v1/         — REST API v1 (DRF)
    /api/schema/     — OpenAPI schema (raw YAML/JSON)
    /api/docs/       — Swagger UI
    /api/redoc/      — ReDoc UI

This project is API-only. Legacy server-rendered routes have been
removed; the frontend is a separate React application that talks to
/api/v1/ exclusively.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# ─────────────────────────────────────────────────────────────────────────────
# API documentation routes
# ─────────────────────────────────────────────────────────────────────────────

api_doc_patterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# ─────────────────────────────────────────────────────────────────────────────
# URL patterns
# ─────────────────────────────────────────────────────────────────────────────

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),
    # OpenAPI / Swagger documentation
    path("api/", include(api_doc_patterns)),
    # REST API v1
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("users.urls")),
]

# ─────────────────────────────────────────────────────────────────────────────
# Media files (development only)
# ─────────────────────────────────────────────────────────────────────────────

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
