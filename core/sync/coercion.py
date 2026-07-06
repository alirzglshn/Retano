# core/sync/coercion.py
"""
Per-field type coercion for the sync ingest pipeline.

Design intent (per project decision):
    - The ETL never coerces types. It ships raw driver-native values as
      JSON (numbers as numbers, strings as strings, dates as ISO-8601
      strings, None for SQL NULL). Different client DB engines/drivers
      return slightly different Python types for "the same" column
      (e.g. a MySQL DECIMAL might arrive as a JSON number or a numeric
      string depending on driver config) — this layer absorbs all of
      that, so the ETL stays a dumb, engine-agnostic transport.
    - Every failure is EXPLICIT. Unlike the legacy Excel pipeline
      (core/services/upload_pipeline.py), which silently defaults bad
      values to 0.0, this layer raises CoercionError with the field name,
      the raw offending value, and a human reason. The caller decides
      per-field whether that's fatal for the row (see sync_pipeline.py):
      for the two attribute fields specifically, a coercion failure is
      treated the same as a schema miss (→ None); for every other field,
      it means the ROW is rejected, not the whole batch.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from core.utils.date_parser import FlexibleDateParser


class CoercionError(Exception):
    def __init__(self, field_name: str, raw_value: Any, reason: str):
        self.field_name = field_name
        self.raw_value = raw_value
        self.reason = reason
        super().__init__(f"{field_name}: {reason} (got {raw_value!r})")


def coerce_text(field_name: str, raw_value: Any, max_length: int | None) -> str | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if text == "":
        return None
    if max_length is not None:
        text = text[:max_length]
    return text


def coerce_int(field_name: str, raw_value: Any) -> int:
    if raw_value is None or raw_value == "":
        raise CoercionError(field_name, raw_value, "value is required and cannot be null/empty")
    try:
        # Accept int, float-that-is-whole, or numeric string.
        if isinstance(raw_value, bool):
            raise ValueError("boolean is not a valid integer source")
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
        return int(raw_value)
    except (ValueError, TypeError) as exc:
        raise CoercionError(field_name, raw_value, f"could not parse as integer: {exc}")


def coerce_decimal(field_name: str, raw_value: Any) -> Decimal:
    if raw_value is None or raw_value == "":
        raise CoercionError(field_name, raw_value, "value is required and cannot be null/empty")
    try:
        if isinstance(raw_value, str):
            raw_value = raw_value.strip().replace(",", "")
        return Decimal(str(raw_value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CoercionError(field_name, raw_value, f"could not parse as decimal: {exc}")


def coerce_date(field_name: str, raw_value: Any) -> date:
    if raw_value is None or raw_value == "":
        raise CoercionError(field_name, raw_value, "value is required and cannot be null/empty")
    try:
        parsed = FlexibleDateParser.parse_date(raw_value)
    except ValueError as exc:
        raise CoercionError(field_name, raw_value, f"could not parse as date: {exc}")
    if parsed is None:
        raise CoercionError(field_name, raw_value, "could not parse as date")
    # FlexibleDateParser.parse_date returns "YYYY-MM-DD" string; convert to date.
    from datetime import datetime

    return datetime.strptime(parsed, "%Y-%m-%d").date()


_COERCERS = {
    "int": lambda field_name, raw_value, max_length: coerce_int(field_name, raw_value),
    "decimal": lambda field_name, raw_value, max_length: coerce_decimal(field_name, raw_value),
    "date": lambda field_name, raw_value, max_length: coerce_date(field_name, raw_value),
    "text": coerce_text,
}


def coerce_field(field_name: str, raw_value: Any, coercion: str, max_length: int | None) -> Any:
    """
    Single entry point used by the ingest pipeline. Raises CoercionError
    on failure — never silently substitutes a default value.
    """
    coercer = _COERCERS.get(coercion)
    if coercer is None:
        raise CoercionError(field_name, raw_value, f"unknown coercion type: {coercion!r}")
    return coercer(field_name, raw_value, max_length)
