# users/tests.py
"""
Tests for Phase 2 (OTP auth + JWT) and Phase 3 (profile + account status).

Uses OTP_FAKE_MODE so no real Kavenegar calls happen; the OTP code is
read back from cache directly rather than parsed off an SMS.
"""

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .auth.otp import _code_key
from .models import CustomUser

PHONE = "09121234567"
PHONE_E164 = "+989121234567"


@override_settings(OTP_FAKE_MODE=True)
class OTPRequestTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_request_otp_success(self):
        url = reverse("auth-otp-request")
        response = self.client.post(url, {"phone_number": PHONE})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], PHONE_E164)
        self.assertIn("debug_code", response.data)  # fake mode echoes it
        self.assertIsNotNone(cache.get(_code_key(PHONE_E164)))

    def test_request_otp_invalid_phone_rejected(self):
        url = reverse("auth-otp-request")
        response = self.client.post(url, {"phone_number": "12345"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_otp_respects_resend_cooldown(self):
        url = reverse("auth-otp-request")
        self.client.post(url, {"phone_number": PHONE})
        response = self.client.post(url, {"phone_number": PHONE})

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@override_settings(OTP_FAKE_MODE=True)
class OTPVerifyTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.request_url = reverse("auth-otp-request")
        self.verify_url = reverse("auth-otp-verify")

    def _issue_code(self):
        response = self.client.post(self.request_url, {"phone_number": PHONE})
        return response.data["debug_code"]

    def test_verify_correct_code_creates_user_and_returns_tokens(self):
        code = self._issue_code()

        response = self.client.post(
            self.verify_url, {"phone_number": PHONE, "code": code}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(
            CustomUser.objects.filter(phone_number=PHONE_E164).exists()
        )

    def test_verify_wrong_code_rejected(self):
        self._issue_code()

        response = self.client.post(
            self.verify_url, {"phone_number": PHONE, "code": "000000"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_expired_code_rejected(self):
        # No code was ever issued for this phone — equivalent to expired.
        response = self.client.post(
            self.verify_url, {"phone_number": PHONE, "code": "123456"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_locks_out_after_max_attempts(self):
        code = self._issue_code()
        wrong = "000000" if code != "000000" else "111111"

        for _ in range(5):
            self.client.post(
                self.verify_url, {"phone_number": PHONE, "code": wrong}
            )

        # Even the correct code should now be rejected — code was burned.
        response = self.client.post(
            self.verify_url, {"phone_number": PHONE, "code": code}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_existing_user_does_not_duplicate(self):
        CustomUser.objects.create_user(phone_number=PHONE_E164)
        code = self._issue_code()

        self.client.post(self.verify_url, {"phone_number": PHONE, "code": code})

        self.assertEqual(
            CustomUser.objects.filter(phone_number=PHONE_E164).count(), 1
        )


class RegisterTests(APITestCase):
    def test_register_creates_user_and_tenant(self):
        url = reverse("auth-register")
        response = self.client.post(
            url,
            {
                "phone_number": PHONE,
                "first_name": "Ali",
                "last_name": "Rezaei",
                "shop_name": "Test Shop",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = CustomUser.objects.get(phone_number=PHONE_E164)
        self.assertTrue(hasattr(user, "tenant"))
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_register_duplicate_phone_rejected(self):
        CustomUser.objects.create_user(phone_number=PHONE_E164)
        url = reverse("auth-register")

        response = self.client.post(url, {"phone_number": PHONE})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(phone_number=PHONE_E164)

    def _tokens_for(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def test_logout_blacklists_refresh_token(self):
        access, refresh = self._tokens_for(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        url = reverse("auth-logout")
        response = self.client.post(url, {"refresh": refresh})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Token refresh should now fail since it's blacklisted.
        refresh_url = reverse("token-refresh")
        retry = self.client.post(refresh_url, {"refresh": refresh})
        self.assertEqual(retry.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        url = reverse("auth-logout")
        response = self.client.post(url, {"refresh": "whatever"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_invalid_token_rejected(self):
        access, _ = self._tokens_for(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        url = reverse("auth-logout")
        response = self.client.post(url, {"refresh": "not-a-real-token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# Profile (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────


class ProfileTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number=PHONE_E164,
            first_name="Ali",
            last_name="Rezaei",
            shop_name="Test Shop",
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("profile")

    def test_get_profile_returns_own_data(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], PHONE_E164)
        self.assertEqual(response.data["first_name"], "Ali")

    def test_patch_profile_updates_allowed_fields(self):
        response = self.client.patch(self.url, {"about_me": "Hello there"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.about_me, "Hello there")

    def test_patch_profile_cannot_change_phone_number(self):
        response = self.client.patch(
            self.url, {"phone_number": "+989120000000"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, PHONE_E164)

    def test_patch_profile_cannot_change_is_premium(self):
        response = self.client.patch(self.url, {"is_premium": True})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_premium)

    def test_profile_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AccountStatusTests(APITestCase):
    def setUp(self):
        self.url = reverse("account-status")

    def test_status_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_reports_incomplete_profile(self):
        user = CustomUser.objects.create_user(phone_number=PHONE_E164)
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["profile_complete"])
        self.assertTrue(response.data["has_tenant"])
        self.assertTrue(response.data["phone_verified"])
        self.assertFalse(response.data["is_premium"])

    def test_status_reports_complete_profile(self):
        user = CustomUser.objects.create_user(
            phone_number=PHONE_E164,
            first_name="Ali",
            last_name="Rezaei",
            shop_name="Test Shop",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)

        self.assertTrue(response.data["profile_complete"])
