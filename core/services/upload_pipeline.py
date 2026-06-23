# core/services/upload_pipeline.py
"""
Upload pipeline functions extracted from CampaignExcelFilesView.

These three functions are the authoritative implementation of the
customers, products, and coupons ingestion pipelines. They are called
identically from:
    - The legacy SSR CampaignExcelFilesView (during transition)
    - The DRF upload APIViews (Phase 6)

Nothing in the pipeline logic is changed. The only difference is the
return value: instead of writing Django messages, each function returns
a result dict that the caller uses to build its response.

Return shape (both success and error):
    {
        "status":          "success" | "error",
        "error_type":      None | "mapping_error" | "file_error"
                                  | "pipeline_error" | "duplicate_coupon_error",
        "message":         str,
        "rows_processed":  int,
        "rows_saved":      int,
    }
"""

import pandas as pd
from django.db import connection, transaction

from core.models import (
    Coupon,
    CustomerFileUpload,
    ProductFileUpload,
    CouponFileUpload,
    UsersUnNormalizedDataStaging,
    ProductsUnNormalizedDataStaging,
)
from core.utils.excel_mapper import (
    CustomerExcelMapper,
    ProductExcelMapper,
    CouponExcelMapper,
)


# ─────────────────────────────────────────────────────────────────────────────
# Customers pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_customers(tenant, customers_file, customers_mapping: dict) -> dict:
    """
    Full customers ingestion pipeline.

    Args:
        tenant:             core.models.Tenant instance
        customers_file:     Django UploadedFile (from request.FILES or form)
        customers_mapping:  dict mapping field names → zero-based column indices
                            e.g. {"internal_id": 0, "first_name": 1, ...}
    """
    is_valid, error_msg = CustomerExcelMapper.validate_mapping_integrity(
        customers_mapping
    )
    if not is_valid:
        return {
            "status": "error",
            "error_type": "mapping_error",
            "message": f"خطا در نگاشت ستون‌های فایل مشتریان: {error_msg}",
            "rows_processed": 0,
            "rows_saved": 0,
        }

    with transaction.atomic():
        customer_upload = CustomerFileUpload.objects.create(
            tenant=tenant,
            customers_file=customers_file,
            customers_mapping=customers_mapping,
        )

    try:
        customers_df, actual_mapping = CustomerExcelMapper.validate_and_map_file(
            customer_upload.customers_file.path, customers_mapping
        )
    except ValueError as e:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": f"خطا در پردازش فایل مشتریان: {str(e)}",
            "rows_processed": 0,
            "rows_saved": 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": f"خطای غیرمنتظره در فایل مشتریان: {str(e)}",
            "rows_processed": 0,
            "rows_saved": 0,
        }

    rows_processed = len(customers_df)

    customers_df["internal_id"] = customers_df["internal_id"].astype(str)
    customers_df["internal_order_id"] = customers_df["internal_order_id"].astype(str)
    customers_df["internal_product_id"] = customers_df["internal_product_id"].astype(str)

    # ── Allocate globally-unique user_ids ─────────────────────────────────
    unique_internal_ids = (
        customers_df[["internal_id"]].drop_duplicates()["internal_id"].tolist()
    )
    user_id_mapping: dict = {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT internal_user_id, user_id
            FROM users_unnormalized_data
            WHERE tenant_id = %s
              AND internal_user_id = ANY(%s)
            """,
            [tenant.id, unique_internal_ids],
        )
        for internal_id, uid in cursor.fetchall():
            user_id_mapping[internal_id] = uid

    new_internal_ids = [
        iid for iid in unique_internal_ids if iid not in user_id_mapping
    ]
    if new_internal_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT nextval('global_user_id_seq') FROM generate_series(1, %s)",
                [len(new_internal_ids)],
            )
            for internal_id, (new_id,) in zip(new_internal_ids, cursor.fetchall()):
                user_id_mapping[internal_id] = new_id

    # ── Allocate globally-unique order_ids ────────────────────────────────
    unique_internal_order_ids = (
        customers_df[["internal_order_id"]]
        .drop_duplicates()["internal_order_id"]
        .tolist()
    )
    order_id_mapping: dict = {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT internal_order_id, order_id
            FROM users_unnormalized_data
            WHERE tenant_id = %s
              AND internal_order_id = ANY(%s)
            """,
            [tenant.id, unique_internal_order_ids],
        )
        for internal_order_id, oid in cursor.fetchall():
            order_id_mapping[internal_order_id] = oid

    new_internal_order_ids = [
        iid for iid in unique_internal_order_ids if iid not in order_id_mapping
    ]
    if new_internal_order_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT nextval('global_order_id_seq') FROM generate_series(1, %s)",
                [len(new_internal_order_ids)],
            )
            for internal_order_id, (new_id,) in zip(
                new_internal_order_ids, cursor.fetchall()
            ):
                order_id_mapping[internal_order_id] = new_id

    # ── Build staging objects ─────────────────────────────────────────────
    staging_objects = []
    for _, row in customers_df.iterrows():
        internal_id = str(row.get("internal_id", ""))
        internal_order_id = str(row.get("internal_order_id", ""))
        internal_product_id = str(row.get("internal_product_id", ""))

        if not internal_id or not internal_order_id or not internal_product_id:
            continue

        try:
            then_price = (
                float(row["then_product_price"])
                if pd.notna(row.get("then_product_price"))
                else 0.0
            )
        except (ValueError, TypeError):
            then_price = 0.0

        try:
            qty = (
                int(row["quantity"])
                if pd.notna(row.get("quantity"))
                else 0
            )
        except (ValueError, TypeError):
            qty = 0

        staging_objects.append(
            UsersUnNormalizedDataStaging(
                tenant=tenant,
                internal_user_id=internal_id,
                user_id=user_id_mapping[internal_id],
                first_name=str(row.get("first_name", ""))[:200],
                last_name=str(row.get("last_name", "")) or None,
                gender=str(row.get("gender", "")) or None,
                phone_number=(
                    str(row["phone_number"])[:20]
                    if pd.notna(row.get("phone_number"))
                    else None
                ),
                internal_order_id=internal_order_id,
                order_id=order_id_mapping[internal_order_id],
                order_date=(
                    row["order_date"] if pd.notna(row.get("order_date")) else None
                ),
                internal_product_id=internal_product_id,
                product_id=None,
                then_product_price=then_price,
                quantity=qty,
                subtotal=None,
                column_mapping={
                    "customers_file_mapping": actual_mapping,
                    "customers_index_mapping": customers_mapping,
                    "uploaded_at": str(customer_upload.created_at),
                },
            )
        )

    if not staging_objects:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": "هیچ رکورد معتبری در فایل مشتریان یافت نشد.",
            "rows_processed": rows_processed,
            "rows_saved": 0,
        }

    try:
        UsersUnNormalizedDataStaging.objects.bulk_create(
            staging_objects, batch_size=1000
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '600000';")
            cursor.execute("SELECT flush_customers_staging(%s)", [tenant.id])
            rows_saved = cursor.fetchone()[0] or 0

        return {
            "status": "success",
            "error_type": None,
            "message": f"{rows_saved} رکورد مشتریان با موفقیت در دیتابیس ذخیره شد.",
            "rows_processed": rows_processed,
            "rows_saved": rows_saved,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "pipeline_error",
            "message": f"خطای غیرمنتظره در ذخیره‌سازی مشتریان: {str(e)}",
            "rows_processed": rows_processed,
            "rows_saved": 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Products pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_products(tenant, products_file, products_mapping: dict) -> dict:
    is_valid, error_msg = ProductExcelMapper.validate_mapping_integrity(
        products_mapping
    )
    if not is_valid:
        return {
            "status": "error",
            "error_type": "mapping_error",
            "message": f"خطا در نگاشت ستون‌های فایل محصولات: {error_msg}",
            "rows_processed": 0,
            "rows_saved": 0,
        }

    with transaction.atomic():
        product_upload = ProductFileUpload.objects.create(
            tenant=tenant,
            products_file=products_file,
            products_mapping=products_mapping,
        )

    try:
        products_df, actual_mapping = ProductExcelMapper.validate_and_map_file(
            product_upload.products_file.path, products_mapping
        )
    except ValueError as e:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": f"خطا در پردازش فایل محصولات: {str(e)}",
            "rows_processed": 0,
            "rows_saved": 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": f"خطای غیرمنتظره در فایل محصولات: {str(e)}",
            "rows_processed": 0,
            "rows_saved": 0,
        }

    rows_processed = len(products_df)

    products_df["internal_product_id"] = (
        products_df["internal_product_id"].astype(str)
    )

    # ── Allocate globally-unique product_ids ──────────────────────────────
    unique_internal_product_ids = (
        products_df[["internal_product_id"]]
        .drop_duplicates()["internal_product_id"]
        .tolist()
    )
    product_id_mapping: dict = {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT internal_product_id, product_id
            FROM products_unnormalized_data
            WHERE tenant_id = %s
              AND internal_product_id = ANY(%s)
            """,
            [tenant.id, unique_internal_product_ids],
        )
        for internal_product_id, pid in cursor.fetchall():
            product_id_mapping[internal_product_id] = pid

    new_internal_product_ids = [
        iid
        for iid in unique_internal_product_ids
        if iid not in product_id_mapping
    ]
    if new_internal_product_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT nextval('global_product_id_seq') FROM generate_series(1, %s)",
                [len(new_internal_product_ids)],
            )
            for internal_product_id, (new_id,) in zip(
                new_internal_product_ids, cursor.fetchall()
            ):
                product_id_mapping[internal_product_id] = new_id

    def _attr_value(row, field_name):
        val = row.get(field_name)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        val = str(val).strip()
        return val if val else None

    staging_objects = []
    for _, row in products_df.iterrows():
        internal_product_id = str(row.get("internal_product_id", ""))
        if not internal_product_id:
            continue

        try:
            price = (
                float(row["current_product_price"])
                if pd.notna(row.get("current_product_price"))
                else 0.0
            )
        except (ValueError, TypeError):
            price = 0.0

        staging_objects.append(
            ProductsUnNormalizedDataStaging(
                tenant=tenant,
                internal_product_id=internal_product_id,
                product_id=product_id_mapping[internal_product_id],
                product_name=str(row.get("product_name", ""))[:255],
                product_category=str(row.get("category", ""))[:100],
                current_product_price=price,
                product_link=(
                    str(row["product_link"])[:2000]
                    if pd.notna(row.get("product_link"))
                    else ""
                ),
                first_product_attribute=_attr_value(row, "first_product_attribute"),
                second_product_attribute=_attr_value(row, "second_product_attribute"),
                column_mapping={
                    "products_file_mapping": actual_mapping,
                    "products_index_mapping": products_mapping,
                    "uploaded_at": str(product_upload.created_at),
                },
            )
        )

    if not staging_objects:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": "هیچ رکورد معتبری در فایل محصولات یافت نشد.",
            "rows_processed": rows_processed,
            "rows_saved": 0,
        }

    try:
        ProductsUnNormalizedDataStaging.objects.bulk_create(
            staging_objects, batch_size=1000
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '600000';")
            cursor.execute("SELECT flush_products_staging(%s)", [tenant.id])
            rows_saved = cursor.fetchone()[0] or 0

        return {
            "status": "success",
            "error_type": None,
            "message": f"{rows_saved} رکورد محصولات با موفقیت در دیتابیس ذخیره شد.",
            "rows_processed": rows_processed,
            "rows_saved": rows_saved,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "pipeline_error",
            "message": f"خطای غیرمنتظره در ذخیره‌سازی محصولات: {str(e)}",
            "rows_processed": rows_processed,
            "rows_saved": 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Coupons pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_coupons(tenant, coupons_file, coupons_mapping: dict) -> dict:
    # Duplicate coupon guard — unchanged from SSR
    existing_available = Coupon.objects.filter(
        tenant=tenant, status="available"
    ).exists()
    if existing_available:
        return {
            "status": "error",
            "error_type": "duplicate_coupon_error",
            "message": (
                "شما هنوز کوپن‌های استفاده نشده دارید. "
                "تا زمانی که همه کوپن‌ها استفاده نشده‌اند، "
                "امکان آپلود فایل کوپن جدید وجود ندارد."
            ),
            "rows_processed": 0,
            "rows_saved": 0,
        }

    with transaction.atomic():
        coupon_upload = CouponFileUpload.objects.create(
            tenant=tenant,
            coupons_file=coupons_file,
            coupons_mapping=coupons_mapping,
        )

    try:
        coupons_df, _ = CouponExcelMapper.validate_and_map_file(
            coupon_upload.coupons_file.path, coupons_mapping
        )
    except Exception as e:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": f"خطا در پردازش فایل کوپن: {str(e)}",
            "rows_processed": 0,
            "rows_saved": 0,
        }

    rows_processed = len(coupons_df)

    coupon_objects = []
    for _, row in coupons_df.iterrows():
        coupon_code = str(row.get("coupon_code", "")).strip()
        if not coupon_code:
            continue
        try:
            discount_val = float(row.get("discount_percentage", 0))
        except (ValueError, TypeError):
            discount_val = 0
        coupon_objects.append(
            Coupon(
                tenant=tenant,
                coupon_code=coupon_code,
                discount_percentage=discount_val,
                status="available",
            )
        )

    if not coupon_objects:
        return {
            "status": "error",
            "error_type": "file_error",
            "message": "هیچ کوپن معتبری در فایل یافت نشد.",
            "rows_processed": rows_processed,
            "rows_saved": 0,
        }

    try:
        Coupon.objects.bulk_create(
            coupon_objects, batch_size=1000, ignore_conflicts=True
        )
        rows_saved = len(coupon_objects)
        return {
            "status": "success",
            "error_type": None,
            "message": f"{rows_saved} کوپن با موفقیت در دیتابیس ذخیره شد.",
            "rows_processed": rows_processed,
            "rows_saved": rows_saved,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "pipeline_error",
            "message": f"خطای غیرمنتظره در ذخیره‌سازی کوپن‌ها: {str(e)}",
            "rows_processed": rows_processed,
            "rows_saved": 0,
        }