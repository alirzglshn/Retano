# tickets/serializers.py

from rest_framework import serializers

from .models import Message, Thread


class MessageSerializer(serializers.ModelSerializer):
    """
    Read shape for a single message.
    sender_display is the phone number of the sender, or 'support'
    for staff messages — gives the frontend something human-readable
    without exposing internal user IDs.
    """

    sender_display = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender_type",
            "sender_display",
            "body",
            "created_at",
        ]
        read_only_fields = fields

    def get_sender_display(self, obj) -> str:
        if obj.sender_type == Message.SUPPORT:
            return "support"
        if obj.sender and obj.sender.phone_number:
            return obj.sender.phone_number
        return "tenant"


class SendMessageSerializer(serializers.Serializer):
    """Write shape — body only. Everything else is derived server-side."""

    body = serializers.CharField(min_length=1, max_length=5000)


class SmsPurchaseRequestSerializer(serializers.Serializer):
    """
    Write shape for POST /api/v1/sms/purchase-request/.

    All pricing (discount_percent, unit_price, total_price, final_price)
    is calculated on the frontend and accepted here only to be relayed
    to support in the chat message — the backend never recalculates or
    trusts these numbers for anything billing-related. They are optional
    precisely because the backend's only real requirement is the SMS
    quantity; the rest is convenience context for the support agent.
    """

    sms_count = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    discount_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    final_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
