# core/models.py

from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_tenant_for_new_user(sender, instance, created, **kwargs):
    if created:
        Tenant.objects.get_or_create(owner=instance)


class Tenant(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return f"Tenant #{self.id} — {self.owner}"


# ─────────────────────────────────────────────────────────────────────────────
# Coupon
# ─────────────────────────────────────────────────────────────────────────────

class Coupon(models.Model):
    status = models.CharField(default="available")
    coupon_code = models.TextField(unique=True, max_length=2000)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def __str__(self):
        return f"Coupon {self.coupon_code} | Tenant {self.tenant_id}"


# ─────────────────────────────────────────────────────────────────────────────
# File Upload Models
# ─────────────────────────────────────────────────────────────────────────────

class CustomerFileUpload(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    customers_file = models.FileField(upload_to="campaign_customers/")
    customers_mapping = models.JSONField(
        default=dict,
        help_text=(
            "Maps field names to zero-based column indices "
            "in the customers Excel file."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CustomerFileUpload #{self.id} | Tenant {self.tenant_id}"


class ProductFileUpload(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    products_file = models.FileField(upload_to="campaign_products/")
    products_mapping = models.JSONField(
        default=dict,
        help_text=(
            "Maps field names to zero-based column indices "
            "in the products Excel file."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ProductFileUpload #{self.id} | Tenant {self.tenant_id}"


class CouponFileUpload(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    coupons_file = models.FileField(upload_to="campaign_coupons/")
    coupons_mapping = models.JSONField(
        default=dict,
        help_text=(
            "Maps field names to zero-based column indices "
            "in the coupons Excel file."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CouponFileUpload #{self.id} | Tenant {self.tenant_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Campaign
# ─────────────────────────────────────────────────────────────────────────────

class Campaign(models.Model):

    COUPON_DISCOUNT_PERCENTAGE_CHOICES = [
        (i, f"{i}%") for i in range(0, 101)
    ]

    ACTIVATION_BASE_CHOICES = [
        ("همیشه", "همیشه"),
        ("آخرین خرید", "آخرین خرید"),
        ("اولین خرید", "اولین خرید"),
        ("یادآوری خرید بعدی", "یادآوری خرید بعدی"),
        ("قدرت خرید", "قدرت خرید"),
    ]

    COMPARISON_TYPE_CHOICES = [
        ("بزرگتر از", "بزرگتر از"),
        ("کوچکتر از", "کوچکتر از"),
        ("برابر با", "برابر با"),
    ]

    VALUE_UNIT_CHOICES = [
        ("روز", "روز"),
        ("تومان", "تومان"),
    ]

    GENDER_CHOICES = [
        ("آقایان", "آقایان"),
        ("بانوان", "بانوان"),
        ("همه", "همه"),
    ]

    BUYING_POWER_CHOICES = [
        ("همه", "همه"),
        ("خیلی بالا", "خیلی بالا"),
        ("بالا", "بالا"),
        ("متوسط", "متوسط"),
        ("پایین", "پایین"),
        ("خیلی پایین", "خیلی پایین"),
    ]

    PRIORITIES_CHOICES = [
        ("خیلی بالا", "خیلی بالا"),
        ("بالا", "بالا"),
        ("متوسط", "متوسط"),
        ("پایین", "پایین"),
        ("خیلی پایین", "خیلی پایین"),
    ]

    PRODUCT_SOURCE_CHOICES = [
        ("اولین محصول پرفروش", "اولین محصول پرفروش"),
        ("دومین محصول پرفروش", "دومین محصول پرفروش"),
        ("سومین محصول پرفروش", "سومین محصول پرفروش"),
        ("پرتکرارترین محصول خریداری شده کاربر", "پرتکرارترین محصول خریداری شده کاربر"),
        ("هیچ کدام", "هیچ کدام"),
    ]

    CUSTOMER_TYPE_CHOICES = [
        ("همه", "همه"),
        ("ویژه", "ویژه"),
        ("فعال", "فعال"),
        ("تازه وارد", "تازه وارد"),
        ("در خطر ریزش", "در خطر ریزش"),
        ("از دست رفته", "از دست رفته"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    rule_number = models.IntegerField(editable=False)

    coupon_discount_percentage = models.DecimalField(
        choices=COUPON_DISCOUNT_PERCENTAGE_CHOICES,
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    campaign_start_date = models.DateField(null=True, blank=True)
    campaign_end_date = models.DateField(null=True, blank=True)
    send_sms_time = models.TimeField(default="11:00:00")

    activation_base = models.CharField(
        blank=True, null=True, max_length=50,
        choices=ACTIVATION_BASE_CHOICES, default="همیشه",
    )
    comparison_type = models.CharField(
        null=True, blank=True, max_length=50,
        choices=COMPARISON_TYPE_CHOICES, default="بزرگتر از",
    )
    comparison_value = models.IntegerField(null=True, blank=True, default=1)
    value_unit = models.CharField(
        null=True, blank=True, max_length=50,
        choices=VALUE_UNIT_CHOICES, default="روز",
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITIES_CHOICES, default="خیلی بالا",
    )
    buying_power = models.CharField(
        max_length=20, choices=BUYING_POWER_CHOICES, default="همه",
    )
    customer_type = models.CharField(
        max_length=50, choices=CUSTOMER_TYPE_CHOICES, default="همه",
    )
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES, default="همه",
    )
    
    first_product_attribute = models.CharField(
        max_length=255,
        default="همه",
        blank=True,
        verbose_name="ویژگی اول محصول",
    )
    second_product_attribute = models.CharField(
        max_length=255,
        default="همه",
        blank=True,
        verbose_name="ویژگی دوم محصول",
    )  
    product_source = models.CharField(
        max_length=100, choices=PRODUCT_SOURCE_CHOICES,
        default="اولین محصول پرفروش",
    )
    is_active = models.BooleanField(default=True)
    message_pattern = models.TextField(default="الگوی پیام")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            last_rule = (
                Campaign.objects.filter(tenant_id=self.tenant_id)
                .order_by("-rule_number")
                .first()
            )
            self.rule_number = last_rule.rule_number + 1 if last_rule else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Campaign {self.rule_number} | Tenant {self.tenant_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Users flat store  (customers-file pipeline)
# ─────────────────────────────────────────────────────────────────────────────

class UsersUnNormalizedData(models.Model):
    """
    Permanent flat store for the customers-file pipeline.
    product_id is NULL until the products file is uploaded and the Postgres
    flush function backfills it via internal_product_id.
    subtotal is computed in Postgres as quantity * then_product_price.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    internal_user_id = models.TextField(default="null")
    user_id = models.IntegerField()

    first_name = models.CharField(max_length=200)
    last_name = models.TextField(null=True, blank=True)
    gender = models.TextField(null=True, blank=True, default="زن")
    phone_number = models.TextField(null=True, blank=True)

    internal_order_id = models.TextField(default="null")
    order_id = models.IntegerField()
    order_date = models.DateTimeField(null=True, blank=True)

    internal_product_id = models.TextField(default="null")
    product_id = models.IntegerField(null=True, blank=True)

    then_product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    column_mapping = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_unnormalized_data"
        indexes = [
            models.Index(fields=["tenant_id"], name="users_unnorm_tenant_idx"),
            models.Index(
                fields=["internal_product_id"],
                name="users_unnorm_int_prod_idx",
            ),
        ]

    def __str__(self):
        return f"UsersUnNorm order {self.order_id} | Tenant {self.tenant_id}"


class UsersUnNormalizedDataStaging(models.Model):
    """
    Staging mirror of users_unnormalized_data.
    managed = False — created by RunSQL in migration 0044.
    No triggers. Flushed via flush_customers_staging(p_tenant_id).
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    internal_user_id = models.TextField(default="null")
    user_id = models.IntegerField()

    first_name = models.CharField(max_length=200)
    last_name = models.TextField(null=True, blank=True)
    gender = models.TextField(null=True, blank=True, default="زن")
    phone_number = models.TextField(null=True, blank=True)

    internal_order_id = models.TextField(default="null")
    order_id = models.IntegerField()
    order_date = models.DateTimeField(null=True, blank=True)

    internal_product_id = models.TextField(default="null")
    product_id = models.IntegerField(null=True, blank=True)

    then_product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    column_mapping = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_unnormalized_data_staging"
        managed = False

    def __str__(self):
        return f"UsersStaging order {self.order_id} | Tenant {self.tenant_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Products flat store  (products-file pipeline)
# ─────────────────────────────────────────────────────────────────────────────

class ProductsUnNormalizedData(models.Model):
    """
    Permanent flat store for the products-file pipeline.

    first_product_attribute and second_product_attribute are raw values
    from the products Excel file — no normalisation is applied.
    current_product_price is initialised from the Excel file and updated
    manually over time. It is the price used in all analytics.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    internal_product_id = models.TextField(default="null")
    product_id = models.IntegerField()

    product_name = models.CharField(max_length=255)
    product_category = models.CharField(max_length=100)
    current_product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_link = models.URLField(max_length=2000, blank=True)

    # Generic product attributes — raw values, no normalisation
    first_product_attribute = models.TextField(null=True, blank=True)
    second_product_attribute = models.TextField(null=True, blank=True)

    column_mapping = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "products_unnormalized_data"
        indexes = [
            models.Index(fields=["tenant_id"], name="products_unnorm_tenant_idx"),
            models.Index(
                fields=["internal_product_id"],
                name="products_unnorm_int_prod_idx",
            ),
        ]

    def __str__(self):
        return f"ProductsUnNorm {self.product_name} | Tenant {self.tenant_id}"


class ProductsUnNormalizedDataStaging(models.Model):
    """
    Staging mirror of products_unnormalized_data.
    managed = False — created by RunSQL in migration 0044, altered in 0045.
    No triggers. Flushed via flush_products_staging(p_tenant_id).
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    internal_product_id = models.TextField(default="null")
    product_id = models.IntegerField()

    product_name = models.CharField(max_length=255)
    product_category = models.CharField(max_length=100)
    current_product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_link = models.URLField(max_length=2000, blank=True)

    first_product_attribute = models.TextField(null=True, blank=True)
    second_product_attribute = models.TextField(null=True, blank=True)

    column_mapping = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "products_unnormalized_data_staging"
        managed = False

    def __str__(self):
        return f"ProductsStaging {self.product_name} | Tenant {self.tenant_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Error Log
# ─────────────────────────────────────────────────────────────────────────────

class ErrorLog(models.Model):

    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("error", "Error"),
        ("warning", "Warning"),
        ("info", "Info"),
    ]

    SOURCE_CHOICES = [
        ("coupon", "Coupon"),
        ("sms", "SMS"),
        ("campaign", "Campaign"),
        ("trigger", "Trigger"),
        ("system", "System"),
        ("other", "Other"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The tenant this error belongs to, if applicable",
    )
    source = models.CharField(
        max_length=50, choices=SOURCE_CHOICES, default="other",
        help_text="Which part of the system raised this error",
    )
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default="error",
        help_text="How severe is this error",
    )
    error_code = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Machine-readable error code, e.g. NO_COUPON_FOUND",
    )
    message = models.TextField(help_text="Human-readable error message")
    context = models.JSONField(
        default=dict, blank=True,
        help_text="Structured data relevant to this error",
    )
    resolved = models.BooleanField(
        default=False,
        help_text="Whether this error has been acknowledged and resolved",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id"]),
            models.Index(fields=["source"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["resolved"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return (
            f"[{self.severity.upper()}] {self.source} | "
            f"{self.error_code or 'N/A'} | {self.created_at}"
        )
