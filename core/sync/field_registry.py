# core/sync/field_registry.py
"""
Single source of truth for which fields the sync system collects, per
entity ("user" / "product"), and how each one behaves.

Both the API-Conf backend (validating that تولید API can be pressed) and
the sync ingest pipeline (coercing incoming values) import from HERE and
nowhere else. If you add, rename, or remove a synced field, this is the
only file that needs to change — SyncFieldMapping deliberately has no
hardcoded choices list, and the ingest pipeline has no hardcoded field
list either.

Each FieldSpec describes:
    entity              — "user" or "product"
    field_name          — canonical name, matches the corresponding
                           column on UsersUnNormalizedData(Staging) /
                           ProductsUnNormalizedData(Staging)
    coercion            — one of "text", "int", "decimal", "date"
                           (see core/sync/coercion.py for the coercers)
    required_for_config — if False, تولید API does not block on this field
                           being left blank in the mapping UI. Currently
                           only the two product attribute fields are
                           optional in this sense... actually, per
                           explicit product decision, they ARE mandatory
                           to configure (the tenant must still declare a
                           table/column for them) — what's optional is
                           whether the actual sync run tolerates that
                           table/column not existing in the client's DB.
                           See `nullable_on_schema_miss` below for that.
                           required_for_config stays True for every field
                           for this reason; kept as an explicit flag
                           (rather than assuming "always True") so a
                           future genuinely-optional field doesn't require
                           restructuring this registry.
    nullable_on_schema_miss
                        — if True, a missing/misnamed COLUMN for this
                          field does not fail the sync run; the field is
                          simply stored as NULL for every affected row.
                          A missing TABLE is always fatal regardless of
                          this flag — this only ever applies to columns.
                          True for exactly two fields per explicit product
                          decision: first_product_attribute and
                          second_product_attribute.
    max_length          — for text fields, truncation length matching the
                           target model column (mirrors the truncation
                           already done in core/services/upload_pipeline.py)
"""

from dataclasses import dataclass
from typing import Literal

Entity = Literal["user", "product"]
Coercion = Literal["text", "int", "decimal", "date"]


@dataclass(frozen=True)
class FieldSpec:
    entity: Entity
    field_name: str
    coercion: Coercion
    required_for_config: bool = True
    nullable_on_schema_miss: bool = False
    max_length: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# USER fields → UsersUnNormalizedData / UsersUnNormalizedDataStaging
# ─────────────────────────────────────────────────────────────────────────────

USER_FIELDS: list[FieldSpec] = [
    FieldSpec("user", "internal_user_id", "text", max_length=None),
    FieldSpec("user", "first_name", "text", max_length=200),
    FieldSpec("user", "last_name", "text", max_length=None),
    FieldSpec("user", "gender", "text", max_length=None),
    FieldSpec("user", "phone_number", "text", max_length=20),
    FieldSpec("user", "internal_order_id", "text", max_length=None),
    FieldSpec("user", "order_date", "date"),
    FieldSpec("user", "internal_product_id", "text", max_length=None),
    FieldSpec("user", "quantity", "int"),
    FieldSpec("user", "then_product_price", "decimal"),
]

# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT fields → ProductsUnNormalizedData / ProductsUnNormalizedDataStaging
# ─────────────────────────────────────────────────────────────────────────────

PRODUCT_FIELDS: list[FieldSpec] = [
    FieldSpec("product", "internal_product_id", "text", max_length=None),
    FieldSpec("product", "product_name", "text", max_length=255),
    FieldSpec("product", "category", "text", max_length=100),
    FieldSpec("product", "current_product_price", "decimal"),
    FieldSpec("product", "product_link", "text", max_length=2000),
    FieldSpec(
        "product",
        "first_product_attribute",
        "text",
        max_length=None,
        nullable_on_schema_miss=True,
    ),
    FieldSpec(
        "product",
        "second_product_attribute",
        "text",
        max_length=None,
        nullable_on_schema_miss=True,
    ),
]

FIELD_REGISTRY: dict[Entity, list[FieldSpec]] = {
    "user": USER_FIELDS,
    "product": PRODUCT_FIELDS,
}


def get_field_specs(entity: Entity) -> list[FieldSpec]:
    try:
        return FIELD_REGISTRY[entity]
    except KeyError:
        raise ValueError(f"Unknown sync entity: {entity!r}")


def get_field_spec(entity: Entity, field_name: str) -> FieldSpec | None:
    for spec in get_field_specs(entity):
        if spec.field_name == field_name:
            return spec
    return None


def all_field_names(entity: Entity) -> set[str]:
    return {spec.field_name for spec in get_field_specs(entity)}


def nullable_field_names(entity: Entity) -> set[str]:
    """Field names for which a missing COLUMN degrades to NULL instead of
    failing the whole run. (Missing TABLES are always fatal — this set is
    only ever consulted for column-level schema checks.)"""
    return {
        spec.field_name
        for spec in get_field_specs(entity)
        if spec.nullable_on_schema_miss
    }
