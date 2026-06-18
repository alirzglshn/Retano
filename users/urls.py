# users/urls.py  (DRF API v1 auth + profile routes)

from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

# These views will be implemented in Phase 2 and Phase 3.
# They are stubbed here as comments to define the contract now.

urlpatterns = [
    # ── Authentication (Phase 2) ──────────────────────────────────────────
    # POST /api/v1/auth/otp/request/
    # path("auth/otp/request/", OTPRequestView.as_view(), name="auth-otp-request"),
    # POST /api/v1/auth/otp/verify/
    # path("auth/otp/verify/", OTPVerifyView.as_view(), name="auth-otp-verify"),
    # POST /api/v1/auth/register/
    # path("auth/register/", RegisterView.as_view(), name="auth-register"),
    # POST /api/v1/auth/logout/
    # path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    # POST /api/v1/auth/token/refresh/   (Simple JWT — built-in view, no customization needed)
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    # ── Profile (Phase 3) ─────────────────────────────────────────────────
    # GET/PATCH /api/v1/profile/
    # path("profile/", ProfileView.as_view(), name="profile"),
    # GET /api/v1/account/status/
    # path("account/status/", AccountStatusView.as_view(), name="account-status"),
]
