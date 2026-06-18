# core/utils/excel_mapper.py

import pandas as pd
from .date_parser import FlexibleDateParser


# ─────────────────────────────────────────────────────────────────────────────
# CustomerExcelMapper  — unchanged from migration 0044
# ─────────────────────────────────────────────────────────────────────────────

class CustomerExcelMapper:
    """
    Maps customers Excel columns by INDEX position to the fields expected by
    the customers pipeline (UsersUnNormalizedData).

    Required fields:
        internal_id, first_name, last_name, internal_order_id, order_date,
        quantity, then_product_price, phone_number, internal_product_id, gender
    """

    REQUIRED_FIELDS = [
        "internal_id",
        "first_name",
        "last_name",
        "internal_order_id",
        "order_date",
        "quantity",
        "then_product_price",
        "phone_number",
        "internal_product_id",
        "gender",
    ]

    FIELDS_DESCRIPTION = {
        "internal_id":          "شناسه یکتای مشتری (مثلاً کد ملی یا شماره موبایل) - Required",
        "first_name":           "نام مشتری - Required",
        "last_name":            "نام خانوادگی مشتری - Required",
        "internal_order_id":    "شناسه یکتای سفارش - Required",
        "order_date":           (
            "تاریخ ثبت سفارش (هر فرمتی قابل قبول است: "
            "2024-08-12, 12/08/2024, Jan 12 2024, etc.) - Required"
        ),
        "quantity":             "تعداد محصول سفارش داده شده - Required",
        "then_product_price":   "قیمت محصول در زمان خرید (ثابت و تغییر نمی‌کند) - Required",
        "phone_number":         "شماره تلفن مشتری - Required",
        "internal_product_id":  "شناسه یکتای محصول (ربط به فایل محصولات) - Required",
        "gender":               "جنسیت مشتری (آقایان/بانوان) - Required",
    }

    INSTRUCTIONS = {
        "file_type":       "Customers File",
        "required_fields": len(REQUIRED_FIELDS),
        "fields_list":     REQUIRED_FIELDS,
        "note": (
            "شماره ایندکس ستون‌ها از ۰ شروع می‌شود. "
            "مثال: ستون اول = 0، ستون دوم = 1، ستون سوم = 2"
        ),
    }

    @classmethod
    def validate_mapping_integrity(cls, mapping: dict):
        if not mapping:
            return False, "Customers column mapping is required and cannot be empty."
        missing = set(cls.REQUIRED_FIELDS) - set(mapping.keys())
        if missing:
            return False, f"Missing customers fields in mapping: {missing}"
        indices = list(mapping.values())
        if len(indices) != len(set(indices)):
            return False, "Duplicate column indices found in customers mapping."
        if any(idx < 0 for idx in indices):
            return False, "Column indices cannot be negative."
        return True, "Mapping is valid"

    @classmethod
    def validate_and_map_file(cls, file_path: str, column_mapping: dict):
        is_valid, error_msg = cls.validate_mapping_integrity(column_mapping)
        if not is_valid:
            raise ValueError(error_msg)

        df = pd.read_excel(file_path)
        df = df.fillna("")

        max_index_needed = max(column_mapping.values())
        if len(df.columns) <= max_index_needed:
            raise ValueError(
                f"Customers file must have at least {max_index_needed + 1} columns. "
                f"Found {len(df.columns)} columns."
            )

        actual_column_mapping = {}
        mapped_data = {}

        for field_name, col_idx in column_mapping.items():
            if field_name not in cls.REQUIRED_FIELDS:
                continue
            actual_column_mapping[field_name] = df.columns[col_idx]
            if field_name == "order_date":
                mapped_data[field_name] = FlexibleDateParser.parse_series_to_dates(
                    df[df.columns[col_idx]]
                )
            else:
                mapped_data[field_name] = df[df.columns[col_idx]]

        missing = set(cls.REQUIRED_FIELDS) - set(mapped_data.keys())
        if missing:
            raise ValueError(f"Missing required fields after mapping: {missing}")

        mapped_df = pd.DataFrame(mapped_data)

        if mapped_df["order_date"].isna().any():
            failed = mapped_df[mapped_df["order_date"].isna()].index.tolist()
            print(f"Warning: Failed to parse dates for rows: {failed}")

        return mapped_df, actual_column_mapping

    @classmethod
    def get_sample_mapping(cls):
        return {
            "internal_id":         0,
            "first_name":          1,
            "last_name":           2,
            "internal_order_id":   3,
            "order_date":          4,
            "quantity":            5,
            "then_product_price":  6,
            "phone_number":        7,
            "internal_product_id": 8,
            "gender":              9,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ProductExcelMapper
# hair_tag / skin_tag removed.
# first_product_attribute / second_product_attribute added.
# Empty cells → NULL (no normalisation whatsoever).
# ─────────────────────────────────────────────────────────────────────────────

class ProductExcelMapper:
    """
    Maps products Excel columns by INDEX position to the fields expected by
    the products pipeline (ProductsUnNormalizedData).

    Required fields:
        internal_product_id, product_name, category, current_product_price,
        first_product_attribute, second_product_attribute, product_link

    first_product_attribute and second_product_attribute are stored as-is —
    no normalisation, no transformation.  Empty cells become NULL.
    """

    REQUIRED_FIELDS = [
        "internal_product_id",
        "product_name",
        "category",
        "current_product_price",
        "first_product_attribute",
        "second_product_attribute",
        "product_link",
    ]

    FIELDS_DESCRIPTION = {
        "internal_product_id":      "شناسه یکتای محصول - Required",
        "product_name":             "نام محصول - Required",
        "category":                 "دسته‌بندی محصول - Required",
        "current_product_price":    "قیمت فعلی محصول (برای آنالیتیکس استفاده می‌شود) - Required",
        "first_product_attribute":  "ویژگی اول محصول (در صورت خالی بودن، NULL ذخیره می‌شود) - Required",
        "second_product_attribute": "ویژگی دوم محصول (در صورت خالی بودن، NULL ذخیره می‌شود) - Required",
        "product_link":             "لینک محصول - Required",
    }

    INSTRUCTIONS = {
        "file_type":       "Products File",
        "required_fields": len(REQUIRED_FIELDS),
        "fields_list":     REQUIRED_FIELDS,
        "note": (
            "شماره ایندکس ستون‌ها از ۰ شروع می‌شود. "
            "مثال: ستون اول = 0، ستون دوم = 1، ستون سوم = 2"
        ),
    }

    @classmethod
    def validate_mapping_integrity(cls, mapping: dict):
        if not mapping:
            return False, "Products column mapping is required and cannot be empty."
        missing = set(cls.REQUIRED_FIELDS) - set(mapping.keys())
        if missing:
            return False, f"Missing products fields in mapping: {missing}"
        indices = list(mapping.values())
        if len(indices) != len(set(indices)):
            return False, "Duplicate column indices found in products mapping."
        if any(idx < 0 for idx in indices):
            return False, "Column indices cannot be negative."
        return True, "Mapping is valid"

    @classmethod
    def validate_and_map_file(cls, file_path: str, column_mapping: dict):
        is_valid, error_msg = cls.validate_mapping_integrity(column_mapping)
        if not is_valid:
            raise ValueError(error_msg)

        df = pd.read_excel(file_path)
        # Do NOT fillna("") globally here — we need to detect empty attribute
        # cells and store them as NULL rather than empty string.
        # We fillna("") only for non-attribute fields below.

        max_index_needed = max(column_mapping.values())
        if len(df.columns) <= max_index_needed:
            raise ValueError(
                f"Products file must have at least {max_index_needed + 1} columns. "
                f"Found {len(df.columns)} columns."
            )

        actual_column_mapping = {}
        mapped_data = {}

        # Attribute fields that should remain NaN (not coerced to empty string)
        # so the view can detect emptiness and store NULL.
        ATTRIBUTE_FIELDS = {"first_product_attribute", "second_product_attribute"}

        for field_name, col_idx in column_mapping.items():
            if field_name not in cls.REQUIRED_FIELDS:
                continue
            actual_column_mapping[field_name] = df.columns[col_idx]
            if field_name in ATTRIBUTE_FIELDS:
                # Keep NaN as-is — view will convert to None (NULL in Postgres)
                mapped_data[field_name] = df[df.columns[col_idx]]
            else:
                mapped_data[field_name] = df[df.columns[col_idx]].fillna("")

        missing = set(cls.REQUIRED_FIELDS) - set(mapped_data.keys())
        if missing:
            raise ValueError(f"Missing required fields after mapping: {missing}")

        return pd.DataFrame(mapped_data), actual_column_mapping

    @classmethod
    def get_sample_mapping(cls):
        return {
            "internal_product_id":      0,
            "product_name":             1,
            "category":                 2,
            "current_product_price":    3,
            "first_product_attribute":  4,
            "second_product_attribute": 5,
            "product_link":             6,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CouponExcelMapper  — unchanged
# ─────────────────────────────────────────────────────────────────────────────

class CouponExcelMapper:

    REQUIRED_FIELDS = [
        "coupon_code",
        "discount_percentage",
    ]

    FIELDS_DESCRIPTION = {
        "coupon_code":          "کد تخفیف یکتا - Required",
        "discount_percentage":  "درصد تخفیف (عدد بین ۰ تا ۱۰۰) - Required",
    }

    INSTRUCTIONS = {
        "file_type":       "Coupons File",
        "required_fields": len(REQUIRED_FIELDS),
        "fields_list":     REQUIRED_FIELDS,
        "note": "شماره ایندکس ستون‌ها از ۰ شروع می‌شود. مثال: ستون اول = 0، ستون دوم = 1",
    }

    @classmethod
    def validate_mapping_integrity(cls, mapping: dict):
        if not mapping:
            return False, "Coupons column mapping is required and cannot be empty."
        missing = set(cls.REQUIRED_FIELDS) - set(mapping.keys())
        if missing:
            return False, f"Missing coupons fields in mapping: {missing}"
        indices = list(mapping.values())
        if len(indices) != len(set(indices)):
            return False, "Duplicate column indices found in coupons mapping."
        if any(idx < 0 for idx in indices):
            return False, "Column indices cannot be negative."
        return True, "Mapping is valid"

    @classmethod
    def validate_and_map_file(cls, file_path: str, column_mapping: dict):
        is_valid, error_msg = cls.validate_mapping_integrity(column_mapping)
        if not is_valid:
            raise ValueError(error_msg)

        df = pd.read_excel(file_path)
        df = df.fillna("")

        max_index_needed = max(column_mapping.values())
        if len(df.columns) <= max_index_needed:
            raise ValueError(
                f"Coupons file must have at least {max_index_needed + 1} columns. "
                f"Found {len(df.columns)} columns."
            )

        actual_column_mapping = {}
        mapped_data = {}

        for field_name, col_idx in column_mapping.items():
            if field_name not in cls.REQUIRED_FIELDS:
                continue
            actual_column_mapping[field_name] = df.columns[col_idx]
            mapped_data[field_name] = df[df.columns[col_idx]]

        missing = set(cls.REQUIRED_FIELDS) - set(mapped_data.keys())
        if missing:
            raise ValueError(f"Missing required fields after mapping: {missing}")

        return pd.DataFrame(mapped_data), actual_column_mapping

    @classmethod
    def get_sample_mapping(cls):
        return {
            "coupon_code":         0,
            "discount_percentage": 1,
        }
