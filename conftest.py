# conftest.py  (project root)
"""
Shared pytest fixtures available to all test modules.

Fixture hierarchy:
    db fixtures (db, django_db) — handled by pytest-django
    tenant_user     — a CustomUser with an auto-created Tenant
    other_user      — a second CustomUser (for tenant isolation tests)
    api_client      — unauthenticated DRF APIClient
    auth_client     — APIClient authenticated as tenant_user via JWT
    other_client    — APIClient authenticated as other_user via JWT
"""

import pytest

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# ─────────────────────────────────────────────────────────────────────────────
# Users and tenants
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def tenant_user(db):
    """Primary test user.  Creating this triggers the post_save signal
    that auto-creates a Tenant."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="testuser",
        email="testuser@retano.test",
        password="SecurePass123!",
        phone_number="09120000001",
        shop_name="Test Shop",
        shop_website_address="https://testshop.example.com",
    )
    return user


@pytest.fixture
def other_user(db):
    """Secondary test user — different tenant, used to verify isolation."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="otheruser",
        email="otheruser@retano.test",
        password="SecurePass123!",
        phone_number="09120000002",
        shop_name="Other Shop",
        shop_website_address="https://othershop.example.com",
    )
    return user


@pytest.fixture
def tenant(tenant_user):
    """Return the Tenant auto-created for tenant_user."""
    from core.models import Tenant

    return Tenant.objects.get(owner=tenant_user)


# ─────────────────────────────────────────────────────────────────────────────
# API clients
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def auth_client(tenant_user):
    """DRF test client authenticated as tenant_user via JWT Bearer token."""
    client = APIClient()
    refresh = RefreshToken.for_user(tenant_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


@pytest.fixture
def other_client(other_user):
    """DRF test client authenticated as other_user via JWT Bearer token."""
    client = APIClient()
    refresh = RefreshToken.for_user(other_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def get_tokens_for_user(user):
    """Helper — returns (access_token_str, refresh_token_str) for a user."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)
