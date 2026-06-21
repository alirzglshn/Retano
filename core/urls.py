# core/urls.py  (DRF API v1 routes)

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import CampaignMetaView, CampaignViewSet

# ─────────────────────────────────────────────────────────────────────────────
# DefaultRouter — registers ViewSets
# Generates:
#   GET    /api/v1/campaigns/         → list
#   POST   /api/v1/campaigns/         → create
#   GET    /api/v1/campaigns/{id}/    → retrieve
#   PUT    /api/v1/campaigns/{id}/    → update
#   PATCH  /api/v1/campaigns/{id}/    → partial_update
#   DELETE /api/v1/campaigns/{id}/    → destroy
#   PATCH  /api/v1/campaigns/{id}/toggle/ → custom action (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="campaign")

urlpatterns = [
    # ── Campaign meta (Phase 4) ───────────────────────────────────────────
    # MUST be declared before the router include below: the router's
    # detail route (campaigns/{id}/) has no numeric restriction on the
    # lookup value, so "campaigns/meta/" would otherwise be matched as
    # campaigns/<pk=meta>/ and routed to retrieve() instead of this view.
    path("campaigns/meta/", CampaignMetaView.as_view(), name="campaign-meta"),
    # Router-generated URLs
    path("", include(router.urls)),
    # ── Dashboard (Phase 7) ───────────────────────────────────────────────
    # path("dashboard/", DashboardView.as_view(), name="api-dashboard"),
    # ── Reports (Phase 5) ─────────────────────────────────────────────────
    # path("reports/trends/", TrendsView.as_view(), name="report-trends"),
    # path("reports/segments/", SegmentsView.as_view(), name="report-segments"),
    # ── File uploads (Phase 6) ────────────────────────────────────────────
    # path("uploads/customers/", CustomerUploadView.as_view(), name="upload-customers"),
    # path("uploads/products/", ProductUploadView.as_view(), name="upload-products"),
    # path("uploads/coupons/", CouponUploadView.as_view(), name="upload-coupons"),
    # path("uploads/sample-files/", SampleFilesView.as_view(), name="upload-sample-files"),
    # ── SMS / Billing (Phase 8) ───────────────────────────────────────────
    # path("sms/packages/", PackagesView.as_view(), name="sms-packages"),
    # path("sms/purchase/", PurchaseView.as_view(), name="sms-purchase"),
    # path("sms/purchase/verify/", PurchaseVerifyView.as_view(), name="sms-purchase-verify"),
    # path("sms/balance/", BalanceView.as_view(), name="sms-balance"),
]
