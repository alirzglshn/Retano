# notifications/serializers.py
"""
Read-only serializers for the tenant-facing notification API.

There is no write serializer here on purpose — tenants never create,
update, or delete notifications through the API. Every field below is
read_only so this can never accidentally become writable if a view is
later wired up carelessly.
"""

from rest_framework import serializers

from .jalali import to_jalali_string
from .models import Notification


class NotificationListSerializer(serializers.ModelSerializer):
    """
    GET /api/v1/notifications/  — one row per item in Image 1's table.

    created_at_jalali is the display string the frontend renders
    directly (e.g. "1405/03/10"); created_at is kept alongside it as
    the standard ISO datetime in case the frontend ever needs to sort
    or diff client-side.
    """

    created_at_jalali = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "created_at",
            "created_at_jalali",
            "is_read",
        ]
        read_only_fields = fields

    def get_created_at_jalali(self, obj) -> str:
        return to_jalali_string(obj.created_at, fmt="%Y/%m/%d")


class NotificationDetailSerializer(serializers.ModelSerializer):
    """
    GET /api/v1/notifications/{id}/ — Image 2's detail view.

    Includes `content`, which the list serializer omits since Image 1
    never shows body text — only the detail view does, after مشاهده.
    """

    created_at_jalali = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "content",
            "created_at",
            "created_at_jalali",
            "is_read",
        ]
        read_only_fields = fields

    def get_created_at_jalali(self, obj) -> str:
        return to_jalali_string(obj.created_at, fmt="%Y/%m/%d")
