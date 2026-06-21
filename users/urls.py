# users/urls.py  (DRF API v1 auth + profile routes)

from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AccountStatusView,
    LogoutView,
    OTPRequestView,
    OTPVerifyView,
    ProfileView,
    RegisterView,
)

urlpatterns = [
    # ── Authentication (Phase 2) ──────────────────────────────────────────
    path("auth/otp/request/", OTPRequestView.as_view(), name="auth-otp-request"),
    path("auth/otp/verify/", OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    # ── Profile (Phase 3) ─────────────────────────────────────────────────
    path("profile/", ProfileView.as_view(), name="profile"),
    path("account/status/", AccountStatusView.as_view(), name="account-status"),
]
