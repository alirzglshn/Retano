# core/views_uploads.py

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.upload_pipeline import (
    process_customers,
    process_products,
    process_coupons,
)
from core.utils.excel_mapper import (
    CustomerExcelMapper,
    ProductExcelMapper,
    CouponExcelMapper,
)


def _tenant(request):
    """Extract the Tenant from the authenticated user. Never fails in production
    because the post_save signal guarantees every CustomUser has a Tenant."""
    return request.user.tenant


def _int_field(data, key) -> int | None:
    """Parse a multipart string field as a non-negative integer, or None."""
    val = data.get(key)
    if val is None or val == "":
        return None
    try:
        result = int(val)
        return result if result >= 0 else None
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Customers upload
# ─────────────────────────────────────────────────────────────────────────────


class CustomerUploadView(APIView):
    """
    POST /api/v1/uploads/customers/

    multipart/form-data fields:
        customers_file                   — required, .xlsx
        customers_internal_id            — required, int >= 0
        customers_first_name             — required, int >= 0
        customers_last_name              — required, int >= 0
        customers_internal_order_id      — required, int >= 0
        customers_order_date             — required, int >= 0
        customers_quantity               — required, int >= 0
        customers_then_product_price     — required, int >= 0
        customers_phone_number           — required, int >= 0
        customers_internal_product_id    — required, int >= 0
        customers_gender                 — required, int >= 0

    Field names mirror ColumnMappingForm._CUSTOMERS_FORM_FIELDS exactly so
    the frontend can reuse its existing field set without renaming.

    Response (success):
        {"status": "success", "message": "...", "rows_processed": N, "rows_saved": M}

    Response (error):
        {"status": "error", "error_type": "...", "message": "...",
         "rows_processed": N, "rows_saved": 0}
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    # Field name → mapper key (strips "customers_" prefix)
    _MAPPING_FIELDS = [
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
    ]

    def post(self, request):
        # ── File validation ───────────────────────────────────────────────
        uploaded_file = request.FILES.get("customers_file")
        if not uploaded_file:
            return Response(
                {
                    "status": "error",
                    "error_type": "file_error",
                    "message": "فایل مشتریان ارسال نشده است.",
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Build mapping dict from POST fields ───────────────────────────
        mapping = {}
        missing_fields = []
        prefix = "customers_"

        for form_field in self._MAPPING_FIELDS:
            mapper_key = form_field[len(prefix):]
            val = _int_field(request.data, form_field)
            if val is None:
                missing_fields.append(form_field)
            else:
                mapping[mapper_key] = val

        if missing_fields:
            return Response(
                {
                    "status": "error",
                    "error_type": "mapping_error",
                    "message": (
                        f"فیلدهای نگاشت ستون الزامی هستند و باید عدد صحیح غیرمنفی باشند: "
                        f"{', '.join(missing_fields)}"
                    ),
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Run pipeline ──────────────────────────────────────────────────
        result = process_customers(
            tenant=_tenant(request),
            customers_file=uploaded_file,
            customers_mapping=mapping,
        )

        http_status = (
            status.HTTP_200_OK
            if result["status"] == "success"
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)


# ─────────────────────────────────────────────────────────────────────────────
# Products upload
# ─────────────────────────────────────────────────────────────────────────────


class ProductUploadView(APIView):
    """
    POST /api/v1/uploads/products/

    multipart/form-data fields:
        products_file                        — required, .xlsx
        products_internal_product_id         — required, int >= 0
        products_product_name                — required, int >= 0
        products_category                    — required, int >= 0
        products_current_product_price       — required, int >= 0
        products_first_product_attribute     — required, int >= 0
        products_second_product_attribute    — required, int >= 0
        products_product_link                — required, int >= 0
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    _MAPPING_FIELDS = [
        "products_internal_product_id",
        "products_product_name",
        "products_category",
        "products_current_product_price",
        "products_first_product_attribute",
        "products_second_product_attribute",
        "products_product_link",
    ]

    def post(self, request):
        uploaded_file = request.FILES.get("products_file")
        if not uploaded_file:
            return Response(
                {
                    "status": "error",
                    "error_type": "file_error",
                    "message": "فایل محصولات ارسال نشده است.",
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mapping = {}
        missing_fields = []
        prefix = "products_"

        for form_field in self._MAPPING_FIELDS:
            mapper_key = form_field[len(prefix):]
            val = _int_field(request.data, form_field)
            if val is None:
                missing_fields.append(form_field)
            else:
                mapping[mapper_key] = val

        if missing_fields:
            return Response(
                {
                    "status": "error",
                    "error_type": "mapping_error",
                    "message": (
                        f"فیلدهای نگاشت ستون الزامی هستند و باید عدد صحیح غیرمنفی باشند: "
                        f"{', '.join(missing_fields)}"
                    ),
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = process_products(
            tenant=_tenant(request),
            products_file=uploaded_file,
            products_mapping=mapping,
        )

        http_status = (
            status.HTTP_200_OK
            if result["status"] == "success"
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)


# ─────────────────────────────────────────────────────────────────────────────
# Coupons upload
# ─────────────────────────────────────────────────────────────────────────────


class CouponUploadView(APIView):
    """
    POST /api/v1/uploads/coupons/

    multipart/form-data fields:
        coupons_file                  — required, .xlsx
        coupons_coupon_code           — required, int >= 0
        coupons_discount_percentage   — required, int >= 0
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    _MAPPING_FIELDS = [
        "coupons_coupon_code",
        "coupons_discount_percentage",
    ]

    def post(self, request):
        uploaded_file = request.FILES.get("coupons_file")
        if not uploaded_file:
            return Response(
                {
                    "status": "error",
                    "error_type": "file_error",
                    "message": "فایل کوپن‌ها ارسال نشده است.",
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mapping = {}
        missing_fields = []
        prefix = "coupons_"

        for form_field in self._MAPPING_FIELDS:
            mapper_key = form_field[len(prefix):]
            val = _int_field(request.data, form_field)
            if val is None:
                missing_fields.append(form_field)
            else:
                mapping[mapper_key] = val

        if missing_fields:
            return Response(
                {
                    "status": "error",
                    "error_type": "mapping_error",
                    "message": (
                        f"فیلدهای نگاشت ستون الزامی هستند و باید عدد صحیح غیرمنفی باشند: "
                        f"{', '.join(missing_fields)}"
                    ),
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = process_coupons(
            tenant=_tenant(request),
            coupons_file=uploaded_file,
            coupons_mapping=mapping,
        )

        http_status = (
            status.HTTP_200_OK
            if result["status"] == "success"
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)


# ─────────────────────────────────────────────────────────────────────────────
# Sample files
# ─────────────────────────────────────────────────────────────────────────────


class SampleFilesView(APIView):
    """
    GET /api/v1/uploads/sample-files/

    Returns absolute URLs for the three sample Excel files so the React
    frontend can offer download links without hardcoding domain names.

    Response:
        {
            "customers": "https://api.retano360.com/static/files/format.xlsx",
            "products":  "https://api.retano360.com/static/files/format_products.xlsx",
            "coupons":   "https://api.retano360.com/static/files/coupons_excel.xlsx"
        }
    """

    permission_classes = [permissions.IsAuthenticated]

    _STATIC_FILES = {
        "customers": "files/format.xlsx",
        "products": "files/format_products.xlsx",
        "coupons": "files/coupons_excel.xlsx",
    }

    def get(self, request):
        base = settings.STATIC_URL  # "/static/"
        data = {
            key: request.build_absolute_uri(f"{base}{path}")
            for key, path in self._STATIC_FILES.items()
        }
        return Response(data, status=status.HTTP_200_OK)