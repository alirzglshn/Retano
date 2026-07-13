# core/schema.py
"""
drf-spectacular @extend_schema / @extend_schema_view wiring for every view
in the project.

This module is the ONLY place Phase 10 adds behavior. Every view file
listed below gets exactly two kinds of changes:
    1. An import of the relevant decorator function(s)/mixin from here.
    2. The decorator applied directly above the view class (or, for
       function-style application on individual methods/actions, above
       the method).

No business logic in any view changes. If you diff any view file
before/after this phase, the only lines that should appear are import
additions and decorator lines.

Files this module's contents get applied to (see the bottom "APPLICATION
MAP" comment block for the exact wiring):
    core/views.py
    core/views_uploads.py
    core/views_sync.py
    core/views_sync_conf.py
    core/views_reports.py
    core/views_dashboard.py
    users/views.py
    users/views_sms.py
    tickets/views.py

Organization: one section per source view file, in the same order as the
"APPLICATION MAP" at the bottom, so a reviewer can jump from "which view
am I looking at" to "which decorator applies to it" without hunting.

A note on the error envelope
-----------------------------
core.serializers_schema.ErrorResponseSerializer documents the standard
envelope produced by core.exceptions.custom_exception_handler. It is
attached to 400/401/403/404/409/429/500 wherever a view's errors are
genuinely raised as DRF exceptions (ValidationError, NotAuthenticated,
PermissionDenied, Http404, APIException subclasses). Several views build
error Response() objects BY HAND instead of raising, and therefore never
pass through that handler — for those, the response documented is the
view's actual literal shape (see core/serializers_schema.py docstrings
for each one), not ErrorResponseSerializer. Silently documenting the
"aspirational" shared envelope on an endpoint that doesn't actually
produce it would be a factually wrong contract for the frontend team to
build against, which is worse than a known inconsistency being visible.
This was left as-is per explicit product decision (out of scope for this
phase) but documented accurately either way.
"""

from rest_framework import serializers

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from drf_spectacular.types import OpenApiTypes

from core.serializers_schema import (
    AccountStatusResponseSerializer,
    ActiveUsersResponseSerializer,
    CampaignMetaResponseSerializer,
    ChatThreadResponseSerializer,
    DashboardResponseSerializer,
    ErrorResponseSerializer,
    OTPRequestResponseSerializer,
    OTPVerifyResponseSerializer,
    RegisterResponseSerializer,
    RetentionResponseSerializer,
    SMSActivationRequestBodySerializer,
    SMSActivationRequestResponseSerializer,
    SMSBalanceResponseSerializer,
    SMSPackagesResponseSerializer,
    SalesRangeResponseSerializer,
    SampleFilesResponseSerializer,
    SegmentsResponseSerializer,
    SupportThreadNotFoundResponseSerializer,
    SyncApiKeyMappingIncompleteResponseSerializer,
    SyncFieldMappingListResponseSerializer,
    SyncFieldMappingSavedResponseSerializer,
    SyncIngestResponseSerializer,
    SyncReportRecordedResponseSerializer,
    TenantMissingResponseSerializer,
    TrendsBadGranularityResponseSerializer,
    TrendsMonthlyResponseSerializer,
    TrendsYearlyResponseSerializer,
    UnreadCountResponseSerializer,
    UploadAcceptedResponseSerializer,
    UploadErrorResponseSerializer,
    UploadJobNotFoundResponseSerializer,
    UploadJobStatusResponseSerializer,
)

from core.serializers import (
    CampaignListSerializer,
    CampaignSerializer,
    CampaignToggleSerializer,
)
from core.serializers_sync import (
    SyncApiKeyGeneratedSerializer,
    SyncConfigFetchSerializer,
    SyncConfigMappingBulkSerializer,
    SyncConfigStatusSerializer,
    SyncReportSerializer,
)
from tickets.serializers import MessageSerializer, SendMessageSerializer, SmsPurchaseRequestSerializer

from users.serializers import (
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
)


# ─────────────────────────────────────────────────────────────────────────
# Cross-app composed serializers (schema-only)
# ─────────────────────────────────────────────────────────────────────────
# These two compositions legitimately need both core and tickets, which is
# exactly why they live here rather than in core/serializers_schema.py —
# this file already imports across app boundaries for view-wiring, so it
# is the correct place for a schema-only class that also needs to import
# across app boundaries. Neither class is used by any view to build an
# actual response; both exist solely to give drf-spectacular a concrete,
# named shape.


class ChatResponseSerializer(ChatThreadResponseSerializer):
    """
    Full {thread_id, messages} shape for GET /api/v1/tickets/chat/ and
    GET /api/v1/tickets/support/{tenant_id}/, extending the thread_id-only
    base declared in core/serializers_schema.py with the real
    tickets.serializers.MessageSerializer.
    """

    messages = MessageSerializer(many=True)


# ═══════════════════════════════════════════════════════════════════════
# core/views.py — Campaigns
# ═══════════════════════════════════════════════════════════════════════

CAMPAIGN_VIEWSET_SCHEMA = extend_schema_view(
    list=extend_schema(
        tags=["Campaigns"],
        summary="List campaigns",
        description=(
            "Paginated, searchable, filterable, orderable list of the "
            "authenticated tenant's own campaigns. A campaign belonging "
            "to a different tenant never appears here and never appears "
            "at any other campaign endpoint — tenant scoping is enforced "
            "in get_queryset(), not at the permission layer."
        ),
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Case-insensitive substring match against `name` only.",
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Exact-match filter, e.g. ?is_active=true.",
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "One of: created_at, name, rule_number. Prefix with "
                    "- for descending, e.g. ?ordering=-created_at "
                    "(also the default ordering when omitted)."
                ),
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="1-based page number.",
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Items per page. Default 20, maximum 100.",
            ),
        ],
        responses={
            200: CampaignListSerializer,
            401: ErrorResponseSerializer,
        },
    ),
    create=extend_schema(
        tags=["Campaigns"],
        summary="Create a campaign",
        description=(
            "`tenant` and `rule_number` are backend-controlled and ignored "
            "if sent — tenant is always the authenticated user's own "
            "tenant, and rule_number auto-increments per tenant."
        ),
        request=CampaignSerializer,
        responses={
            201: CampaignSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=["Campaigns"],
        summary="Retrieve a single campaign",
        description=(
            "A campaign ID belonging to another tenant returns 404, "
            "never 403 — its existence is not revealed to a tenant that "
            "does not own it."
        ),
        responses={
            200: CampaignSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
    update=extend_schema(
        tags=["Campaigns"],
        summary="Replace a campaign (full update)",
        request=CampaignSerializer,
        responses={
            200: CampaignSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
    partial_update=extend_schema(
        tags=["Campaigns"],
        summary="Partially update a campaign",
        request=CampaignSerializer,
        responses={
            200: CampaignSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
)
"""
Applied to CampaignViewSet as a class decorator in core/views.py.

destroy (DELETE) is intentionally NOT given a schema override here —
http_method_names on CampaignViewSet already excludes "delete", so DRF's
router never generates a DELETE route for this ViewSet in the first
place, and drf-spectacular will not document a method the URLConf does
not expose. Nothing to override.
"""


CAMPAIGN_TOGGLE_SCHEMA = extend_schema(
    tags=["Campaigns"],
    summary="Toggle or set a campaign's is_active flag",
    description=(
        "This is the soft-delete endpoint — 'حذف' in the UI calls this "
        "with is_active: false, it never calls DELETE. "
        "Two distinct request bodies are accepted:\n\n"
        "- Empty body ({} or omitted entirely): flips is_active to its "
        "opposite value.\n"
        "- {\"is_active\": true|false}: sets is_active to exactly that "
        "value, regardless of its current value."
    ),
    request=CampaignToggleSerializer,
    responses={
        200: CampaignToggleSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
    examples=[
        OpenApiExample(
            "Flip current value",
            value={},
            request_only=True,
        ),
        OpenApiExample(
            "Set explicitly",
            value={"is_active": False},
            request_only=True,
        ),
    ],
)
"""Applied directly above the `toggle` action method in core/views.py."""


CAMPAIGN_META_SCHEMA = extend_schema(
    tags=["Campaigns"],
    summary="Choice-field options for the campaign create/edit form",
    description=(
        "Returns the available options for every <select> on the "
        "campaign create/edit form: activation_base, comparison_type, "
        "value_unit, gender, buying_power, priority, customer_type, and "
        "coupon_discount_percentage. Does NOT cover "
        "first_product_attribute / second_product_attribute — those are "
        "free-text fields on the Campaign model, not choices=, so there "
        "is no fixed option set to serve for them."
    ),
    responses={
        200: CampaignMetaResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above CampaignMetaView in core/views.py."""


# ═══════════════════════════════════════════════════════════════════════
# core/views_uploads.py
# ═══════════════════════════════════════════════════════════════════════

_UPLOAD_COMMON_RESPONSES_BASE = {
    202: UploadAcceptedResponseSerializer,
    400: UploadErrorResponseSerializer,
    401: ErrorResponseSerializer,
}

CUSTOMER_UPLOAD_SCHEMA = extend_schema(
    tags=["Uploads"],
    summary="Upload the customers Excel file",
    description=(
        "multipart/form-data. One request carries both the file and the "
        "full column-mapping. Every _MAPPING_FIELDS entry below is "
        "REQUIRED and must be a non-negative integer — the zero-based "
        "column index in the uploaded spreadsheet, e.g. "
        "customers_first_name=1 means column B holds first names.\n\n"
        "Returns 202 immediately with a job_id; the actual import runs "
        "asynchronously on a Celery worker. Poll "
        "GET /api/v1/uploads/jobs/{job_id}/ for progress."
    ),
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "customers_file": {
                    "type": "string",
                    "format": "binary",
                    "description": "The .xlsx or .xls file.",
                },
                "customers_internal_id": {
                    "type": "integer",
                    "description": "Column index: customer's unique internal ID.",
                },
                "customers_first_name": {
                    "type": "integer",
                    "description": "Column index: first name.",
                },
                "customers_last_name": {
                    "type": "integer",
                    "description": "Column index: last name.",
                },
                "customers_internal_order_id": {
                    "type": "integer",
                    "description": "Column index: unique internal order ID.",
                },
                "customers_order_date": {
                    "type": "integer",
                    "description": (
                        "Column index: order date. Any common date format "
                        "is accepted (parsed via a flexible multi-format "
                        "parser)."
                    ),
                },
                "customers_quantity": {
                    "type": "integer",
                    "description": "Column index: quantity ordered.",
                },
                "customers_then_product_price": {
                    "type": "integer",
                    "description": (
                        "Column index: the product's price AT THE TIME OF "
                        "PURCHASE (fixed historical value, distinct from "
                        "the product's current price in the products "
                        "file)."
                    ),
                },
                "customers_phone_number": {
                    "type": "integer",
                    "description": "Column index: customer's phone number.",
                },
                "customers_internal_product_id": {
                    "type": "integer",
                    "description": (
                        "Column index: internal product ID — links this "
                        "row to a row in the products file."
                    ),
                },
                "customers_gender": {
                    "type": "integer",
                    "description": "Column index: customer's gender.",
                },
            },
            "required": [
                "customers_file",
                "customers_internal_id",
                "customers_first_name",
                "customers_last_name",
                "customers_internal_order_id",
                "customers_order_date",
                "customers_quantity",
                "customers_then_product_price",
                "customers_phone_number",
                "customers_internal_product_id",
                "customers_gender",
            ],
        },
    },
    responses=_UPLOAD_COMMON_RESPONSES_BASE,
)
"""Applied directly above CustomerUploadView in core/views_uploads.py."""


PRODUCT_UPLOAD_SCHEMA = extend_schema(
    tags=["Uploads"],
    summary="Upload the products Excel file",
    description=(
        "multipart/form-data. Same one-request pattern as the customers "
        "upload. All 7 mapping fields below are REQUIRED, non-negative "
        "integer column indices. first_product_attribute and "
        "second_product_attribute are stored completely as-is with zero "
        "normalization; an empty cell in either column is stored as NULL, "
        "never as an empty string.\n\n"
        "Returns 202 immediately with a job_id; poll "
        "GET /api/v1/uploads/jobs/{job_id}/ for progress."
    ),
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "products_file": {
                    "type": "string",
                    "format": "binary",
                    "description": "The .xlsx or .xls file.",
                },
                "products_internal_product_id": {
                    "type": "integer",
                    "description": "Column index: product's unique internal ID.",
                },
                "products_product_name": {
                    "type": "integer",
                    "description": "Column index: product name.",
                },
                "products_category": {
                    "type": "integer",
                    "description": "Column index: product category.",
                },
                "products_current_product_price": {
                    "type": "integer",
                    "description": (
                        "Column index: current price. This is the value "
                        "used by all analytics/reports going forward, and "
                        "is expected to be updated over time as prices "
                        "change (independent of then_product_price on "
                        "historical orders)."
                    ),
                },
                "products_first_product_attribute": {
                    "type": "integer",
                    "description": (
                        "Column index: first free-text product attribute. "
                        "Empty cell -> stored as NULL, not empty string."
                    ),
                },
                "products_second_product_attribute": {
                    "type": "integer",
                    "description": (
                        "Column index: second free-text product "
                        "attribute. Empty cell -> stored as NULL."
                    ),
                },
                "products_product_link": {
                    "type": "integer",
                    "description": "Column index: URL to the product page.",
                },
            },
            "required": [
                "products_file",
                "products_internal_product_id",
                "products_product_name",
                "products_category",
                "products_current_product_price",
                "products_first_product_attribute",
                "products_second_product_attribute",
                "products_product_link",
            ],
        },
    },
    responses=_UPLOAD_COMMON_RESPONSES_BASE,
)
"""Applied directly above ProductUploadView in core/views_uploads.py."""


COUPON_UPLOAD_SCHEMA = extend_schema(
    tags=["Uploads"],
    summary="Upload the coupons Excel file",
    description=(
        "multipart/form-data. Only 2 mapping fields, both REQUIRED, "
        "non-negative integer column indices.\n\n"
        "Pre-flight guard: if the tenant still has ANY unused "
        "(status='available') coupons from a previous upload, this "
        "endpoint returns 400 with error_type='duplicate_coupon_error' "
        "BEFORE the file is even read — a tenant must exhaust all "
        "existing coupons before a new coupon file can be uploaded.\n\n"
        "Returns 202 immediately with a job_id; poll "
        "GET /api/v1/uploads/jobs/{job_id}/ for progress."
    ),
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "coupons_file": {
                    "type": "string",
                    "format": "binary",
                    "description": "The .xlsx or .xls file.",
                },
                "coupons_coupon_code": {
                    "type": "integer",
                    "description": "Column index: the coupon code string.",
                },
                "coupons_discount_percentage": {
                    "type": "integer",
                    "description": "Column index: discount percentage, 0-100.",
                },
            },
            "required": [
                "coupons_file",
                "coupons_coupon_code",
                "coupons_discount_percentage",
            ],
        },
    },
    responses=_UPLOAD_COMMON_RESPONSES_BASE,
)
"""Applied directly above CouponUploadView in core/views_uploads.py."""


UPLOAD_JOB_STATUS_SCHEMA = extend_schema(
    tags=["Uploads"],
    summary="Poll an upload job's progress",
    description=(
        "Poll this endpoint to track an async upload started by any of "
        "the three upload endpoints. `status` transitions: "
        "queued -> processing -> (success | partial | failed). "
        "`partial` means the flush completed but some rows were skipped "
        "(e.g. missing a required internal ID) — rows_saved reflects "
        "only what actually made it into the database."
    ),
    responses={
        200: UploadJobStatusResponseSerializer,
        401: ErrorResponseSerializer,
        404: UploadJobNotFoundResponseSerializer,
    },
)
"""Applied directly above UploadJobStatusView in core/views_uploads.py."""


SAMPLE_FILES_SCHEMA = extend_schema(
    tags=["Uploads"],
    summary="Get sample Excel template download URLs",
    description=(
        "Returns absolute URLs (built from the current request's host) "
        "for the three static sample Excel templates, for a 'download "
        "template' link in the upload UI."
    ),
    responses={
        200: SampleFilesResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SampleFilesView in core/views_uploads.py."""


# ═══════════════════════════════════════════════════════════════════════
# core/views_sync.py — ETL-facing (sync API key auth)
# ═══════════════════════════════════════════════════════════════════════

SYNC_CONFIG_FETCH_SCHEMA = extend_schema(
    tags=["Sync (ETL)"],
    summary="Fetch this tenant's current sync configuration",
    description=(
        "Authenticated with the tenant's sync API key (see the "
        "syncApiKeyAuth security scheme), NOT a JWT. The ETL container "
        "must call this at the START of every sync cycle rather than "
        "caching it — edits made on the تنظیم API page (JWT-authenticated, "
        "see core/views_sync_conf.py) take effect on the very next cycle "
        "with zero redeployment of the ETL container.\n\n"
        "nullable_fields lists, per entity, which field names may "
        "degrade to NULL on a missing/misnamed COLUMN during the ETL's "
        "own pre-flight schema check, instead of aborting the whole run. "
        "A missing TABLE is always fatal regardless of this list — it "
        "only ever applies at column granularity."
    ),
    responses={
        200: SyncConfigFetchSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SyncConfigFetchView in core/views_sync.py."""


SYNC_USER_INGEST_SCHEMA = extend_schema(
    tags=["Sync (ETL)"],
    summary="Ingest a batch of user/order rows",
    description=(
        "Authenticated with the tenant's sync API key. Assumes the ETL "
        "has ALREADY completed its own pre-flight schema check "
        "(table/column existence against the tenant's actual database) "
        "before calling this — this endpoint performs per-field, per-row "
        "type coercion only, never schema validation, and has no "
        "visibility into the tenant's database.\n\n"
        "Row identity is the COMPOSITE (internal_user_id, "
        "internal_order_id) — a flat per-order-line table, so the same "
        "user appears in many rows, one per order. A row matching an "
        "existing (internal_user_id, internal_order_id) pair is treated "
        "as an UPDATE to that specific order line, not a new record.\n\n"
        "Coercion failures reject the ROW, not the batch — except for "
        "first_product_attribute/second_product_attribute on the product "
        "side, where a coercion failure degrades that field to NULL and "
        "the row proceeds normally. Always returns 200, even when some "
        "or all rows were rejected — check rows_rejected / rejections in "
        "the body, not the HTTP status, to detect partial failures."
    ),
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {"type": "object"},
                    "maxItems": 20000,
                    "description": (
                        "Raw, loosely-typed rows straight from the "
                        "client's database driver — numbers as numbers, "
                        "strings as strings, ISO-8601 date strings, null "
                        "for SQL NULL. This endpoint's coercion layer "
                        "absorbs driver/engine differences; the ETL must "
                        "NOT pre-coerce types itself."
                    ),
                },
            },
            "required": ["rows"],
        },
    },
    responses={
        200: SyncIngestResponseSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above UserSyncIngestView in core/views_sync.py."""


SYNC_PRODUCT_INGEST_SCHEMA = extend_schema(
    tags=["Sync (ETL)"],
    summary="Ingest a batch of product rows",
    description=(
        "Same contract as POST /api/v1/sync/data/users/ — see that "
        "endpoint's description for the full row-identity / coercion / "
        "partial-failure semantics. Row identity here is "
        "internal_product_id alone (products are not per-order-line)."
    ),
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {"type": "object"},
                    "maxItems": 20000,
                },
            },
            "required": ["rows"],
        },
    },
    responses={
        200: SyncIngestResponseSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above ProductSyncIngestView in core/views_sync.py."""


SYNC_REPORT_SCHEMA = extend_schema(
    tags=["Sync (ETL)"],
    summary="Report the outcome of a sync cycle",
    description=(
        "Call exactly once per sync cycle, in one of two situations:\n\n"
        "1. Pre-flight schema check failed and the data-ingest endpoints "
        "were NEVER called: status='failed', failure_stage="
        "'schema_table'|'schema_column', failure_detail=<precise missing "
        "table/column name, for logs only — not shown to the tenant "
        "verbatim>.\n\n"
        "2. The cycle ran to completion (success or partial): "
        "status='success'|'partial', plus the rows_* counters already "
        "returned by the data-ingest endpoints' own responses. This call "
        "exists purely so a SyncRun audit record exists even when "
        "nothing went wrong, giving the تنظیم API page a real 'last "
        "synced at' timestamp."
    ),
    request=SyncReportSerializer,
    responses={
        201: SyncReportRecordedResponseSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SyncReportView in core/views_sync.py."""


# ═══════════════════════════════════════════════════════════════════════
# core/views_sync_conf.py — تنظیم API page (JWT auth)
# ═══════════════════════════════════════════════════════════════════════

SYNC_CONFIG_STATUS_SCHEMA = extend_schema(
    tags=["Sync Configuration"],
    summary="Get the top-of-page sync status",
    description=(
        "is_enabled, masked api_key_prefix, and the outcome of the most "
        "recent SyncRun. Does not include the mapping rows themselves — "
        "see GET /api/v1/sync-conf/mapping/ for those."
    ),
    responses={
        200: SyncConfigStatusSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SyncConfigStatusView in core/views_sync_conf.py."""


SYNC_FIELD_MAPPING_GET_SCHEMA = extend_schema(
    tags=["Sync Configuration"],
    summary="Get every field-mapping row (filled or empty)",
    description=(
        "Always returns exactly 17 rows: 10 user fields + 7 product "
        "fields, from core.sync.field_registry.FIELD_REGISTRY. A field "
        "never saved yet still appears, with client_table/client_column "
        "as empty strings and is_filled=false, so the frontend can "
        "render every rectangle on first page load."
    ),
    responses={
        200: SyncFieldMappingListResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied above SyncFieldMappingView.get in core/views_sync_conf.py."""


SYNC_FIELD_MAPPING_PUT_SCHEMA = extend_schema(
    tags=["Sync Configuration"],
    summary="Replace the entire field mapping atomically",
    description=(
        "ALL 17 rows (both entities, every registry field) must be "
        "present in a single call — a partial save (e.g. only the user "
        "rows) is rejected with a validation error, because تولید API "
        "needs to validate completeness across both entities together "
        "and a partial save would leave the mapping in an ambiguous "
        "state between requests. entity must be 'user' or 'product'; "
        "field_name must exactly match a name in the registry for that "
        "entity."
    ),
    request=SyncConfigMappingBulkSerializer,
    responses={
        200: SyncFieldMappingSavedResponseSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied above SyncFieldMappingView.put in core/views_sync_conf.py."""


SYNC_API_KEY_GENERATE_SCHEMA = extend_schema(
    tags=["Sync Configuration"],
    summary="Generate (or rotate) the tenant's sync API key",
    description=(
        "The 'تولید API' button. Blocked with 400 "
        "(error_type='mapping_incomplete') unless EVERY one of the 17 "
        "mapping rows has both client_table and client_column non-blank "
        "— this includes first_product_attribute/second_product_attribute, "
        "which must still be DECLARED here even though they are the only "
        "two fields allowed to gracefully degrade to NULL later if the "
        "declared column turns out not to exist at sync time.\n\n"
        "On success: generates a new key (silently invalidating any "
        "previous one, since only its hash is stored), enables the "
        "SyncConfig, and returns the RAW key EXACTLY ONCE. It is not "
        "retrievable again after this response — the frontend must "
        "display/copy it immediately."
    ),
    request=None,
    responses={
        201: SyncApiKeyGeneratedSerializer,
        400: SyncApiKeyMappingIncompleteResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SyncApiKeyGenerateView in core/views_sync_conf.py."""


# ═══════════════════════════════════════════════════════════════════════
# core/views_reports.py
# ═══════════════════════════════════════════════════════════════════════

# PolymorphicProxySerializer is drf-spectacular's native mechanism for "one
# endpoint, several genuinely different response shapes, selected by some
# discriminator" — exactly this endpoint's situation. `granularity` is
# already a literal field present in BOTH shapes (values "year"/"month"),
# so it doubles as the discriminator field name with no schema changes
# needed on either underlying serializer. This produces a proper `oneOf`
# in the generated OpenAPI document with both component schemas correctly
# registered as a normal side effect of being passed into `serializers=`
# here — no manual $ref bookkeeping, no dependency on either serializer
# being referenced elsewhere first.
TRENDS_RESPONSE_SCHEMA = PolymorphicProxySerializer(
    component_name="TrendsResponse",
    serializers={
        "year": TrendsYearlyResponseSerializer,
        "month": TrendsMonthlyResponseSerializer,
    },
    resource_type_field_name="granularity",
)

TRENDS_REPORT_SCHEMA = extend_schema(
    tags=["Reports"],
    summary="Customer count / revenue / CLV trends",
    description=(
        "Backs THREE charts on the frontend (تعداد مشتریان, میزان فروش, "
        "CLV) from a single payload — the frontend picks a different "
        "field per chart (customer_count / revenue / clv). There is "
        "intentionally one endpoint here, not three.\n\n"
        "Two response shapes depending on ?granularity=, discriminated "
        "by the `granularity` field itself in the response body:\n\n"
        "- year (default, omit the param entirely): last 4 Jalali years "
        "ending at the current Jalali year, zero-filled for years with "
        "no orders. This is a fixed 4-year window, NOT the tenant's full "
        "order history.\n"
        "- month: re-renders the ENTIRE chart as 6 monthly bars (last 6 "
        "Jalali months including the current month) rather than a "
        "single value — selecting month mode changes the chart shape "
        "per product decision, it does not add a 4th data point to the "
        "yearly view."
    ),
    parameters=[
        OpenApiParameter(
            name="granularity",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=["year", "month"],
            default="year",
            description="Selects which of the two response shapes below is returned.",
        ),
    ],
    responses={
        200: TRENDS_RESPONSE_SCHEMA,
        400: TrendsBadGranularityResponseSerializer,
        403: TenantMissingResponseSerializer,
    },
    examples=[
        OpenApiExample(
            "Yearly (default)",
            value={
                "granularity": "year",
                "data": [
                    {"jalali_year": 1402, "customer_count": 312, "revenue": 4820000000.0, "clv": 15448717.95},
                    {"jalali_year": 1403, "customer_count": 340, "revenue": 5010000000.0, "clv": 14735294.12},
                ],
            },
            response_only=True,
        ),
        OpenApiExample(
            "Monthly (?granularity=month)",
            value={
                "granularity": "month",
                "data": [
                    {
                        "jalali_year": 1405, "jalali_month": 2, "month_name": "اردیبهشت",
                        "customer_count": 40, "revenue": 120000000.0, "clv": 3000000.0,
                    },
                ],
            },
            response_only=True,
        ),
    ],
)
"""
Applied directly above TrendsReportView in core/views_reports.py.

The 200 response uses TRENDS_RESPONSE_SCHEMA (a PolymorphicProxySerializer
defined immediately above), which produces a proper `oneOf` in the
generated OpenAPI document with both TrendsYearlyResponseSerializer and
TrendsMonthlyResponseSerializer registered as named components — this is
drf-spectacular's own supported mechanism for "one endpoint, several
response shapes selected by a discriminator field," and requires no
manual $ref bookkeeping.
"""


SALES_RANGE_REPORT_SCHEMA = extend_schema(
    tags=["Reports"],
    summary="Order-value histogram (بازه‌های فروش)",
    description=(
        "Histogram of individual order totals across the tenant's ENTIRE "
        "order history (not windowed to any date range), bucketed into "
        "4 fixed ranges in tomans. Each order counts exactly once."
    ),
    responses={
        200: SalesRangeResponseSerializer,
        403: TenantMissingResponseSerializer,
    },
)
"""Applied directly above SalesRangeReportView in core/views_reports.py."""


SEGMENTS_REPORT_SCHEMA = extend_schema(
    tags=["Reports"],
    summary="RFM segment distribution (دسته‌بندی RFM)",
    description=(
        "Only users with a non-null rfm_segment are counted. Always "
        "returns exactly 5 segments in a fixed order, zero-filled for "
        "segments with no users."
    ),
    responses={
        200: SegmentsResponseSerializer,
        403: TenantMissingResponseSerializer,
    },
)
"""Applied directly above SegmentsReportView in core/views_reports.py."""


ACTIVE_USERS_REPORT_SCHEMA = extend_schema(
    tags=["Reports"],
    summary="Active vs inactive customer percentage (درصد کاربران فعال)",
    description=(
        "active = rfm_segment IN (vip, new, active); "
        "inactive = rfm_segment IN (churned, at_risk). Only users with a "
        "non-null rfm_segment are counted — totals here always agree "
        "with GET /api/v1/reports/segments/'s total_users."
    ),
    responses={
        200: ActiveUsersResponseSerializer,
        403: TenantMissingResponseSerializer,
    },
)
"""Applied directly above ActiveUsersReportView in core/views_reports.py."""


RETENTION_REPORT_SCHEMA = extend_schema(
    tags=["Reports"],
    summary="Yearly retention / churn (نرخ نگهداری / نرخ ریزش)",
    description=(
        "Computed via the exact same shared function "
        "(core.utils.analytics.get_yearly_retention) that the dashboard "
        "endpoint's monthly_trends key also calls — the two pages can "
        "never disagree on this number. The most recent computable year "
        "always omits its own retention figure (no year+1 data exists "
        "yet to measure it against); there is no null placeholder for it."
    ),
    responses={
        200: RetentionResponseSerializer,
        403: TenantMissingResponseSerializer,
    },
)
"""Applied directly above RetentionReportView in core/views_reports.py."""


# ═══════════════════════════════════════════════════════════════════════
# core/views_dashboard.py
# ═══════════════════════════════════════════════════════════════════════

DASHBOARD_SCHEMA = extend_schema(
    tags=["Dashboard"],
    summary="Single aggregated payload for the دشبورد page",
    description=(
        "Everything the dashboard page needs in one request: campaign "
        "counts, active/inactive customer counts, current-month sales, "
        "top 4 products by revenue, yearly retention/churn (see the "
        "monthly_trends field's own description for an important naming "
        "caveat), RFM segment distribution, SMS balance, and the support "
        "unread-message badge count.\n\n"
        "Cached server-side per tenant for 60 seconds — a cache hit "
        "returns byte-for-byte the same shape as a fresh computation."
    ),
    responses={
        200: DashboardResponseSerializer,
        403: TenantMissingResponseSerializer,
    },
)
"""Applied directly above DashboardView in core/views_dashboard.py."""


# ═══════════════════════════════════════════════════════════════════════
# users/views.py — Auth + Profile
# ═══════════════════════════════════════════════════════════════════════

OTP_REQUEST_SCHEMA = extend_schema(
    tags=["Auth"],
    summary="Request an OTP code",
    description=(
        "No authentication required. Sends a 6-digit code to the given "
        "phone number via the configured SMS provider (sms.ir by "
        "default; see OTP_PROVIDER). Rate-limited two ways: a per-phone "
        "resend cooldown (independent of DRF's own throttle_scope= "
        "'otp_request' 5/hour limit) and a max-attempts counter enforced "
        "at verify time.\n\n"
        "debug_code is included in the response ONLY when the server is "
        "running with OTP_FAKE_MODE=True (local development only) — "
        "never rely on its presence."
    ),
    request=OTPRequestSerializer,
    responses={
        200: OTPRequestResponseSerializer,
        400: ErrorResponseSerializer,
        429: ErrorResponseSerializer,
    },
)
"""Applied directly above OTPRequestView in users/views.py."""


OTP_VERIFY_SCHEMA = extend_schema(
    tags=["Auth"],
    summary="Verify an OTP code and receive JWT tokens",
    description=(
        "No authentication required. On success, creates the CustomUser "
        "if one does not already exist for this phone number (this "
        "endpoint doubles as implicit registration for anyone who never "
        "calls POST /api/v1/auth/register/), which triggers the existing "
        "Tenant-creation signal. Codes are single-use and are burned on "
        "successful verification — a repeated call with the same code "
        "will fail as expired."
    ),
    request=OTPVerifySerializer,
    responses={
        200: OTPVerifyResponseSerializer,
        400: ErrorResponseSerializer,
    },
)
"""Applied directly above OTPVerifyView in users/views.py."""


REGISTER_SCHEMA = extend_schema(
    tags=["Auth"],
    summary="Explicit registration",
    description=(
        "No authentication required. Alternate signup path to OTP "
        "verify's implicit registration — only phone_number is actually "
        "required; first_name/last_name/shop_name are optional up front "
        "and can be filled in later via PATCH /api/v1/profile/. Fails "
        "with a validation error if the phone number is already "
        "registered."
    ),
    responses={
        201: RegisterResponseSerializer,
        400: ErrorResponseSerializer,
    },
)
"""Applied above RegisterView.create in users/views.py."""


LOGOUT_SCHEMA = extend_schema(
    tags=["Auth"],
    summary="Log out (blacklist a refresh token)",
    description=(
        "Requires a valid access token. Blacklists the given refresh "
        "token via Simple JWT's token-blacklist app — after this call, "
        "that refresh token can never be used again to obtain a new "
        "access token."
    ),
    request=LogoutSerializer,
    responses={
        204: OpenApiResponse(description="Logged out. No response body."),
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above LogoutView in users/views.py."""


PROFILE_SCHEMA = extend_schema_view(
    get=extend_schema(
        tags=["Profile"],
        summary="Get the authenticated user's own profile",
        responses={200: None, 401: ErrorResponseSerializer},
    ),
    patch=extend_schema(
        tags=["Profile"],
        summary="Partially update the authenticated user's own profile",
        description=(
            "Accepts JSON or multipart/form-data (multipart required if "
            "uploading profile_picture). phone_number and is_premium are "
            "read-only on this serializer — sending them is silently "
            "ignored, not rejected."
        ),
        responses={200: None, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer},
    ),
    put=extend_schema(exclude=True),
)
"""
Applied to ProfileView as a class decorator in users/views.py.

`responses={200: None, ...}` intentionally leaves the 200 response body
undocumented HERE and relies on drf-spectacular's normal introspection of
ProfileView.serializer_class (ProfileSerializer, a real ModelSerializer)
to fill it in automatically -- ProfileSerializer already fully and
correctly describes this endpoint's shape, so redeclaring it in
serializers_schema.py would just create a second, driftable copy of a
shape that already has an authoritative source. Passing None here (rather
than omitting the 200 key) explicitly signals "let auto-detection handle
this one," which most closely matches drf-spectacular's own documented
convention for "don't override, just document status codes I'm adding."

`put=extend_schema(exclude=True)` hides PUT from the schema entirely:
generics.RetrieveUpdateAPIView provides PUT (full update) by default, but
every actual and documented use of this endpoint is PATCH (partial) --
requiring every optional profile field on every request via PUT was never
the intended contract and would confuse the frontend team if left
visible and undocumented.
"""


ACCOUNT_STATUS_SCHEMA = extend_schema(
    tags=["Profile"],
    summary="Lightweight account/onboarding-state summary",
    description=(
        "For frontend gating decisions (e.g. whether to show an "
        "onboarding flow), not a full profile fetch. phone_verified is "
        "always true for any request that reaches this endpoint at all — "
        "there is no 'authenticated but unverified' state in this system, "
        "since a JWT is only ever issued after OTP verification or "
        "registration."
    ),
    responses={
        200: AccountStatusResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above AccountStatusView in users/views.py."""


# ═══════════════════════════════════════════════════════════════════════
# users/views_sms.py
# ═══════════════════════════════════════════════════════════════════════

SMS_PACKAGES_SCHEMA = extend_schema(
    tags=["SMS / Billing"],
    summary="Get SMS pricing configuration",
    description=(
        "Drives the purchase-slider UI. ALL price arithmetic (unit "
        "price × count, discount tier lookup, final price) happens "
        "entirely client-side from this config — the backend performs "
        "no price calculation anywhere in this flow. discount_tiers "
        "should be evaluated top-to-bottom (highest min_sms first); the "
        "first tier whose min_sms the chosen sms_count meets or exceeds "
        "is the applicable one."
    ),
    responses={
        200: SMSPackagesResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SMSPackagesView in users/views_sms.py."""


SMS_ACTIVATION_REQUEST_SCHEMA = extend_schema(
    tags=["SMS / Billing"],
    summary="Request SMS package activation (posts to support chat)",
    description=(
        "There is no payment gateway on this endpoint (contrast with "
        "POST /api/v1/sms/purchase-request/ in tickets/views.py, which "
        "additionally accepts and displays pricing figures — the two "
        "endpoints currently coexist; product has not yet decided to "
        "retire one). This endpoint posts a fixed Persian message "
        "stating only the requested sms_count into the tenant's support "
        "chat thread; a human support agent then handles the sale "
        "manually and an admin sets num_available_sms by hand once "
        "payment is confirmed."
    ),
    request=SMSActivationRequestBodySerializer,
    responses={
        201: SMSActivationRequestResponseSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SMSActivationRequestView in users/views_sms.py."""


SMS_BALANCE_SCHEMA = extend_schema(
    tags=["SMS / Billing"],
    summary="Get current SMS credit balance",
    description=(
        "num_available_sms is set manually in the Django admin by a "
        "human operator after payment is confirmed out of band — there "
        "is no automated top-up in this system yet."
    ),
    responses={
        200: SMSBalanceResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SMSBalanceView in users/views_sms.py."""


# ═══════════════════════════════════════════════════════════════════════
# tickets/views.py
# ═══════════════════════════════════════════════════════════════════════

CHAT_VIEW_SCHEMA = extend_schema_view(
    get=extend_schema(
        tags=["Support Chat"],
        summary="Get the tenant's full support chat thread",
        description=(
            "Returns every message in the tenant's own thread, oldest "
            "first. IMPORTANT SIDE EFFECT: calling this also resets the "
            "unread badge — tenant_last_seen_at is updated to now() as "
            "part of this GET. GET /api/v1/tickets/unread/ does NOT have "
            "this side effect; only this endpoint does."
        ),
        responses={
            200: ChatResponseSerializer,
            401: ErrorResponseSerializer,
        },
    ),
    post=extend_schema(
        tags=["Support Chat"],
        summary="Send a chat message as the tenant",
        request=SendMessageSerializer,
        responses={
            201: MessageSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    ),
)
"""
Applied to ChatView as a class decorator in tickets/views.py.

The 200 response uses ChatResponseSerializer (defined at the top of this
file), which composes core/serializers_schema.py's thread_id-only
ChatThreadResponseSerializer base together with the real
tickets.serializers.MessageSerializer for the `messages` field — see the
"Cross-app composed serializers" section near the top of this file for
why that composition lives here instead of in serializers_schema.py.
"""


SUPPORT_CHAT_VIEW_SCHEMA = extend_schema_view(
    get=extend_schema(
        tags=["Support Chat (Staff)"],
        summary="[Staff only] Get a specific tenant's chat thread",
        description="Requires request.user.is_staff. 404 if the tenant_id does not exist.",
        responses={
            200: ChatResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: SupportThreadNotFoundResponseSerializer,
        },
    ),
    post=extend_schema(
        tags=["Support Chat (Staff)"],
        summary="[Staff only] Reply to a specific tenant's thread",
        description="Requires request.user.is_staff. 404 if the tenant_id does not exist.",
        request=SendMessageSerializer,
        responses={
            201: MessageSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: SupportThreadNotFoundResponseSerializer,
        },
    ),
)
"""Applied to SupportChatView as a class decorator in tickets/views.py."""


UNREAD_COUNT_SCHEMA = extend_schema(
    tags=["Support Chat"],
    summary="Get the unread support-message count",
    description=(
        "For the sidebar notification badge shown on every page. Unlike "
        "GET /api/v1/tickets/chat/, polling this endpoint does NOT reset "
        "the badge — tenant_last_seen_at is left untouched."
    ),
    responses={
        200: UnreadCountResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above UnreadCountView in tickets/views.py."""


SMS_PURCHASE_REQUEST_SCHEMA = extend_schema(
    tags=["SMS / Billing"],
    summary="Request an SMS purchase (posts pricing detail to support chat)",
    description=(
        "Only sms_count is required. unit_price / discount_percent / "
        "discount_amount / final_price are optional and used ONLY to "
        "render a more detailed message for the support agent — the "
        "backend never recalculates, validates, or stores any of these "
        "figures for billing purposes; all pricing math already happened "
        "client-side using GET /api/v1/sms/packages/'s config.\n\n"
        "NOTE: this endpoint and POST /api/v1/sms/request-activation/ "
        "(users/views_sms.py) currently both exist and do the same job "
        "with a different payload shape — product has not yet decided to "
        "retire one. Document both accurately; do not treat one as "
        "deprecated unless told to."
    ),
    request=SmsPurchaseRequestSerializer,
    responses={
        201: MessageSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
    },
)
"""Applied directly above SmsPurchaseRequestView in tickets/views.py."""


# ═══════════════════════════════════════════════════════════════════════
# APPLICATION MAP
# ═══════════════════════════════════════════════════════════════════════
"""
Exact wiring — apply each decorator below to the exact class/method named,
in the file named. Nothing else in any of these files changes.

core/views.py
    from core.schema import CAMPAIGN_VIEWSET_SCHEMA, CAMPAIGN_TOGGLE_SCHEMA, CAMPAIGN_META_SCHEMA
    @CAMPAIGN_VIEWSET_SCHEMA
    class CampaignViewSet(viewsets.ModelViewSet): ...
        @CAMPAIGN_TOGGLE_SCHEMA
        @action(detail=True, methods=["patch"])
        def toggle(self, request, pk=None): ...
    @CAMPAIGN_META_SCHEMA
    class CampaignMetaView(APIView): ...

core/views_uploads.py
    from core.schema import (
        CUSTOMER_UPLOAD_SCHEMA, PRODUCT_UPLOAD_SCHEMA, COUPON_UPLOAD_SCHEMA,
        UPLOAD_JOB_STATUS_SCHEMA, SAMPLE_FILES_SCHEMA,
    )
    @CUSTOMER_UPLOAD_SCHEMA
    class CustomerUploadView(APIView): ...
    @PRODUCT_UPLOAD_SCHEMA
    class ProductUploadView(APIView): ...
    @COUPON_UPLOAD_SCHEMA
    class CouponUploadView(APIView): ...
    @UPLOAD_JOB_STATUS_SCHEMA
    class UploadJobStatusView(APIView): ...
    @SAMPLE_FILES_SCHEMA
    class SampleFilesView(APIView): ...

core/views_sync.py
    from core.schema import (
        SYNC_CONFIG_FETCH_SCHEMA, SYNC_USER_INGEST_SCHEMA,
        SYNC_PRODUCT_INGEST_SCHEMA, SYNC_REPORT_SCHEMA,
    )
    @SYNC_CONFIG_FETCH_SCHEMA
    class SyncConfigFetchView(BaseSyncAPIView): ...
    @SYNC_USER_INGEST_SCHEMA
    class UserSyncIngestView(BaseSyncAPIView): ...
    @SYNC_PRODUCT_INGEST_SCHEMA
    class ProductSyncIngestView(BaseSyncAPIView): ...
    @SYNC_REPORT_SCHEMA
    class SyncReportView(BaseSyncAPIView): ...

core/views_sync_conf.py
    from core.schema import (
        SYNC_CONFIG_STATUS_SCHEMA, SYNC_FIELD_MAPPING_GET_SCHEMA,
        SYNC_FIELD_MAPPING_PUT_SCHEMA, SYNC_API_KEY_GENERATE_SCHEMA,
    )
    @SYNC_CONFIG_STATUS_SCHEMA
    class SyncConfigStatusView(APIView): ...
    class SyncFieldMappingView(APIView):
        @SYNC_FIELD_MAPPING_GET_SCHEMA
        def get(self, request): ...
        @SYNC_FIELD_MAPPING_PUT_SCHEMA
        def put(self, request): ...
    @SYNC_API_KEY_GENERATE_SCHEMA
    class SyncApiKeyGenerateView(APIView): ...

core/views_reports.py
    from core.schema import (
        TRENDS_REPORT_SCHEMA, SALES_RANGE_REPORT_SCHEMA, SEGMENTS_REPORT_SCHEMA,
        ACTIVE_USERS_REPORT_SCHEMA, RETENTION_REPORT_SCHEMA,
    )
    @TRENDS_REPORT_SCHEMA
    class TrendsReportView(APIView): ...
    @SALES_RANGE_REPORT_SCHEMA
    class SalesRangeReportView(APIView): ...
    @SEGMENTS_REPORT_SCHEMA
    class SegmentsReportView(APIView): ...
    @ACTIVE_USERS_REPORT_SCHEMA
    class ActiveUsersReportView(APIView): ...
    @RETENTION_REPORT_SCHEMA
    class RetentionReportView(APIView): ...

core/views_dashboard.py
    from core.schema import DASHBOARD_SCHEMA
    @DASHBOARD_SCHEMA
    class DashboardView(APIView): ...

users/views.py
    from core.schema import (
        OTP_REQUEST_SCHEMA, OTP_VERIFY_SCHEMA, REGISTER_SCHEMA, LOGOUT_SCHEMA,
        PROFILE_SCHEMA, ACCOUNT_STATUS_SCHEMA,
    )
    @OTP_REQUEST_SCHEMA
    class OTPRequestView(APIView): ...
    @OTP_VERIFY_SCHEMA
    class OTPVerifyView(APIView): ...
    class RegisterView(generics.CreateAPIView):
        @REGISTER_SCHEMA
        def create(self, request, *args, **kwargs): ...
    @LOGOUT_SCHEMA
    class LogoutView(APIView): ...
    @PROFILE_SCHEMA
    class ProfileView(generics.RetrieveUpdateAPIView): ...
    @ACCOUNT_STATUS_SCHEMA
    class AccountStatusView(APIView): ...

users/views_sms.py
    from core.schema import SMS_PACKAGES_SCHEMA, SMS_ACTIVATION_REQUEST_SCHEMA, SMS_BALANCE_SCHEMA
    @SMS_PACKAGES_SCHEMA
    class SMSPackagesView(APIView): ...
    @SMS_ACTIVATION_REQUEST_SCHEMA
    class SMSActivationRequestView(APIView): ...
    @SMS_BALANCE_SCHEMA
    class SMSBalanceView(APIView): ...

tickets/views.py
    from core.schema import (
        CHAT_VIEW_SCHEMA, SUPPORT_CHAT_VIEW_SCHEMA, UNREAD_COUNT_SCHEMA,
        SMS_PURCHASE_REQUEST_SCHEMA,
    )
    @CHAT_VIEW_SCHEMA
    class ChatView(APIView): ...
    @SUPPORT_CHAT_VIEW_SCHEMA
    class SupportChatView(APIView): ...
    @UNREAD_COUNT_SCHEMA
    class UnreadCountView(APIView): ...
    @SMS_PURCHASE_REQUEST_SCHEMA
    class SmsPurchaseRequestView(APIView): ...
"""
