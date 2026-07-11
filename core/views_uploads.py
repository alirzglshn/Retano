# core/views_uploads.py
"""
Async upload endpoints.

Every endpoint here does the same thing structurally:
    1. Validate the multipart mapping fields (identical rules to before —
       required, non-negative integers; same field name lists).
    2. Validate the uploaded file is present and has a plausible extension.
    3. Stream the file to Supabase Storage (not local disk-then-worker-reads).
    4. Create an UploadJob row (status=queued).
    5. Enqueue the corresponding Celery task with the job id.
    6. Return 202 Accepted immediately with the job id and a status URL.

The client is expected to poll GET /api/v1/uploads/jobs/{id}/ for progress
(processed_rows / total_rows / status) until status is success/partial/failed.

All Persian-language error messages, the same error_type taxonomy, and the
same required-field lists as the old synchronous views are preserved.
"""

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from core.schema import CUSTOMER_UPLOAD_SCHEMA, PRODUCT_UPLOAD_SCHEMA, COUPON_UPLOAD_SCHEMA, UPLOAD_JOB_STATUS_SCHEMA, SAMPLE_FILES_SCHEMA
from core.models import Coupon
from core.models import UploadJob
from core.services.storage import upload_fileobj_to_storage
from core.tasks.uploads import (
    process_customers_upload,
    process_products_upload,
    process_coupons_upload,
)

ALLOWED_EXTENSIONS = (".xlsx", ".xls")


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


def _validate_file(uploaded_file, missing_message: str):
    """
    Returns an error Response if the file is missing or has an implausible
    extension, else None. Extension checking is a cheap first filter —
    it is not a substitute for actually attempting to parse the file (which
    the Celery task still does, and still fails gracefully via error_type
    'file_error' if the content is not valid Excel).
    """
    if not uploaded_file:
        return Response(
            {
                "status": "error",
                "error_type": "file_error",
                "message": missing_message,
                "rows_processed": 0,
                "rows_saved": 0,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    name = uploaded_file.name or ""
    if not name.lower().endswith(ALLOWED_EXTENSIONS):
        return Response(
            {
                "status": "error",
                "error_type": "file_error",
                "message": "فرمت فایل باید Excel (.xlsx یا .xls) باشد.",
                "rows_processed": 0,
                "rows_saved": 0,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _build_mapping(request_data, mapping_fields: list[str], prefix: str):
    """Returns (mapping_dict, missing_fields_list) — same semantics as before."""
    mapping = {}
    missing_fields = []
    for form_field in mapping_fields:
        mapper_key = form_field[len(prefix):]
        val = _int_field(request_data, form_field)
        if val is None:
            missing_fields.append(form_field)
        else:
            mapping[mapper_key] = val
    return mapping, missing_fields


def _accepted_response(job: UploadJob):
    return Response(
        {
            "status": "accepted",
            "job_id": str(job.id),
            "status_url": f"/api/v1/uploads/jobs/{job.id}/",
            "message": "فایل دریافت شد و پردازش آن آغاز شده است.",
        },
        status=status.HTTP_202_ACCEPTED,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Customers upload
# ─────────────────────────────────────────────────────────────────────────────


@CUSTOMER_UPLOAD_SCHEMA 
class CustomerUploadView(APIView):
    """
    POST /api/v1/uploads/customers/

    Same multipart fields as before (customers_file, customers_internal_id,
    customers_first_name, ... customers_gender). Returns 202 with a job_id
    instead of blocking until the import finishes.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
        uploaded_file = request.FILES.get("customers_file")
        file_error = _validate_file(uploaded_file, "فایل مشتریان ارسال نشده است.")
        if file_error:
            return file_error

        mapping, missing_fields = _build_mapping(
            request.data, self._MAPPING_FIELDS, "customers_"
        )
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

        tenant = _tenant(request)
        storage_key = upload_fileobj_to_storage(
            uploaded_file, tenant.id, "customers", uploaded_file.name
        )
        job = UploadJob.objects.create(
            tenant=tenant,
            upload_type=UploadJob.UploadType.CUSTOMERS,
            storage_key=storage_key,
            original_filename=uploaded_file.name,
            mapping=mapping,
        )
        process_customers_upload.delay(str(job.id))
        return _accepted_response(job)


# ─────────────────────────────────────────────────────────────────────────────
# Products upload
# ─────────────────────────────────────────────────────────────────────────────


@PRODUCT_UPLOAD_SCHEMA
class ProductUploadView(APIView):
    """
    POST /api/v1/uploads/products/
    Same multipart fields as before. Returns 202 with a job_id.
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
        file_error = _validate_file(uploaded_file, "فایل محصولات ارسال نشده است.")
        if file_error:
            return file_error

        mapping, missing_fields = _build_mapping(
            request.data, self._MAPPING_FIELDS, "products_"
        )
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

        tenant = _tenant(request)
        storage_key = upload_fileobj_to_storage(
            uploaded_file, tenant.id, "products", uploaded_file.name
        )
        job = UploadJob.objects.create(
            tenant=tenant,
            upload_type=UploadJob.UploadType.PRODUCTS,
            storage_key=storage_key,
            original_filename=uploaded_file.name,
            mapping=mapping,
        )
        process_products_upload.delay(str(job.id))
        return _accepted_response(job)


# ─────────────────────────────────────────────────────────────────────────────
# Coupons upload
# ─────────────────────────────────────────────────────────────────────────────

@COUPON_UPLOAD_SCHEMA
class CouponUploadView(APIView):
    """
    POST /api/v1/uploads/coupons/
    Same multipart fields as before. Returns 202 with a job_id.

    The duplicate-active-coupon guard runs synchronously here, exactly as it
    did in the old pipeline -- a tenant with unused coupons still gets an
    immediate 400 with error_type "duplicate_coupon_error" before the file
    is even uploaded to storage. This check is deliberately kept out of the
    Celery task: it is cheap (single EXISTS query), and users should learn
    about it immediately rather than after a round trip through the queue.
    The task also re-checks the same guard defensively (belt-and-suspenders
    against a race between two near-simultaneous uploads), but the primary,
    user-facing rejection path is here.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    _MAPPING_FIELDS = [
        "coupons_coupon_code",
        "coupons_discount_percentage",
    ]

    def post(self, request):
        tenant = _tenant(request)

        if Coupon.objects.filter(tenant=tenant, status="available").exists():
            return Response(
                {
                    "status": "error",
                    "error_type": "duplicate_coupon_error",
                    "message": (
                        "شما هنوز کوپن\u200cهای استفاده نشده دارید. "
                        "تا زمانی که همه کوپن\u200cها استفاده نشده\u200cاند، "
                        "امکان آپلود فایل کوپن جدید وجود ندارد."
                    ),
                    "rows_processed": 0,
                    "rows_saved": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES.get("coupons_file")
        file_error = _validate_file(uploaded_file, "فایل کوپن\u200cها ارسال نشده است.")
        if file_error:
            return file_error

        mapping, missing_fields = _build_mapping(
            request.data, self._MAPPING_FIELDS, "coupons_"
        )
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

        storage_key = upload_fileobj_to_storage(
            uploaded_file, tenant.id, "coupons", uploaded_file.name
        )
        job = UploadJob.objects.create(
            tenant=tenant,
            upload_type=UploadJob.UploadType.COUPONS,
            storage_key=storage_key,
            original_filename=uploaded_file.name,
            mapping=mapping,
        )
        process_coupons_upload.delay(str(job.id))
        return _accepted_response(job)


# ─────────────────────────────────────────────────────────────────────────────
# Job status polling endpoint
# ─────────────────────────────────────────────────────────────────────────────

@UPLOAD_JOB_STATUS_SCHEMA
class UploadJobStatusView(APIView):
    """
    GET /api/v1/uploads/jobs/{id}/

    Returns the current state of an upload job, including real row-based
    progress (processed_rows / total_rows / progress_percentage) so the
    frontend can render a live progress bar without the request itself
    ever waiting on the import.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = UploadJob.objects.get(id=job_id, tenant=_tenant(request))
        except UploadJob.DoesNotExist:
            return Response(
                {"status": "error", "message": "Job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(job.to_status_dict(), status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Sample files — unchanged from the synchronous version
# ─────────────────────────────────────────────────────────────────────────────

@SAMPLE_FILES_SCHEMA 
class SampleFilesView(APIView):
    """
    GET /api/v1/uploads/sample-files/

    Returns absolute URLs for the three sample Excel files so the React
    frontend can offer download links without hardcoding domain names.
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
