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