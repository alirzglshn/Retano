# users/tests/test_sms.py
"""
Tests for Phase 8 — SMS activation request, pricing config, and balance.
No payment gateway involved. All assertions are about ticket creation
and config shape.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import Message, Thread
from users.views_sms import DISCOUNT_TIERS, PRICE_PER_SMS, SMS_SLIDER_MAX, SMS_SLIDER_MIN


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(client, tenant_user):
    client.force_authenticate(user=tenant_user)
    return client, tenant_user


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/sms/packages/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSMSPackagesView:
    url = reverse("sms-packages")

    def test_requires_authentication(self, client):
        assert client.get(self.url).status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_price_per_sms(self, auth_client):
        client, _ = auth_client
        data = client.get(self.url).data
        assert data["price_per_sms"] == PRICE_PER_SMS

    def test_returns_slider_bounds(self, auth_client):
        client, _ = auth_client
        slider = client.get(self.url).data["slider"]
        assert slider["min"] == SMS_SLIDER_MIN
        assert slider["max"] == SMS_SLIDER_MAX

    def test_discount_tiers_are_present_and_ordered(self, auth_client):
        client, _ = auth_client
        tiers = client.get(self.url).data["discount_tiers"]
        # Same count as the constant.
        assert len(tiers) == len(DISCOUNT_TIERS)
        # Descending by min_sms (highest tier first).
        mins = [t["min_sms"] for t in tiers]
        assert mins == sorted(mins, reverse=True)

    def test_each_tier_has_required_keys(self, auth_client):
        client, _ = auth_client
        for tier in client.get(self.url).data["discount_tiers"]:
            assert "min_sms" in tier
            assert "discount_percent" in tier


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/sms/request-activation/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSMSActivationRequestView:
    url = reverse("sms-request-activation")

    def test_requires_authentication(self, client):
        assert client.post(self.url, {"sms_count": 1000}, format="json").status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_request_returns_201(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": 1000}, format="json").status_code == status.HTTP_201_CREATED

    def test_creates_ticket_thread(self, auth_client):
        client, user = auth_client
        client.post(self.url, {"sms_count": 1000}, format="json")
        assert Thread.objects.filter(tenant=user.tenant).exists()

    def test_creates_message_with_correct_body(self, auth_client):
        client, user = auth_client
        client.post(self.url, {"sms_count": 2500}, format="json")
        thread = Thread.objects.get(tenant=user.tenant)
        msg = Message.objects.get(thread=thread)
        assert "2500" in msg.body
        assert "فعال سازی" in msg.body

    def test_message_sender_is_tenant_user(self, auth_client):
        client, user = auth_client
        client.post(self.url, {"sms_count": 1000}, format="json")
        thread = Thread.objects.get(tenant=user.tenant)
        msg = Message.objects.get(thread=thread)
        assert msg.sender == user
        assert msg.sender_type == Message.TENANT

    def test_second_request_reuses_thread(self, auth_client):
        client, user = auth_client
        client.post(self.url, {"sms_count": 1000}, format="json")
        client.post(self.url, {"sms_count": 5000}, format="json")
        assert Thread.objects.filter(tenant=user.tenant).count() == 1
        thread = Thread.objects.get(tenant=user.tenant)
        assert Message.objects.filter(thread=thread).count() == 2

    def test_response_detail_contains_persian_confirmation(self, auth_client):
        client, _ = auth_client
        data = client.post(self.url, {"sms_count": 1000}, format="json").data
        assert "پشتیبانی" in data["detail"]

    # ── Validation ────────────────────────────────────────────────────────

    def test_below_slider_min_is_rejected(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": 999}, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_above_slider_max_is_rejected(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": 500_001}, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_zero_is_rejected(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": 0}, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_negative_is_rejected(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": -100}, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_field_is_rejected(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {}, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_string_value_is_rejected(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": "خیلی"}, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_exact_slider_min_is_accepted(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": SMS_SLIDER_MIN}, format="json").status_code == status.HTTP_201_CREATED

    def test_exact_slider_max_is_accepted(self, auth_client):
        client, _ = auth_client
        assert client.post(self.url, {"sms_count": SMS_SLIDER_MAX}, format="json").status_code == status.HTTP_201_CREATED


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/sms/balance/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSMSBalanceView:
    url = reverse("sms-balance")

    def test_requires_authentication(self, client):
        assert client.get(self.url).status_code == status.HTTP_401_UNAUTHORIZED

    def test_default_balance_is_zero(self, auth_client):
        client, _ = auth_client
        data = client.get(self.url).data
        assert data["num_available_sms"] == 0

    def test_reflects_admin_update(self, auth_client):
        client, user = auth_client
        user.num_available_sms = 25_000
        user.save(update_fields=["num_available_sms"])
        data = client.get(self.url).data
        assert data["num_available_sms"] == 25_000

    def test_response_status_is_200(self, auth_client):
        client, _ = auth_client
        assert client.get(self.url).status_code == status.HTTP_200_OK