# core/tests.py

import pytest

from django.urls import reverse

from rest_framework import status

# ─────────────────────────────────────────────────────────────────────────────
# Settings smoke tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSettingsConfiguration:
    """Verify that the DRF configuration loaded correctly."""

    def test_drf_is_installed(self):
        from django.apps import apps

        assert apps.is_installed("rest_framework")

    def test_jwt_is_installed(self):
        from django.apps import apps

        assert apps.is_installed("rest_framework_simplejwt")

    def test_token_blacklist_is_installed(self):
        from django.apps import apps

        assert apps.is_installed("rest_framework_simplejwt.token_blacklist")

    def test_cors_is_installed(self):
        from django.apps import apps

        assert apps.is_installed("corsheaders")

    def test_django_filter_is_installed(self):
        from django.apps import apps

        assert apps.is_installed("django_filters")

    def test_drf_spectacular_is_installed(self):
        from django.apps import apps

        assert apps.is_installed("drf_spectacular")

    def test_drf_default_authentication_is_jwt(self):
        from django.conf import settings

        auth_classes = settings.REST_FRAMEWORK.get("DEFAULT_AUTHENTICATION_CLASSES", [])
        assert any(
            "JWTAuthentication" in cls for cls in auth_classes
        ), "JWT must be the default authentication class."

    def test_drf_default_permission_is_authenticated(self):
        from django.conf import settings

        perm_classes = settings.REST_FRAMEWORK.get("DEFAULT_PERMISSION_CLASSES", [])
        assert any(
            "IsAuthenticated" in cls for cls in perm_classes
        ), "IsAuthenticated must be the default permission class."

    def test_pagination_is_configured(self):
        from django.conf import settings

        pagination_class = settings.REST_FRAMEWORK.get("DEFAULT_PAGINATION_CLASS", "")
        assert "StandardResultsPagination" in pagination_class

    def test_custom_exception_handler_is_configured(self):
        from django.conf import settings

        handler = settings.REST_FRAMEWORK.get("EXCEPTION_HANDLER", "")
        assert "custom_exception_handler" in handler

    def test_secret_key_is_set(self):
        from django.conf import settings

        assert settings.SECRET_KEY
        assert len(settings.SECRET_KEY) >= 50


# ─────────────────────────────────────────────────────────────────────────────
# API documentation endpoint tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAPIDocumentationEndpoints:
    """Verify Swagger and ReDoc render without errors."""

    def test_schema_endpoint_returns_200(self, api_client):
        url = reverse("schema")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_swagger_ui_returns_200(self, api_client):
        url = reverse("swagger-ui")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_redoc_returns_200(self, api_client):
        url = reverse("redoc")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK


# ─────────────────────────────────────────────────────────────────────────────
# Token refresh endpoint
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTokenRefreshEndpoint:
    """Verify the token refresh endpoint is wired correctly."""

    def test_token_refresh_with_invalid_token_returns_401(self, api_client):
        url = reverse("token-refresh")
        response = api_client.post(url, {"refresh": "invalid-token"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh_with_valid_token_returns_200(self, api_client, tenant_user):
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(tenant_user)
        url = reverse("token-refresh")
        response = api_client.post(url, {"refresh": str(refresh)}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data


# ─────────────────────────────────────────────────────────────────────────────
# Pagination tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStandardResultsPagination:
    """Unit tests for the pagination class — no DB needed."""

    def test_pagination_class_has_correct_page_size(self):
        from core.pagination import StandardResultsPagination

        assert StandardResultsPagination.page_size == 20

    def test_pagination_class_has_correct_max_page_size(self):
        from core.pagination import StandardResultsPagination

        assert StandardResultsPagination.max_page_size == 100


# ─────────────────────────────────────────────────────────────────────────────
# Exception handler tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCustomExceptionHandler:
    """Unit tests for the exception handler shape."""

    def test_validation_error_returns_correct_shape(self):
        from rest_framework.exceptions import ValidationError

        from core.exceptions import custom_exception_handler

        exc = ValidationError({"email": ["This field is required."]})
        response = custom_exception_handler(exc, {})
        assert response is not None
        assert response.data["error"] is True
        assert "status_code" in response.data
        assert "message" in response.data
        assert "details" in response.data

    def test_permission_denied_returns_403_shape(self):
        from rest_framework.exceptions import PermissionDenied

        from core.exceptions import custom_exception_handler

        exc = PermissionDenied()
        response = custom_exception_handler(exc, {})
        assert response is not None
        assert response.data["error"] is True
        assert response.data["status_code"] == 403


# ─────────────────────────────────────────────────────────────────────────────
# Tenant auto-creation signal
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTenantAutoCreation:
    """Verify the post_save signal still works correctly."""

    def test_tenant_created_on_user_creation(self, tenant_user):
        from core.models import Tenant

        assert Tenant.objects.filter(owner=tenant_user).exists()

    def test_each_user_has_exactly_one_tenant(self, tenant_user):
        from core.models import Tenant

        count = Tenant.objects.filter(owner=tenant_user).count()
        assert count == 1

    def test_two_users_have_separate_tenants(self, tenant_user, other_user):
        from core.models import Tenant

        t1 = Tenant.objects.get(owner=tenant_user)
        t2 = Tenant.objects.get(owner=other_user)
        assert t1.pk != t2.pk
