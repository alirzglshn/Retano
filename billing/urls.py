from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import BillingConstantView, BillViewSet

router = DefaultRouter()
router.register("billing", BillViewSet, basename="bill")

urlpatterns = [
    path(
        "billing/constants/",
        BillingConstantView.as_view(),
        name="billing-constants",
    ),
    path("", include(router.urls)),
]
