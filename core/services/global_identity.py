"""Database-backed, permanent global identity resolution."""

from django.db import connection

IDENTITY_TABLES = {
    "user": ("global_user_identity", "internal_user_id", "user_id"),
    "order": ("global_order_identity", "internal_order_id", "order_id"),
    "product": ("global_product_identity", "internal_product_id", "product_id"),
}


def resolve_identity(kind: str, tenant_id: int, internal_id: str) -> int:
    """Return one stable mapping, creating it atomically when absent."""
    table, internal_column, id_column = IDENTITY_TABLES[kind]
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {id_column} FROM {table} "
            f"WHERE tenant_id = %s AND {internal_column} = %s",
            [tenant_id, internal_id],
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            f"INSERT INTO {table} (tenant_id, {internal_column}) "
            "VALUES (%s, %s) "
            f"ON CONFLICT (tenant_id, {internal_column}) DO UPDATE "
            f"SET {internal_column} = EXCLUDED.{internal_column} "
            f"RETURNING {id_column}",
            [tenant_id, internal_id],
        )
        return cursor.fetchone()[0]


def resolve_identities(
    kind: str, tenant_id: int, internal_ids: list[str]
) -> dict[str, int]:
    """Resolve a whole upload's distinct identities with two set-based queries."""
    if not internal_ids:
        return {}
    table, internal_column, id_column = IDENTITY_TABLES[kind]
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {table} (tenant_id, {internal_column}) "
            f"SELECT %s, value FROM unnest(%s::text[]) AS value "
            f"ON CONFLICT (tenant_id, {internal_column}) DO NOTHING",
            [tenant_id, internal_ids],
        )
        cursor.execute(
            f"SELECT {internal_column}, {id_column} FROM {table} "
            f"WHERE tenant_id = %s AND {internal_column} = ANY(%s)",
            [tenant_id, internal_ids],
        )
        return dict(cursor.fetchall())
