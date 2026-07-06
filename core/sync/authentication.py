# core/sync/authentication.py
"""
Authentication for the ETL-facing sync endpoints only:
    GET  /api/v1/sync/config/
    POST /api/v1/sync/data/users/
    POST /api/v1/sync/data/products/
    POST /api/v1/sync/report/

Deliberately separate from the JWT auth used everywhere else in the app
(rest_framework_simplejwt) — the ETL is not a logged-in human user, it's a
machine client authenticating with a single long-lived per-tenant key, per
project decision ("one API key per tenant... used for configuration fetch,
data upload, and status reporting").

Usage: Authorization: Bearer <tenant-api-key>
"""

from django.utils import timezone
from rest_framework import authentication, exceptions

from core.models import SyncConfig


class TenantSyncAPIKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None  # let DRF fall through to "not authenticated"

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header. Expected: Bearer <api_key>"
            )

        raw_key = parts[1]
        sync_config = SyncConfig.resolve_from_raw_key(raw_key)
        if sync_config is None:
            raise exceptions.AuthenticationFailed("Invalid or disabled API key.")

        # SyncConfig.tenant has no associated CustomUser we can hand back as
        # request.user in the normal sense — sync views should use
        # request.auth (the SyncConfig) rather than request.user for tenant
        # resolution. We return (None, sync_config) rather than inventing a
        # fake user object, keeping this explicit rather than magical.
        return (None, sync_config)

    def authenticate_header(self, request):
        return self.keyword
