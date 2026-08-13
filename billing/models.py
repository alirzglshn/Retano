import secrets
import string
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Q

from core.models import Tenant

BILLING_ID_LENGTH = 48


def generate_billing_id() -> str:
    characters = [
        secrets.choice(string.ascii_letters),
        secrets.choice(string.digits),
    ]
    alphabet = string.ascii_letters + string.digits
    characters.extend(secrets.choice(alphabet) for _ in range(BILLING_ID_LENGTH - 2))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


class BillingConstant(models.Model):
    singleton_key = models.PositiveSmallIntegerField(
        default=1,
        unique=True,
        editable=False,
    )
    sms_unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=Decimal("400"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount_percentage_1000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_percentage_5000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_percentage_25000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_percentage_60000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_percentage_150000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_percentage_300000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_percentage_500000 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("40.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    privileges = models.TextField(default="با خرید بیش از 6000 پیامک ، کسب و کار شما توسط متخصصین ما تحلیل می شود")

    class Meta:
        verbose_name = "billing constants"
        verbose_name_plural = "billing constants"
        constraints = [
            models.CheckConstraint(
                condition=Q(singleton_key=1),
                name="billing_constants_singleton",
            )
        ]

    def __str__(self) -> str:
        return "Billing constants"

    @classmethod
    def get_solo(cls, *, for_update: bool = False):
        queryset = cls.objects
        if for_update:
            queryset = queryset.select_for_update()
        instance, _ = queryset.get_or_create(singleton_key=1)
        return instance

    def discount_for(self, sms_count: int) -> Decimal:
        field_name = f"discount_percentage_{sms_count}"
        try:
            return getattr(self, field_name)
        except AttributeError as exc:
            raise ValidationError({"sms_count": "Unsupported SMS count."}) from exc

    def packages(self) -> list[dict]:
        return [
            {
                "sms_count": sms_count,
                "discount_percentage": self.discount_for(sms_count),
            }
            for sms_count in Bill.SMSCount.values
        ]

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        self.full_clean()
        with transaction.atomic():
            if self.pk:
                type(self).objects.select_for_update().filter(pk=self.pk).exists()
            result = super().save(*args, **kwargs)
            Bill.recalculate_pending(self)
            return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Billing constants cannot be deleted.")


class Bill(models.Model):
    class SMSCount(models.IntegerChoices):
        ONE_THOUSAND = 1_000, "1,000"
        FIVE_THOUSAND = 5_000, "5,000"
        TWENTY_FIVE_THOUSAND = 25_000, "25,000"
        SIXTY_THOUSAND = 60_000, "60,000"
        ONE_HUNDRED_FIFTY_THOUSAND = 150_000, "150,000"
        THREE_HUNDRED_THOUSAND = 300_000, "300,000"
        FIVE_HUNDRED_THOUSAND = 500_000, "500,000"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"

    billing_id = models.CharField(
        max_length=BILLING_ID_LENGTH,
        unique=True,
        default=generate_billing_id,
        editable=False,
        validators=[
            RegexValidator(
                regex=rf"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{{{BILLING_ID_LENGTH}}}$",
                message=(
                    "Billing ID must contain exactly 48 Latin letters and numbers, "
                    "including at least one of each."
                ),
            )
        ],
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="bills",
    )
    sms_unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=Decimal("400"),
        editable=False,
    )
    sms_count = models.PositiveIntegerField(choices=SMSCount.choices)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )
    discount_amount = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=Decimal("0"),
        editable=False,
    )
    actual_price = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=Decimal("0"),
        editable=False,
    )
    final_price = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=Decimal("0"),
        editable=False,
    )
    status = models.CharField(
        max_length=7,
        choices=Status.choices,
        default=Status.PENDING,
    )
    card_number = models.CharField(
        max_length=16,
        default="5029081043096987",
    )
    bale_id = models.CharField(
        max_length=64,
        default="@Retano_Admin",
    )

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pending", "paid"]),
                name="bill_valid_status",
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(status="pending"),
                name="bill_one_pending_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.billing_id} - {self.tenant}"

    def clean(self) -> None:
        super().clean()
        if not self.pk:
            return
        previous = (
            type(self)
            .objects.filter(pk=self.pk)
            .only(
                "billing_id",
                "sms_count",
                "status",
                "tenant_id",
            )
            .first()
        )
        if not previous:
            return
        if previous.billing_id != self.billing_id:
            raise ValidationError({"billing_id": "The billing ID cannot be changed."})
        if previous.tenant_id != self.tenant_id:
            raise ValidationError({"tenant": "The tenant cannot be changed."})
        if previous.status == self.Status.PAID and previous.sms_count != self.sms_count:
            raise ValidationError(
                {"sms_count": "The SMS count of a paid bill cannot be changed."}
            )
        if previous.status == self.Status.PAID and self.status != self.Status.PAID:
            raise ValidationError(
                {"status": "A paid bill cannot be returned to pending."}
            )

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        with transaction.atomic():
            constants = BillingConstant.get_solo(for_update=True)
            previous_status = None
            if not is_new:
                previous_status = (
                    type(self)
                    .objects.filter(pk=self.pk)
                    .values_list("status", flat=True)
                    .first()
                )
            if is_new:
                self.status = self.Status.PENDING
            if is_new or previous_status == self.Status.PENDING:
                self._calculate_pricing(constants)

            update_fields = kwargs.get("update_fields")
            if update_fields is not None and (
                "sms_count" in update_fields or previous_status == self.Status.PENDING
            ):
                kwargs["update_fields"] = set(update_fields) | {
                    "sms_unit_price",
                    "discount_percentage",
                    "discount_amount",
                    "actual_price",
                    "final_price",
                }

            self.full_clean(validate_unique=False)
            if not is_new:
                return super().save(*args, **kwargs)

            for _ in range(5):
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    if (
                        not type(self)
                        .objects.filter(billing_id=self.billing_id)
                        .exists()
                    ):
                        raise
                    self.billing_id = generate_billing_id()
        raise IntegrityError("Could not generate a unique billing ID.")

    def _calculate_pricing(self, constants: BillingConstant) -> None:
        discount_percentage = constants.discount_for(self.sms_count)
        actual_price = Decimal(self.sms_count) * constants.sms_unit_price
        discount_amount = (
            actual_price * discount_percentage / Decimal("100")
        ).quantize(Decimal("1"))
        self.sms_unit_price = constants.sms_unit_price
        self.discount_percentage = discount_percentage
        self.actual_price = actual_price
        self.discount_amount = discount_amount
        self.final_price = actual_price - discount_amount

    @classmethod
    def recalculate_pending(cls, constants: BillingConstant) -> None:
        for sms_count in cls.SMSCount.values:
            discount_percentage = constants.discount_for(sms_count)
            actual_price = Decimal(sms_count) * constants.sms_unit_price
            discount_amount = (
                actual_price * discount_percentage / Decimal("100")
            ).quantize(Decimal("1"))
            cls.objects.filter(
                status=cls.Status.PENDING,
                sms_count=sms_count,
            ).update(
                sms_unit_price=constants.sms_unit_price,
                discount_percentage=discount_percentage,
                actual_price=actual_price,
                discount_amount=discount_amount,
                final_price=actual_price - discount_amount,
            )
