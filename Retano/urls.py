# Retano/urls.py  (root URL configuration)
"""
URL routing for the Retano project.

Structure:
    /admin/          — Django admin (kept in all environments)
    /api/v1/         — REST API v1 (DRF)
    /api/schema/     — OpenAPI schema (raw YAML/JSON)
    /api/docs/       — Swagger UI
    /api/redoc/      — ReDoc UI

    Legacy SSR routes (/, /users/, /tickets/) remain active during the
    transition period.  They will be removed in the final cleanup phase
    once the React frontend is live.
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
    # ── Legacy SSR routes — to be removed after React frontend goes live ──
    path("", include("core.urls_legacy")),
    path("users/", include("users.urls_legacy")),
    path("tickets/", include("tickets.urls")),
]

# ─────────────────────────────────────────────────────────────────────────────
# Media files (development only)
# ─────────────────────────────────────────────────────────────────────────────

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
