# core/exceptions.py

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
)
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import (
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("retano")


def custom_exception_handler(exc, context):
    """
    Overrides DRF's default exception handler.

    Every error response from the API has this consistent shape:

        {
            "error": true,
            "status_code": 400,
            "message": "Human-readable summary.",
            "details": { ... }  # field-level errors when applicable
        }

    This makes frontend error handling trivial — always check `error`
    and `message`, and optionally parse `details` for form validation.
    """

    # Let DRF handle known exceptions first — gives us a Response object.
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception (500-level) — log and return generic error.
        logger.exception(
            "Unhandled exception in view %s",
            context.get("view", "unknown"),
            exc_info=exc,
        )
        return Response(
            {
                "error": True,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An unexpected error occurred. Our team has been notified.",
                "details": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # --- Shape the response consistently ---

    error_data = {
        "error": True,
        "status_code": response.status_code,
        "message": _extract_message(exc, response),
        "details": _extract_details(exc, response),
    }

    response.data = error_data
    return response


def _extract_message(exc, response):
    """Return a clean top-level human-readable message."""
    if isinstance(exc, ValidationError):
        return "Validation failed. Check the details field for field-level errors."
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return "Authentication credentials were not provided or are invalid."
    if isinstance(exc, (PermissionDenied, DRFPermissionDenied)):
        return "You do not have permission to perform this action."
    if isinstance(exc, Http404):
        return "The requested resource was not found."
    # Generic DRF exception — try to get its detail string
    detail = getattr(exc, "detail", None)
    if detail is not None:
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:
            first = detail[0]
            return str(first) if not isinstance(first, dict) else str(exc)
    return str(exc)


def _extract_details(exc, response):
    """Return structured field-level error details when available."""
    if isinstance(exc, ValidationError):
        return _flatten_validation_errors(exc.detail)
    return {}


def _flatten_validation_errors(detail):
    """
    Recursively flatten DRF's nested validation error structure into a flat
    dict of { field_name: [list of error strings] }.
    """
    if isinstance(detail, list):
        return {"non_field_errors": [str(e) for e in detail]}
    if isinstance(detail, dict):
        result = {}
        for key, value in detail.items():
            if isinstance(value, list):
                result[key] = [str(e) for e in value]
            elif isinstance(value, dict):
                # Nested serializer errors — prefix the key
                nested = _flatten_validation_errors(value)
                for nested_key, nested_val in nested.items():
                    result[f"{key}.{nested_key}"] = nested_val
            else:
                result[key] = [str(value)]
        return result
    return {"detail": [str(detail)]}


# ─────────────────────────────────────────────────────────────────────────────
# Custom application exceptions
# ─────────────────────────────────────────────────────────────────────────────


class BusinessLogicError(APIException):
    """
    Raise this for domain-level violations that are not validation errors.
    Example: trying to upload coupons when available coupons still exist.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "A business rule was violated."
    default_code = "business_logic_error"


class TenantPermissionError(APIException):
    """Raise this when a tenant tries to access another tenant's resource."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have access to this resource."
    default_code = "tenant_permission_denied"


class OTPError(APIException):
    """Raise this for OTP validation failures."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The OTP is invalid or has expired."
    default_code = "otp_error"
