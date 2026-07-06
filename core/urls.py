# core/urls.py  (DRF API v1 routes)

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import CampaignMetaView, CampaignViewSet

from core.views_reports import (
    SegmentsReportView,
    TrendsReportView,
    SalesRangeReportView,
    ActiveUsersReportView,
    RetentionReportView,
)

from core.views_uploads import (
    CustomerUploadView,
    ProductUploadView,
    CouponUploadView,
    SampleFilesView,
    UploadJobStatusView,   
)
from core.views_dashboard import DashboardView

# ─────────────────────────────────────────────────────────────────────────────
# DefaultRouter — registers ViewSets
# ─────────────────────────────────────────────────────────────────────────────

router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="campaign")

urlpatterns = [
    # ── Campaign meta (Phase 4) ───────────────────────────────────────────
    path("campaigns/meta/", CampaignMetaView.as_view(), name="campaign-meta"),

    # Router-generated URLs
    path("", include(router.urls)),

    # ── Dashboard  ───────────────────────────────────────────────
    path("dashboard/", DashboardView.as_view(), name="api-dashboard"),

    # ── Reports  ─────────────────────────────────────────────────
    path("reports/trends/", TrendsReportView.as_view(), name="report-trends"),
    path("reports/segments/", SegmentsReportView.as_view(), name="reports-segments"),
    path(
        "reports/sales-ranges/",
        SalesRangeReportView.as_view(),
        name="reports-sales-ranges",
    ),
    path(
        "reports/active-users/",
        ActiveUsersReportView.as_view(),
        name="reports-active-users",
    ),
    path(
        "reports/retention/",
        RetentionReportView.as_view(),
        name="reports-retention",
    ),

    # ── File uploads (async — returns 202 + job_id) ────────────────────────
    path("uploads/customers/", CustomerUploadView.as_view(), name="upload-customers"),
    path("uploads/products/", ProductUploadView.as_view(), name="upload-products"),
    path("uploads/coupons/", CouponUploadView.as_view(), name="upload-coupons"),
    path("uploads/sample-files/", SampleFilesView.as_view(), name="upload-sample-files"),

    # ── Upload job status polling (NEW) ─────────────────────────────────────
    path(
        "uploads/jobs/<uuid:job_id>/",
        UploadJobStatusView.as_view(),
        name="upload-job-status",
    ),
]
