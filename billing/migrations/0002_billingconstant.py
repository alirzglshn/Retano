from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def create_billing_constants(apps, schema_editor):
    BillingConstant = apps.get_model("billing", "BillingConstant")
    BillingConstant.objects.get_or_create(singleton_key=1)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="bill",
            name="bill_valid_package_pricing",
        ),
        migrations.CreateModel(
            name="BillingConstant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "singleton_key",
                    models.PositiveSmallIntegerField(
                        default=1,
                        editable=False,
                        unique=True,
                    ),
                ),
                (
                    "sms_unit_price",
                    models.DecimalField(
                        decimal_places=0,
                        default=Decimal("400"),
                        max_digits=20,
                        validators=[MinValueValidator(Decimal("0"))],
                    ),
                ),
                (
                    "discount_percentage_1000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "discount_percentage_5000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("5.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "discount_percentage_25000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("10.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "discount_percentage_60000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("15.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "discount_percentage_150000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("20.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "discount_percentage_300000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("30.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "discount_percentage_500000",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("40.00"),
                        max_digits=5,
                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                    ),
                ),
                (
                    "privileges",
                    models.TextField(default="this is retano 360"),
                ),
            ],
            options={
                "verbose_name": "billing constants",
                "verbose_name_plural": "billing constants",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("singleton_key", 1)),
                        name="billing_constants_singleton",
                    )
                ],
            },
        ),
        migrations.RunPython(
            create_billing_constants,
            migrations.RunPython.noop,
        ),
    ]
