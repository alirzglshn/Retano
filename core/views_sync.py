# core/views_sync.py
"""
ETL-facing endpoints — the "thin client, smart API" surface consumed by
the Docker sync container running on the b2c tenant's infrastructure.

Authenticated via TenantSyncAPIKeyAuthentication (Bearer <tenant-api-key>),
NOT JWT. See core/sync/authentication.py.

Endpoints:
    GET  /api/v1/sync/config/           — fetch mapping + settings
    POST /api/v1/sync/data/users/       — ingest a batch of user rows
    POST /api/v1/sync/data/products/    — ingest a batch of product rows
    POST /api/v1/sync/report/           — report run outcome / pre-flight failure
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.schema import SYNC_CONFIG_FETCH_SCHEMA, SYNC_USER_INGEST_SCHEMA, SYNC_PRODUCT_INGEST_SCHEMA, SYNC_REPORT_SCHEMA
from core.models import SyncFieldMapping, SyncRun
from core.serializers_sync import (
    SyncConfigFetchSerializer,
    SyncDataRowsSerializer,
    SyncReportSerializer,
)
from core.services.sync_pipeline import ingest_product_rows, ingest_user_rows
from core.sync.authentication import TenantSyncAPIKeyAuthentication
from core.sync.field_registry import get_field_specs, nullable_field_names


class HasValidSyncAPIKey(BasePermission):
    """
    request.auth is the SyncConfig instance set by
    TenantSyncAPIKeyAuthentication. Its mere presence (authentication
    succeeded) is sufficient — there is no additional per-action
    permission distinction for the ETL surface.
    """

    def has_permission(self, request, view):
        return request.auth is not None


class BaseSyncAPIView(APIView):
    authentication_classes = [TenantSyncAPIKeyAuthentication]
    permission_classes = [HasValidSyncAPIKey]

    @property
    def sync_config(self):
        return self.request.auth

    @property
    def tenant(self):
        return self.request.auth.tenant

@SYNC_CONFIG_FETCH_SCHEMA
class SyncConfigFetchView(BaseSyncAPIView):
    """
    GET /api/v1/sync/config/

    Step 2 of the ETL's cycle (per the agreed architecture): fetch
    configuration at the START of every run, never bake it into the
    container. Always reflects the tenant's current منطق نگاشط ستون —
    edits made in the تنظیم API page take effect on the very next sync
    cycle with zero client-side redeployment.
    """

    def get(self, request):
        tenant = self.tenant
        mappings = SyncFieldMapping.objects.filter(tenant=tenant)
        by_key = {(m.entity, m.field_name): m for m in mappings}

        mapping_payload: dict[str, dict[str, dict[str, str]]] = {"user": {}, "product": {}}
        for entity in ("user", "product"):
            for spec in get_field_specs(entity):
                m = by_key.get((entity, spec.field_name))
                if m is None or not m.is_filled:
                    # Should not normally happen — تولید API blocks key
                    # generation until everything is filled — but if the
                    # tenant later blanks out a field via a re-save, the
                    # authoritative response still reflects reality rather
                    # than silently omitting it.
                    mapping_payload[entity][spec.field_name] = {"table": None, "column": None}
                else:
                    mapping_payload[entity][spec.field_name] = {
                        "table": m.client_table,
                        "column": m.client_column,
                    }

        payload = SyncConfigFetchSerializer(
            {
                "batch_size": self.sync_config.batch_size,
                "mapping": mapping_payload,
                "nullable_fields": {
                    "user": sorted(nullable_field_names("user")),
                    "product": sorted(nullable_field_names("product")),
                },
            }
        ).data
        return Response(payload, status=status.HTTP_200_OK)


@SYNC_USER_INGEST_SCHEMA
class UserSyncIngestView(BaseSyncAPIView):
    """
    POST /api/v1/sync/data/users/

    Body: {"rows": [{...}, ...]}  — see SyncDataRowsSerializer.

    IMPORTANT: this endpoint assumes the ETL has already completed its
    own pre-flight schema check (table/column existence against the
    tenant's actual database) before calling it. This endpoint performs
    per-FIELD, per-ROW type coercion (see core/sync/coercion.py) but does
    NOT perform schema validation — it has no visibility into the
    tenant's database at all and never will, by design.
    """

    def post(self, request):
        serializer = SyncDataRowsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["rows"]

        result = ingest_user_rows(self.tenant, rows)
        return Response(result.as_dict(), status=status.HTTP_200_OK)

@SYNC_PRODUCT_INGEST_SCHEMA
class ProductSyncIngestView(BaseSyncAPIView):
    """POST /api/v1/sync/data/products/ — see UserSyncIngestView docstring."""

    def post(self, request):
        serializer = SyncDataRowsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["rows"]

        result = ingest_product_rows(self.tenant, rows)
        return Response(result.as_dict(), status=status.HTTP_200_OK)


@SYNC_REPORT_SCHEMA
class SyncReportView(BaseSyncAPIView):
    """
    POST /api/v1/sync/report/

    The ETL calls this exactly once per cycle, in one of two situations:

    1. Pre-flight schema check failed — data endpoints were NEVER called.
       status="failed", failure_stage="schema_table"|"schema_column",
       failure_detail=<precise missing table/column name, for logs only>.

    2. The cycle ran to completion (successfully or with some rows
       rejected) — status="success"|"partial", plus the rows_* counters
       the ETL already received back from the data endpoints' own
       responses. This call exists so a SyncRun audit record exists even
       when nothing went wrong, giving the تنظیم API page a real "last
       synced at" timestamp to display.
    """

    def post(self, request):
        serializer = SyncReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        SyncRun.objects.create(
            tenant=self.tenant,
            status=data["status"],
            failure_stage=data.get("failure_stage"),
            failure_detail=data.get("failure_detail", ""),
            users_rows_received=data.get("users_rows_received", 0),
            users_rows_accepted=data.get("users_rows_accepted", 0),
            users_rows_rejected=data.get("users_rows_rejected", 0),
            products_rows_received=data.get("products_rows_received", 0),
            products_rows_accepted=data.get("products_rows_accepted", 0),
            products_rows_rejected=data.get("products_rows_rejected", 0),
            finished_at=timezone.now(),
        )

        return Response({"message": "Report recorded."}, status=status.HTTP_201_CREATED)
