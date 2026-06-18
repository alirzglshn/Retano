# core/forms.py

from django import forms

from .models import (
    Campaign,
    CouponFileUpload,
    CustomerFileUpload,
    ProductFileUpload,
)
from .utils.excel_mapper import (
    CouponExcelMapper,
    CustomerExcelMapper,
    ProductExcelMapper,
)

# ─────────────────────────────────────────────────────────────────────────────
# Campaign form  — unchanged
# ─────────────────────────────────────────────────────────────────────────────


class CampaignForm(forms.ModelForm):

    campaign_start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        required=True,
        label="تاریخ شروع کمپین",
    )
    campaign_end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        required=True,
        label="تاریخ پایان کمپین",
    )
    coupon_discount_percentage = forms.ChoiceField(
        choices=Campaign.COUPON_DISCOUNT_PERCENTAGE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
        label="درصد تخفیف",
    )

    class Meta:
        model = Campaign
        fields = [
            "name",
            "campaign_start_date",
            "campaign_end_date",
            "send_sms_time",
            "activation_base",
            "comparison_type",
            "comparison_value",
            "coupon_discount_percentage",
            "value_unit",
            "customer_type",
            "priority",
            "buying_power",
            "gender",
            "first_product_attribute",
            "second_product_attribute",
            "product_source",
            "message_pattern",
            "is_active",
        ]
        labels = {
            "name": "نام کمپین",
            "activation_base": "مبنای فعال‌سازی",
            "comparison_type": "نوع مقایسه",
            "comparison_value": "مقدار مقایسه",
            "send_sms_time": "زمان ارسال پیامک",
            "value_unit": "واحد مقدار",
            "priority": "اولویت",
            "coupon_discount_percentage": "درصد تخفیف",
            "buying_power": "قدرت خرید",
            "customer_type": "نوع مشتری",
            "gender": "جنسیت",
            "first_product_attribute": "ویژگی اول محصول",
            "second_product_attribute": "ویژگی دوم محصول",
            "product_source": "منبع محصولات",
            "message_pattern": "الگوی پیام",
            "is_active": "فعال باشد",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "مثلاً کمپین خرید مجدد"}
            ),
            "send_sms_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "form-control",
                    "step": "1",
                    "placeholder": "HH:MM:SS",
                }
            ),
            "campaign_start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "campaign_end_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "activation_base": forms.Select(attrs={"class": "form-control"}),
            "comparison_type": forms.Select(attrs={"class": "form-control"}),
            "comparison_value": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "مقدار عددی وارد کنید",
                    "step": "1",
                    "min": "0",
                }
            ),
            "value_unit": forms.Select(attrs={"class": "form-control"}),
            "customer_type": forms.Select(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "first_product_attribute": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "مثلاً oily skin یا همه",
                }
            ),
            "second_product_attribute": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "مثلاً dry hair یا همه",
                }
            ),
            "product_source": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "buying_power": forms.Select(attrs={"class": "form-control"}),
            "message_pattern": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "متن پیام ارسالی به مشتری",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if (
            self.instance
            and self.instance.pk
            and hasattr(self.instance, "campaign_date")
        ):
            campaign_date = self.instance.campaign_date
            if campaign_date and campaign_date.lower:
                self.initial["campaign_start_date"] = campaign_date.lower
            if campaign_date and campaign_date.upper:
                self.initial["campaign_end_date"] = campaign_date.upper


# ─────────────────────────────────────────────────────────────────────────────
# File upload forms — one per file type, unchanged
# ─────────────────────────────────────────────────────────────────────────────


class CustomerFileUploadForm(forms.ModelForm):
    class Meta:
        model = CustomerFileUpload
        fields = ["customers_file"]
        labels = {"customers_file": "فایل مشتریان"}
        widgets = {
            "customers_file": forms.ClearableFileInput(
                attrs={"class": "form-control", "id": "id_customers_file"}
            ),
        }


class ProductFileUploadForm(forms.ModelForm):
    class Meta:
        model = ProductFileUpload
        fields = ["products_file"]
        labels = {"products_file": "فایل محصولات"}
        widgets = {
            "products_file": forms.ClearableFileInput(
                attrs={"class": "form-control", "id": "id_products_file"}
            ),
        }


class CouponFileUploadForm(forms.ModelForm):
    class Meta:
        model = CouponFileUpload
        fields = ["coupons_file"]
        labels = {"coupons_file": "فایل کد تخفیف"}
        widgets = {
            "coupons_file": forms.ClearableFileInput(
                attrs={"class": "form-control", "id": "id_coupons_file"}
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Combined column mapping form
# Customers section: unchanged from 0044.
# Products section:  hair_tag / skin_tag removed;
#                    first_product_attribute / second_product_attribute added.
# Coupons section:   unchanged.
# ─────────────────────────────────────────────────────────────────────────────


class ColumnMappingForm(forms.Form):

    # ── Customers fields (unchanged) ──────────────────────────────────────────
    customers_internal_id = forms.IntegerField(
        label="internal_id (شناسه مشتری)", min_value=0, required=False
    )
    customers_first_name = forms.IntegerField(
        label="first_name (نام)", min_value=0, required=False
    )
    customers_last_name = forms.IntegerField(
        label="last_name (نام خانوادگی)", min_value=0, required=False
    )
    customers_internal_order_id = forms.IntegerField(
        label="internal_order_id (شناسه سفارش)", min_value=0, required=False
    )
    customers_order_date = forms.IntegerField(
        label="order_date (تاریخ سفارش)", min_value=0, required=False
    )
    customers_quantity = forms.IntegerField(
        label="quantity (تعداد)", min_value=0, required=False
    )
    customers_then_product_price = forms.IntegerField(
        label="then_product_price (قیمت در زمان خرید)", min_value=0, required=False
    )
    customers_phone_number = forms.IntegerField(
        label="phone_number (شماره تلفن)", min_value=0, required=False
    )
    customers_internal_product_id = forms.IntegerField(
        label="internal_product_id (شناسه محصول)", min_value=0, required=False
    )
    customers_gender = forms.IntegerField(
        label="gender (جنسیت)", min_value=0, required=False
    )

    # ── Products fields — hair_tag/skin_tag removed, first/second added ───────
    products_internal_product_id = forms.IntegerField(
        label="internal_product_id (شناسه محصول)", min_value=0, required=False
    )
    products_product_name = forms.IntegerField(
        label="product_name (نام محصول)", min_value=0, required=False
    )
    products_category = forms.IntegerField(
        label="category (دسته‌بندی)", min_value=0, required=False
    )
    products_current_product_price = forms.IntegerField(
        label="current_product_price (قیمت فعلی محصول)", min_value=0, required=False
    )
    products_first_product_attribute = forms.IntegerField(
        label="first_product_attribute (ویژگی اول محصول)", min_value=0, required=False
    )
    products_second_product_attribute = forms.IntegerField(
        label="second_product_attribute (ویژگی دوم محصول)", min_value=0, required=False
    )
    products_product_link = forms.IntegerField(
        label="product_link (لینک محصول)", min_value=0, required=False
    )

    # ── Coupons fields (unchanged) ────────────────────────────────────────────
    coupons_coupon_code = forms.IntegerField(
        label="coupon_code (کد تخفیف)", min_value=0, required=False
    )
    coupons_discount_percentage = forms.IntegerField(
        label="discount_percentage (درصد تخفیف)", min_value=0, required=False
    )

    # ── Field name lists used by clean() ──────────────────────────────────────
    _CUSTOMERS_FORM_FIELDS = [
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

    _PRODUCTS_FORM_FIELDS = [
        "products_internal_product_id",
        "products_product_name",
        "products_category",
        "products_current_product_price",
        "products_first_product_attribute",
        "products_second_product_attribute",
        "products_product_link",
    ]

    _COUPONS_FORM_FIELDS = [
        "coupons_coupon_code",
        "coupons_discount_percentage",
    ]

    def __init__(self, *args, **kwargs):
        self.uploaded_files = kwargs.pop("uploaded_files", {})
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        has_customers = bool(self.uploaded_files.get("customers_file"))
        has_products = bool(self.uploaded_files.get("products_file"))
        has_coupons = bool(self.uploaded_files.get("coupons_file"))

        if has_customers:
            for field in self._CUSTOMERS_FORM_FIELDS:
                if cleaned_data.get(field) is None:
                    self.add_error(field, "این فیلد برای فایل مشتریان الزامی است")
            idxs = [
                cleaned_data.get(f)
                for f in self._CUSTOMERS_FORM_FIELDS
                if cleaned_data.get(f) is not None
            ]
            if len(idxs) != len(set(idxs)):
                raise forms.ValidationError(
                    "ایندکس‌های ستون‌های فایل مشتریان نباید تکراری باشند"
                )

        if has_products:
            for field in self._PRODUCTS_FORM_FIELDS:
                if cleaned_data.get(field) is None:
                    self.add_error(field, "این فیلد برای فایل محصولات الزامی است")
            idxs = [
                cleaned_data.get(f)
                for f in self._PRODUCTS_FORM_FIELDS
                if cleaned_data.get(f) is not None
            ]
            if len(idxs) != len(set(idxs)):
                raise forms.ValidationError(
                    "ایندکس‌های ستون‌های فایل محصولات نباید تکراری باشند"
                )

        if has_coupons:
            for field in self._COUPONS_FORM_FIELDS:
                if cleaned_data.get(field) is None:
                    self.add_error(field, "این فیلد برای فایل کوپن‌ها الزامی است")
            idxs = [
                cleaned_data.get(f)
                for f in self._COUPONS_FORM_FIELDS
                if cleaned_data.get(f) is not None
            ]
            if len(idxs) != len(set(idxs)):
                raise forms.ValidationError(
                    "ایندکس‌های ستون‌های فایل کوپن‌ها نباید تکراری باشند"
                )

        return cleaned_data

    def get_customers_mapping(self) -> dict:
        prefix = "customers_"
        return {
            k[len(prefix) :]: v
            for k, v in self.cleaned_data.items()
            if k.startswith(prefix) and v is not None
        }

    def get_products_mapping(self) -> dict:
        prefix = "products_"
        return {
            k[len(prefix) :]: v
            for k, v in self.cleaned_data.items()
            if k.startswith(prefix) and v is not None
        }

    def get_coupons_mapping(self) -> dict:
        prefix = "coupons_"
        return {
            k[len(prefix) :]: v
            for k, v in self.cleaned_data.items()
            if k.startswith(prefix) and v is not None
        }
