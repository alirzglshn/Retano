# core/services/sync_pipeline.py
"""
Core ingest logic for the automated ETL synchronization system.

This is deliberately separate from core/services/upload_pipeline.py (the
manual Excel flow). They share the same downstream tables and the same
flush_*_staging() functions, but nothing else — the sync pipeline never
touches CustomerFileUpload/ProductFileUpload, never reads an .xlsx, and
uses per-row coercion with per-row rejection rather than the Excel
pipeline's whole-file validate/reject.

────────────────────────────────────────────────────────────────────────
BUSINESS LOGIC RECAP (per explicit product decisions)
────────────────────────────────────────────────────────────────────────
For every incoming row (already schema-validated by the ETL and type-
coerced by this module):

  1. Look up the permanent table (UsersUnNormalizedData /
     ProductsUnNormalizedData) by the row's internal ID.

  2. NOT FOUND  → this is a new record. Insert it into the STAGING table
     only. The permanent table is left untouched — it is only ever
     populated by flush_customers_staging()/flush_products_staging(),
     which the tenant runs manually. This mirrors the existing Excel
     pipeline's contract exactly.

  3. FOUND      → this is an update to a record that has already been
     flushed through once before. We:
       a. Take the existing permanent row as the base.
       b. Overlay only the fields present/changed in the incoming row
          (merge semantics — the incoming row is a full snapshot per the
          ETL's design, so in practice "overlay" means "replace with the
          incoming value for every field the sync system tracks", but we
          implement it as an explicit per-field overlay rather than a
          blind replace so that fields NOT covered by this tenant's sync
          mapping at all are never clobbered).
       c. DELETE the row from the permanent table.
       d. INSERT the merged row into the STAGING table.
     This guarantees the next manual flush_*_staging() call picks up the
     update exactly as if it were a brand new row — flush_*_staging()
     already does an ON CONFLICT upsert into the permanent table, so
     re-inserting into staging and re-flushing produces the correct
     final state.

  4. Row-level coercion failure on any field OTHER than
     first_product_attribute/second_product_attribute → the ROW is
     rejected (skipped, counted, logged) — NOT the whole batch.

  5. Row-level coercion failure (or the ETL itself reporting the column
     didn't exist) on first_product_attribute/second_product_attribute
     → that field is stored as NULL; the row is otherwise processed
     normally.

  6. Schema-level failures (missing table; missing column other than the
     two attribute fields) are NOT handled here — they are caught by the
     ETL's own pre-flight check BEFORE any data endpoint is ever called,
     and reported via POST /api/v1/sync/report/. This module only ever
     sees rows that already passed that pre-flight check, so it does not
     re-implement schema validation.
────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from django.db import connection, transaction

from core.models import (
    ProductsUnNormalizedDataStaging,
    UsersUnNormalizedDataStaging,
)
from core.services.global_identity import resolve_identity
from core.sync.coercion import CoercionError, coerce_field
from core.sync.field_registry import get_field_specs

Entity = Literal["user", "product"]


@dataclass
class RowRejection:
    index: int
    internal_id: str | None
    field_name: str
    reason: str


@dataclass
class IngestResult:
    rows_received: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rejections: list[RowRejection] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rows_received": self.rows_received,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "rejections": [
                {
                    "index": r.index,
                    "internal_id": r.internal_id,
                    "field": r.field_name,
                    "reason": r.reason,
                }
                for r in self.rejections
            ],
        }


def _coerce_row(
    entity: Entity, raw_row: dict, row_index: int, result: IngestResult
) -> dict | None:
    """
    Coerces every field in a single raw row per the field registry.
    Returns the cleaned dict, or None if the row must be rejected
    (a non-nullable field failed coercion or was missing entirely).
    """
    specs = get_field_specs(entity)
    cleaned: dict[str, Any] = {}
    internal_id_field = (
        "internal_user_id" if entity == "user" else "internal_product_id"
    )
    internal_id_value = raw_row.get(internal_id_field)

    for spec in specs:
        raw_value = raw_row.get(spec.field_name)
        try:
            cleaned[spec.field_name] = coerce_field(
                spec.field_name, raw_value, spec.coercion, spec.max_length
            )
        except CoercionError as exc:
            if spec.nullable_on_schema_miss:
                # first_product_attribute / second_product_attribute:
                # a bad or missing value degrades to NULL, row proceeds.
                cleaned[spec.field_name] = None
                continue
            # Any other field: reject the whole row, not the batch.
            result.rejections.append(
                RowRejection(
                    index=row_index,
                    internal_id=str(internal_id_value) if internal_id_value else None,
                    field_name=exc.field_name,
                    reason=exc.reason,
                )
            )
            return None

    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# USERS entity
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_permanent_user(
    tenant_id: int, internal_user_id: str, internal_order_id: str
) -> dict | None:
    """
    users_unnormalized_data is a flat per-ORDER-LINE table: one client-side
    order = one row. A single user has many rows (one per order). The
    stable identity for "is this an update or a new record" is therefore
    the COMPOSITE (internal_user_id, internal_order_id) — internal_user_id
    alone would match an arbitrary unrelated past order for the same user.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT internal_user_id, user_id, first_name, last_name, gender,
                   phone_number, internal_order_id, order_id, order_date,
                   internal_product_id, product_id, then_product_price,
                   quantity, subtotal, column_mapping
            FROM users_unnormalized_data
            WHERE tenant_id = %s
              AND internal_user_id = %s
              AND internal_order_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [tenant_id, internal_user_id, internal_order_id],
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [
            "internal_user_id",
            "user_id",
            "first_name",
            "last_name",
            "gender",
            "phone_number",
            "internal_order_id",
            "order_id",
            "order_date",
            "internal_product_id",
            "product_id",
            "then_product_price",
            "quantity",
            "subtotal",
            "column_mapping",
        ]
        return dict(zip(columns, row))


def _delete_permanent_user(
    tenant_id: int, internal_user_id: str, internal_order_id: str
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM users_unnormalized_data
            WHERE tenant_id = %s
              AND internal_user_id = %s
              AND internal_order_id = %s
            """,
            [tenant_id, internal_user_id, internal_order_id],
        )


def _resolve_user_and_order_ids(
    tenant_id: int, internal_user_id: str, internal_order_id: str
) -> tuple[int, int]:
    """
    Uses the same persistent identity registries as file uploads. The mapping
    survives staging/permanent-flat-table cleanup and is protected by unique
    constraints at the database layer.
    """
    return (
        resolve_identity("user", tenant_id, internal_user_id),
        resolve_identity("order", tenant_id, internal_order_id),
    )


def ingest_user_rows(tenant, raw_rows: list[dict]) -> IngestResult:
    result = IngestResult(rows_received=len(raw_rows))
    staging_objects: list[UsersUnNormalizedDataStaging] = []

    with transaction.atomic():
        for idx, raw_row in enumerate(raw_rows):
            cleaned = _coerce_row("user", raw_row, idx, result)
            if cleaned is None:
                result.rows_rejected += 1
                continue

            internal_user_id = cleaned["internal_user_id"]
            internal_order_id = cleaned["internal_order_id"]

            if not internal_user_id or not internal_order_id:
                result.rejections.append(
                    RowRejection(
                        index=idx,
                        internal_id=internal_user_id,
                        field_name="internal_user_id/internal_order_id",
                        reason="both internal_user_id and internal_order_id are required",
                    )
                )
                result.rows_rejected += 1
                continue

            existing = _fetch_permanent_user(
                tenant.id, internal_user_id, internal_order_id
            )

            if existing is not None:
                # UPDATE case: same user, same order → merge incoming
                # fields onto the existing permanent row, delete it,
                # restage the merged result.
                merged = {**existing, **cleaned}
                user_id = existing["user_id"]
                order_id = existing["order_id"]
                _delete_permanent_user(tenant.id, internal_user_id, internal_order_id)
            else:
                # New order line — either a brand new user, or an existing
                # user placing an order we haven't seen before. Either way
                # this is an INSERT, never a merge.
                merged = cleaned
                user_id, order_id = _resolve_user_and_order_ids(
                    tenant.id, internal_user_id, internal_order_id
                )

            staging_objects.append(
                UsersUnNormalizedDataStaging(
                    tenant=tenant,
                    internal_user_id=internal_user_id,
                    user_id=user_id,
                    first_name=merged.get("first_name") or "",
                    last_name=merged.get("last_name"),
                    gender=merged.get("gender"),
                    phone_number=merged.get("phone_number"),
                    internal_order_id=internal_order_id,
                    order_id=order_id,
                    order_date=merged.get("order_date"),
                    internal_product_id=merged.get("internal_product_id") or "null",
                    product_id=None,
                    then_product_price=merged.get("then_product_price") or 0,
                    quantity=merged.get("quantity") or 0,
                    subtotal=None,
                    column_mapping={"source": "automated_sync"},
                )
            )
            result.rows_accepted += 1

        if staging_objects:
            UsersUnNormalizedDataStaging.objects.bulk_create(
                staging_objects, batch_size=1000
            )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTS entity
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_permanent_product(tenant_id: int, internal_product_id: str) -> dict | None:
    """
    NOTE: product_category is aliased to `category` here — that is the
    field_registry.py / coercion-layer name (matching what the ETL/tenant
    mapping UI calls it), whereas the permanent table's actual column is
    `product_category` (matching ProductExcelMapper's own field naming).
    Without this alias, `{**existing, **cleaned}` in ingest_product_rows
    would end up with BOTH "product_category" (old, from this fetch) and
    "category" (new, from coercion) as separate dict keys that never
    collide — silently discarding every incoming category update. Aliasing
    here keeps merge semantics correct: one canonical key, one value, the
    incoming one always wins on conflict.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT internal_product_id, product_id, product_name,
                   product_category AS category,
                   current_product_price, product_link, first_product_attribute,
                   second_product_attribute, column_mapping
            FROM products_unnormalized_data
            WHERE tenant_id = %s AND internal_product_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [tenant_id, internal_product_id],
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [
            "internal_product_id",
            "product_id",
            "product_name",
            "category",
            "current_product_price",
            "product_link",
            "first_product_attribute",
            "second_product_attribute",
            "column_mapping",
        ]
        return dict(zip(columns, row))


def _delete_permanent_product(tenant_id: int, internal_product_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM products_unnormalized_data
            WHERE tenant_id = %s AND internal_product_id = %s
            """,
            [tenant_id, internal_product_id],
        )


def _resolve_product_id(tenant_id: int, internal_product_id: str) -> int:
    return resolve_identity("product", tenant_id, internal_product_id)


def ingest_product_rows(tenant, raw_rows: list[dict]) -> IngestResult:
    result = IngestResult(rows_received=len(raw_rows))
    staging_objects: list[ProductsUnNormalizedDataStaging] = []

    with transaction.atomic():
        for idx, raw_row in enumerate(raw_rows):
            cleaned = _coerce_row("product", raw_row, idx, result)
            if cleaned is None:
                result.rows_rejected += 1
                continue

            internal_product_id = cleaned["internal_product_id"]
            if not internal_product_id:
                result.rejections.append(
                    RowRejection(
                        index=idx,
                        internal_id=None,
                        field_name="internal_product_id",
                        reason="internal_product_id is required",
                    )
                )
                result.rows_rejected += 1
                continue

            existing = _fetch_permanent_product(tenant.id, internal_product_id)

            if existing is not None:
                merged = {**existing, **cleaned}
                product_id = existing["product_id"]
                _delete_permanent_product(tenant.id, internal_product_id)
            else:
                merged = cleaned
                product_id = _resolve_product_id(tenant.id, internal_product_id)

            staging_objects.append(
                ProductsUnNormalizedDataStaging(
                    tenant=tenant,
                    internal_product_id=internal_product_id,
                    product_id=product_id,
                    product_name=merged.get("product_name") or "",
                    product_category=merged.get("category") or "",
                    current_product_price=merged.get("current_product_price") or 0,
                    product_link=merged.get("product_link") or "",
                    first_product_attribute=merged.get("first_product_attribute"),
                    second_product_attribute=merged.get("second_product_attribute"),
                    column_mapping={"source": "automated_sync"},
                )
            )
            result.rows_accepted += 1

        if staging_objects:
            ProductsUnNormalizedDataStaging.objects.bulk_create(
                staging_objects, batch_size=1000
            )

    return result
