# core/openapi_extensions.py
"""
drf-spectacular authentication extensions.

Why this file exists
---------------------
drf-spectacular auto-detects security schemes for authentication classes it
recognizes out of the box (e.g. rest_framework_simplejwt.authentication.
JWTAuthentication via its own bundled contrib extension). It has no idea
what core.sync.authentication.TenantSyncAPIKeyAuthentication is, because
that class is custom to this project.

Without an extension registered for it, every view under
core/views_sync.py (BaseSyncAPIView and its subclasses) would either show
NO security requirement in Swagger UI (implying the endpoint is public,
which is wrong and dangerous to document) or would incorrectly inherit
whatever scheme DRF's SPECTACULAR_SETTINGS default picks. Either way,
someone using Swagger UI's "Authorize" button to test a /api/v1/sync/*
endpoint would have no visible way to supply the tenant's sync API key,
and would get an opaque 401 with no explanation of what credential the
endpoint actually wants.

This module registers a second, clearly-labeled Bearer scheme
("syncApiKeyAuth") alongside the existing JWT scheme ("jwtAuth", provided
automatically by drf-spectacular's bundled Simple JWT extension). Swagger
UI's Authorize modal will then show two independent locks: one for JWT
(used by every human-facing endpoint) and one for the sync API key (used
exclusively by the four ETL-facing endpoints in core/views_sync.py).

Registration
------------
drf-spectacular discovers OpenApiAuthenticationExtension subclasses via
its own internal registry (OpenApiGeneratorExtension._registry), which is
populated as a side effect of the class body executing -- i.e. simply
importing this module registers the extension. It does NOT require an
entry in SPECTACULAR_SETTINGS. See core/apps.py (CoreConfig.ready) for
where this import is triggered; Django guarantees ready() runs once,
after the app registry is fully populated, which is the correct place
for this kind of side-effecting import (as opposed to importing it at
the top of settings/base.py, which risks running before app loading is
complete).
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class TenantSyncAPIKeySchemeExtension(OpenApiAuthenticationExtension):
    """
    Security scheme for core.sync.authentication.TenantSyncAPIKeyAuthentication.

    Mirrors drf_spectacular.contrib.rest_framework_simplejwt.SimpleJWTScheme's
    approach (build_bearer_security_scheme_object) since both schemes use
    the exact same wire format: `Authorization: Bearer <token>`. The two
    schemes differ only in what the token IS and who is allowed to hold
    one -- a tenant's single long-lived sync API key here, versus a human
    user's short-lived JWT access token elsewhere -- which is exactly why
    they must be two distinct, separately-named security schemes rather
    than sharing "jwtAuth". Reusing the JWT scheme name would make Swagger
    UI apply a JWT-shaped token to sync endpoints (or vice versa), which
    is both confusing and factually wrong about what credential each
    endpoint accepts.
    """

    target_class = "core.sync.authentication.TenantSyncAPIKeyAuthentication"
    name = "syncApiKeyAuth"

    def get_security_definition(self, auto_schema):
        scheme = build_bearer_security_scheme_object(
            header_name="Authorization",
            token_prefix="Bearer",
            bearer_format="Tenant Sync API Key",
        )
        # build_bearer_security_scheme_object already returns the correct
        # {"type": "http", "scheme": "bearer", "bearerFormat": ...} shape
        # for the Authorization/Bearer case. We layer on a human-readable
        # description so the Swagger UI Authorize modal explains, in
        # place, that this is NOT the same credential as jwtAuth.
        scheme["description"] = (
            "Per-tenant sync API key for the ETL-facing endpoints under "
            "/api/v1/sync/ (config fetch, data ingest, run reporting). "
            "This is NOT a JWT and is unrelated to the jwtAuth scheme used "
            "by every other endpoint in this API. Generate a key from the "
            "human-facing POST /api/v1/sync-conf/generate-key/ endpoint "
            "(JWT-authenticated), then supply it here as: "
            "Authorization: Bearer <api_key>. "
            "The key is enabled only after every field mapping row has "
            "been completed on the API-Conf page; a disabled or unknown "
            "key returns 401."
        )
        return scheme
