# core/tests/test_reports_trends.py
"""
Tests for GET /api/v1/reports/trends/

Same two-layer strategy as segments:
    Layer 1 — contract tests (this file): auth, shape, validation.
    Layer 2 — integration tests: seed orders, assert actual year buckets.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

TRENDS_URL = "/api/v1/reports/trends/"
EXPECTED_YEAR_KEYS = {"jalali_year", "customer_count", "revenue", "clv"}


class TrendsReportAuthTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )

    def test_unauthenticated_returns_401(self):
        response = self.client.get(TRENDS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(TRENDS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_not_allowed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(TRENDS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class TrendsReportShapeTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_top_level_key_is_years(self):
        data = self.client.get(TRENDS_URL).json()
        self.assertIn("years", data)
        self.assertIsInstance(data["years"], list)

    def test_empty_tenant_returns_empty_years(self):
        # No orders seeded — empty list is correct
        data = self.client.get(TRENDS_URL).json()
        self.assertEqual(data["years"], [])

    def test_each_year_entry_has_required_keys(self):
        # Only meaningful once data is seeded — guard for shape correctness
        data = self.client.get(TRENDS_URL).json()
        for entry in data["years"]:
            self.assertEqual(set(entry.keys()), EXPECTED_YEAR_KEYS)

    def test_years_sorted_ascending(self):
        data = self.client.get(TRENDS_URL).json()
        years = [e["jalali_year"] for e in data["years"]]
        self.assertEqual(years, sorted(years))


class TrendsReportYearFilterTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_valid_year_param_returns_200(self):
        response = self.client.get(TRENDS_URL, {"year": "1403"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_integer_year_returns_400(self):
        response = self.client.get(TRENDS_URL, {"year": "blah"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_out_of_range_year_returns_400(self):
        response = self.client.get(TRENDS_URL, {"year": "1200"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_year_filter_returns_years_list(self):
        data = self.client.get(TRENDS_URL, {"year": "1403"}).json()
        self.assertIn("years", data)
        # With no data seeded this will be empty — shape still correct
        self.assertIsInstance(data["years"], list)


class TrendsReportTenantIsolationTests(TestCase):

    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()
        self.user_a = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.user_b = User.objects.create_user(
            phone_number="+989122222222", password="testpass123"
        )
        self.client_a.force_authenticate(user=self.user_a)
        self.client_b.force_authenticate(user=self.user_b)

    def test_both_tenants_receive_200(self):
        self.assertEqual(self.client_a.get(TRENDS_URL).status_code, 200)
        self.assertEqual(self.client_b.get(TRENDS_URL).status_code, 200)

    def test_tenants_have_independent_ids(self):
        self.assertNotEqual(self.user_a.tenant.id, self.user_b.tenant.id)