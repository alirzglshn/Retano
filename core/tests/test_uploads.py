# core/tests/test_uploads.py
"""
Tests for Phase 6 upload endpoints.

Layer 1 — contract tests (this file):
    Auth enforcement, response shape, missing file, missing mapping fields,
    duplicate coupon guard. No real Excel files needed.

Layer 2 — integration tests:
    Real .xlsx files processed end-to-end. Marked @pytest.mark.integration,
    skipped in CI unless explicitly enabled.
"""

import io
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

CUSTOMERS_URL = "/api/v1/uploads/customers/"
PRODUCTS_URL = "/api/v1/uploads/products/"
COUPONS_URL = "/api/v1/uploads/coupons/"
SAMPLE_FILES_URL = "/api/v1/uploads/sample-files/"

# Minimal valid mapping field sets for each upload type
CUSTOMERS_MAPPING = {
    "customers_internal_id": "0",
    "customers_first_name": "1",
    "customers_last_name": "2",
    "customers_internal_order_id": "3",
    "customers_order_date": "4",
    "customers_quantity": "5",
    "customers_then_product_price": "6",
    "customers_phone_number": "7",
    "customers_internal_product_id": "8",
    "customers_gender": "9",
}

PRODUCTS_MAPPING = {
    "products_internal_product_id": "0",
    "products_product_name": "1",
    "products_category": "2",
    "products_current_product_price": "3",
    "products_first_product_attribute": "4",
    "products_second_product_attribute": "5",
    "products_product_link": "6",
}

COUPONS_MAPPING = {
    "coupons_coupon_code": "0",
    "coupons_discount_percentage": "1",
}


def _fake_xlsx():
    """Minimal in-memory file that passes the 'file present' check."""
    return io.BytesIO(b"PK\x03\x04fake xlsx content")


class UploadAuthTests(TestCase):
    """All upload endpoints require authentication."""

    def setUp(self):
        self.client = APIClient()

    def test_customers_unauthenticated_returns_401(self):
        response = self.client.post(CUSTOMERS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_products_unauthenticated_returns_401(self):
        response = self.client.post(PRODUCTS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_coupons_unauthenticated_returns_401(self):
        response = self.client.post(COUPONS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sample_files_unauthenticated_returns_401(self):
        response = self.client.get(SAMPLE_FILES_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UploadMissingFileTests(TestCase):
    """Missing file field returns structured 400."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_customers_no_file_returns_400(self):
        response = self.client.post(
            CUSTOMERS_URL, CUSTOMERS_MAPPING, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_type"], "file_error")

    def test_products_no_file_returns_400(self):
        response = self.client.post(
            PRODUCTS_URL, PRODUCTS_MAPPING, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error_type"], "file_error")

    def test_coupons_no_file_returns_400(self):
        response = self.client.post(
            COUPONS_URL, COUPONS_MAPPING, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error_type"], "file_error")


class UploadMissingMappingTests(TestCase):
    """Missing mapping fields return structured 400 with error_type mapping_error."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def _fake_file(self, name="test.xlsx"):
        f = io.BytesIO(b"fake")
        f.name = name
        return f

    def test_customers_missing_mapping_returns_400(self):
        # Send file but omit all mapping fields
        response = self.client.post(
            CUSTOMERS_URL,
            {"customers_file": self._fake_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_type"], "mapping_error")
        self.assertEqual(data["rows_processed"], 0)
        self.assertEqual(data["rows_saved"], 0)

    def test_products_missing_mapping_returns_400(self):
        response = self.client.post(
            PRODUCTS_URL,
            {"products_file": self._fake_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error_type"], "mapping_error")

    def test_coupons_missing_mapping_returns_400(self):
        response = self.client.post(
            COUPONS_URL,
            {"coupons_file": self._fake_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error_type"], "mapping_error")


class CouponDuplicateGuardTest(TestCase):
    """
    Duplicate coupon upload prevention.
    Mocks process_coupons to return the duplicate_coupon_error response
    without touching the DB or reading a real file.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def _fake_file(self):
        f = io.BytesIO(b"fake")
        f.name = "coupons.xlsx"
        return f

    @patch("core.views_uploads.process_coupons")
    def test_duplicate_coupon_returns_400_with_correct_error_type(
        self, mock_process
    ):
        mock_process.return_value = {
            "status": "error",
            "error_type": "duplicate_coupon_error",
            "message": "شما هنوز کوپن‌های استفاده نشده دارید.",
            "rows_processed": 0,
            "rows_saved": 0,
        }

        payload = {"coupons_file": self._fake_file(), **COUPONS_MAPPING}
        response = self.client.post(COUPONS_URL, payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["error_type"], "duplicate_coupon_error")
        self.assertEqual(data["rows_saved"], 0)


class SampleFilesViewTests(TestCase):
    """Sample files endpoint returns correct shape and absolute URLs."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_returns_200(self):
        response = self.client.get(SAMPLE_FILES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_has_three_keys(self):
        data = self.client.get(SAMPLE_FILES_URL).json()
        self.assertIn("customers", data)
        self.assertIn("products", data)
        self.assertIn("coupons", data)

    def test_urls_are_absolute(self):
        data = self.client.get(SAMPLE_FILES_URL).json()
        for key in ("customers", "products", "coupons"):
            self.assertTrue(
                data[key].startswith("http"),
                f"{key} URL is not absolute: {data[key]}",
            )

    def test_post_not_allowed(self):
        response = self.client.post(SAMPLE_FILES_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)