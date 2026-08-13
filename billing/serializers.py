from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from rest_framework import serializers

from core.exceptions import BusinessLogicError

from .models import Bill, BillingConstant


class BillingPackageSerializer(serializers.Serializer):
    sms_count = serializers.IntegerField(read_only=True)
    discount_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )


class BillingConstantSerializer(serializers.ModelSerializer):
    packages = BillingPackageSerializer(many=True, read_only=True)

    class Meta:
        model = BillingConstant
        fields = ["sms_unit_price", "packages", "privileges"]
        read_only_fields = fields


class BillSerializer(serializers.ModelSerializer):
    writable_fields = {"sms_count"}

    class Meta:
        model = Bill
        fields = [
            "billing_id",
            "sms_unit_price",
            "sms_count",
            "discount_percentage",
            "discount_amount",
            "actual_price",
            "final_price",
            "status",
            "card_number",
            "bale_id",
        ]
        read_only_fields = [
            "billing_id",
            "sms_unit_price",
            "discount_percentage",
            "discount_amount",
            "actual_price",
            "final_price",
            "status",
            "card_number",
            "bale_id",
        ]

    def to_internal_value(self, data):
        disallowed_fields = set(data.keys()) - self.writable_fields
        if disallowed_fields:
            raise serializers.ValidationError(
                {
                    field: ["This field is read-only."]
                    for field in sorted(disallowed_fields)
                }
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        if self.instance and self.instance.status == Bill.Status.PAID:
            raise BusinessLogicError("Paid bills cannot be modified.")

        if self.instance and "sms_count" not in attrs:
            raise serializers.ValidationError(
                {"sms_count": ["This field is required."]}
            )

        if self.instance is None:
            tenant = self.context["request"].user.tenant
            if Bill.objects.filter(
                tenant=tenant,
                status=Bill.Status.PENDING,
            ).exists():
                raise BusinessLogicError(
                    "A pending bill already exists for this tenant."
                )
        return attrs

    def create(self, validated_data):
        tenant = self.context["request"].user.tenant
        try:
            with transaction.atomic():
                return Bill.objects.create(tenant=tenant, **validated_data)
        except DjangoValidationError as exc:
            if Bill.objects.filter(
                tenant=tenant,
                status=Bill.Status.PENDING,
            ).exists():
                raise BusinessLogicError(
                    "A pending bill already exists for this tenant."
                ) from exc
            raise serializers.ValidationError(exc.message_dict) from exc
        except IntegrityError as exc:
            if Bill.objects.filter(
                tenant=tenant,
                status=Bill.Status.PENDING,
            ).exists():
                raise BusinessLogicError(
                    "A pending bill already exists for this tenant."
                ) from exc
            raise

    def update(self, instance, validated_data):
        instance.sms_count = validated_data["sms_count"]
        try:
            instance.save(update_fields={"sms_count"})
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return instance
