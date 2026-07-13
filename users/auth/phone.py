# users/auth/phone.py
"""Iranian mobile number normalization helpers for OTP authentication."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

_NON_DIGIT_RE = re.compile(r"[^\d+]")
_CANONICAL_RE = re.compile(r"^\+989\d{9}$")


def normalize_iranian_phone(raw: str) -> str:
    """
    Normalize common Iranian mobile formats to E.164: +989XXXXXXXXX.

    Accepted examples:
        09121234567, 9121234567, 00989121234567,
        +98 912 123 4567, +989121234567
    """
    if not raw or not isinstance(raw, str):
        raise ValidationError("Phone number is required.")

    cleaned = _NON_DIGIT_RE.sub("", raw.strip())

    if cleaned.startswith("+98"):
        national = cleaned[3:]
    elif cleaned.startswith("0098"):
        national = cleaned[4:]
    elif cleaned.startswith("98") and len(cleaned) == 12:
        national = cleaned[2:]
    elif cleaned.startswith("0"):
        national = cleaned[1:]
    else:
        national = cleaned

    if len(national) != 10 or not national.startswith("9"):
        raise ValidationError(
            "Phone number must be a valid Iranian mobile number "
            "(for example 09121234567 or +989121234567)."
        )

    canonical = f"+98{national}"
    if not _CANONICAL_RE.match(canonical):
        raise ValidationError("Invalid Iranian mobile number.")
    return canonical
