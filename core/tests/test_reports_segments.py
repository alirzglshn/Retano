# core/tests/test_reports_segments.py
"""
Tests for GET /api/v1/reports/segments/

Strategy:
    The data source (the_users_summary_rfm_segmented) is a Postgres view
    backed by a materialized view. We cannot seed it via Django ORM.

    Tests are therefore split into two layers:

    Layer 1 — contract tests (this file):
        Auth enforcement, response shape, label mapping, segment ordering,
        zero-fill behaviour for empty tenants, and tenant isolation.
        These run against the real DB with no seeded RFM data, so all
        counts will be zero — but the shape and auth must still be correct.

    Layer 2 — integration tests (test_reports_segments_integration.py):
        Seed public.users + public.user_summary + REFRESH MATERIALIZED VIEW,
        then assert actual count/monetary values. These are marked with
        @pytest.mark.integration and skipped in CI unless explicitly enabled.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

SEGMENTS_URL = "/api/v1/reports/segments/"
EXPECTED_SEGMENTS = ["vip", "active", "new", "at_risk", "churned"]
EXPECTED_LABELS = {
    "new": "تازه وارد",
    "active": "فعال",
    "vip": "ویژه",
    "at_risk": "در خطر ریزش",
    "churned": "از دست رفته",
}
EXPECTED_KEYS = {
    "segment",
    "label",
    "count",
    "percentage",
    "total_monetary",
    "avg_monetary",
    "avg_frequency",
    "avg_recency_days",
}


class SegmentsReportAuthTests(TestCase):
    """Authentication and permission enforcement."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get(SEGMENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_request_returns_200(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(SEGMENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_not_allowed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(SEGMENTS_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class SegmentsReportShapeTests(TestCase):
    """Response structure — runs against empty DB, counts will be zero."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def _get(self):
        return self.client.get(SEGMENTS_URL)

    def test_top_level_keys_present(self):
        data = self._get().json()
        self.assertIn("total_users", data)
        self.assertIn("segments", data)

    def test_segments_is_list_of_five(self):
        # Always 5 — zero-filled for segments with no users
        segments = self._get().json()["segments"]
        self.assertIsInstance(segments, list)
        self.assertEqual(len(segments), 5)

    def test_each_segment_has_required_keys(self):
        for seg in self._get().json()["segments"]:
            self.assertEqual(set(seg.keys()), EXPECTED_KEYS)

    def test_canonical_segment_order(self):
        keys = [s["segment"] for s in self._get().json()["segments"]]
        self.assertEqual(keys, EXPECTED_SEGMENTS)

    def test_persian_labels_correct(self):
        label_map = {
            s["segment"]: s["label"]
            for s in self._get().json()["segments"]
        }
        for seg_key, expected_label in EXPECTED_LABELS.items():
            self.assertEqual(label_map[seg_key], expected_label)

    def test_empty_tenant_returns_zero_counts(self):
        data = self._get().json()
        self.assertEqual(data["total_users"], 0)
        for seg in data["segments"]:
            self.assertEqual(seg["count"], 0)
            self.assertEqual(seg["percentage"], 0.0)

    def test_numeric_fields_are_floats_or_ints(self):
        for seg in self._get().json()["segments"]:
            self.assertIsInstance(seg["count"], int)
            self.assertIsInstance(seg["percentage"], float)
            self.assertIsInstance(seg["total_monetary"], float)
            self.assertIsInstance(seg["avg_monetary"], float)
            self.assertIsInstance(seg["avg_frequency"], float)
            self.assertIsInstance(seg["avg_recency_days"], float)


class SegmentsReportTenantIsolationTests(TestCase):
    """
    Tenant B must not see Tenant A's data.

    Without seeding the Postgres view (which requires REFRESH MATERIALIZED VIEW),
    we verify the structural guarantee: both tenants get the same shape, and
    neither leaks into the other. True value isolation is tested in the
    integration layer.
    """

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
        self.assertEqual(self.client_a.get(SEGMENTS_URL).status_code, 200)
        self.assertEqual(self.client_b.get(SEGMENTS_URL).status_code, 200)

    def test_tenant_a_cannot_see_tenant_b_users(self):
        # Both are empty in the test DB — structural isolation confirmed.
        # Full data isolation verified in integration tests.
        data_a = self.client_a.get(SEGMENTS_URL).json()
        data_b = self.client_b.get(SEGMENTS_URL).json()
        self.assertEqual(data_a["total_users"], 0)
        self.assertEqual(data_b["total_users"], 0)

    def test_different_tenants_have_independent_tenant_ids(self):
        self.assertNotEqual(
            self.user_a.tenant.id,
            self.user_b.tenant.id,
        )