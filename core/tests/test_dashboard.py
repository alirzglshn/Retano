# core/tests/test_dashboard.py

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

DASHBOARD_URL = "/api/v1/dashboard/"

EXPECTED_TOP_LEVEL_KEYS = {
    "campaigns",
    "customers",
    "monthly_sales",
    "top_products",
    "monthly_trends",
    "rfm_segments",
    "sms_balance",
    "support_unread_count",
}

EXPECTED_CAMPAIGN_KEYS = {"active", "ended", "inactive", "total"}
EXPECTED_CUSTOMER_KEYS = {
    "active", "inactive", "churned", "total",
    "churn_rate_percent", "retention_rate_percent",
}
EXPECTED_RFM_KEYS = {"vip", "active", "new", "at_risk", "churned"}
EXPECTED_TREND_KEYS = {
    "jalali_year", "jalali_month", "month_name",
    "retention_rate_percent", "churn_rate_percent",
}


class DashboardAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        self.assertEqual(
            self.client.get(DASHBOARD_URL).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class DashboardShapeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="pass"
        )
        self.client.force_authenticate(user=self.user)

    def _get(self):
        return self.client.get(DASHBOARD_URL).json()

    def test_returns_200(self):
        self.assertEqual(
            self.client.get(DASHBOARD_URL).status_code,
            status.HTTP_200_OK,
        )

    def test_top_level_keys_present(self):
        self.assertEqual(set(self._get().keys()), EXPECTED_TOP_LEVEL_KEYS)

    def test_campaigns_shape(self):
        self.assertEqual(set(self._get()["campaigns"].keys()), EXPECTED_CAMPAIGN_KEYS)

    def test_customers_shape(self):
        self.assertEqual(set(self._get()["customers"].keys()), EXPECTED_CUSTOMER_KEYS)

    def test_rfm_segments_shape(self):
        self.assertEqual(set(self._get()["rfm_segments"].keys()), EXPECTED_RFM_KEYS)

    def test_monthly_trends_has_6_entries(self):
        trends = self._get()["monthly_trends"]
        self.assertIsInstance(trends, list)
        self.assertEqual(len(trends), 6)

    def test_monthly_trends_entry_shape(self):
        for entry in self._get()["monthly_trends"]:
            self.assertEqual(set(entry.keys()), EXPECTED_TREND_KEYS)

    def test_top_products_is_list(self):
        self.assertIsInstance(self._get()["top_products"], list)

    def test_sms_balance_is_integer(self):
        self.assertIsInstance(self._get()["sms_balance"], int)

    def test_support_unread_count_is_integer(self):
        self.assertIsInstance(self._get()["support_unread_count"], int)

    def test_post_not_allowed(self):
        self.assertEqual(
            self.client.post(DASHBOARD_URL, {}).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )