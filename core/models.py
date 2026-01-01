from django.db import models


class Campaign(models.Model):

    # ---------- CHOICES ----------
    WEEK_CHOICES = [
        ("اول", "اول"),
        ("دوم", "دوم"),
        ("سوم", "سوم"),
        ("چهارم", "چهارم"),
        ("فرقی نمی کند", "فرقی نمی کند"),
    ]

    ACTIVATION_BASE_CHOICES = [
        ("همیشه", "همیشه"),
        ("آخرین خرید", "آخرین خرید"),
        ("اولین خرید", "اولین خرید"),
        ("تاریخ خرید بعدی", "تاریخ خرید بعدی"),
        ("دسته بندی مشتری", "دسته بندی مشتری"),
        ("یادآوری خرید بعدی", "یادآوری خرید بعدی"),
    ]

    COMPARISON_TYPE_CHOICES = [
        ("بزرگتر از", "بزرگتر از"),
        ("کوچکتر از", "کوچکتر از"),
        ("برابر با", "برابر با"),
    ]

    VALUE_UNIT_CHOICES = [
        ("روز", "روز"),
        ("درصد", "درصد"),
        ("سفارش", "سفارش"),
        ("تومان", "تومان"),
        ("تعداد", "تعداد"),
    ]

    GENDER_CHOICES = [
        ("آقایان", "آقایان"),
        ("بانوان", "بانوان"),
        ("همه", "همه"),
    ]

    COMPARISON_VALUE_CHOICES = [(i, i) for i in [
        1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,120,200,400
    ]]

    SKIN_TYPE_CHOICES = [
        ("پوست مختلط", "پوست مختلط"),
        ("پوست چرب", "پوست چرب"),
        ("پوست خشک", "پوست خشک"),
        ("همه", "همه"),
    ]

    HAIR_TYPE_CHOICES = [
        ("موی مختلط", "موی مختلط"),
        ("موی چرب", "موی چرب"),
        ("موی خشک", "موی خشک"),
        ("همه", "همه"),
    ]

    PRODUCT_SOURCE_CHOICES = [
        ("اولین محصول پرفروش", "اولین محصول پرفروش"),
        ("دومین محصول پرفروش", "دومین محصول پرفروش"),
        ("سومین محصول پرفروش", "سومین محصول پرفروش"),
        ("آخرین خرید + میانگین دوره خرید محصول", "آخرین خرید + میانگین دوره خرید محصول"),
        ("پرتکرارترین محصول خریداری شده کاربر", "پرتکرارترین محصول خریداری شده کاربر"),
        ("هیچ کدام", "هیچ کدام"),
    ]

    CUSTOMER_TYPE_CHOICES = [
        ("همه", "همه"),
        ("ویژه", "ویژه"),
        ("فعال", "فعال"),
        ("در خطر ریزش", "در خطر ریزش"),
        ("از دست رفته", "از دست رفته"),
    ]

    # ---------- FIELDS ----------
    tenant_id = models.IntegerField()

    name = models.CharField(max_length=255)
    rule_number = models.IntegerField(editable=False)

    week = models.CharField(
        max_length=50,
        choices=WEEK_CHOICES,
        default="فرقی نمی کند"
    )

    activation_base = models.CharField(
        max_length=50,
        choices=ACTIVATION_BASE_CHOICES,
        default="همیشه"
    )

    comparison_type = models.CharField(
        max_length=50,
        choices=COMPARISON_TYPE_CHOICES,
        default="بزرگتر از"
    )

    comparison_value = models.IntegerField(
        choices=COMPARISON_VALUE_CHOICES,
        default=1
    )

    value_unit = models.CharField(
        max_length=50,
        choices=VALUE_UNIT_CHOICES,
        default="روز"
    )

    customer_type = models.CharField(
        max_length=50,
        choices=CUSTOMER_TYPE_CHOICES,
        default="همه"
    )

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default="همه"
    )

    skin_type = models.CharField(
        max_length=50,
        choices=SKIN_TYPE_CHOICES,
        default="همه"
    )

    hair_type = models.CharField(
        max_length=50,
        choices=HAIR_TYPE_CHOICES,
        default="همه"
    )

    product_source = models.CharField(
        max_length=100,
        choices=PRODUCT_SOURCE_CHOICES,
        default="اولین محصول پرفروش"
    )

    is_active = models.BooleanField(default=True)

    customers_file = models.FileField(
        upload_to="campaign_customers/",
        null=True,
        blank=True
    )

    message_pattern = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant_id"]),
        ]


    def save(self, *args, **kwargs):
        if not self.pk:
            last_rule = Campaign.objects.filter(
                tenant_id=self.tenant_id
            ).order_by('-rule_number').first()
            self.rule_number = last_rule.rule_number + 1 if last_rule else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Campaign {self.rule_number} | Tenant {self.tenant_id}"
