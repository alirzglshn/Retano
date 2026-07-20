# notifications/admin.py
"""
This admin panel IS the notification-sending interface. There is no
staff-facing API — writing a Notification here is exactly how "we"
notify a tenant, so the list view is optimized for that workflow:
finding a tenant, seeing what's already been sent to them, and adding
a new title/content pair.
"""

from django.contrib import admin

from .jalali import to_jalali_string
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "tenant", "created_at_jalali_display", "is_read"]
    list_filter = ["is_read", "created_at"]
    search_fields = ["title", "content", "tenant__owner__phone_number", "tenant__owner__shop_name"]
    raw_id_fields = ["tenant"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]

    fields = ["tenant", "title", "content", "is_read", "created_at"]

    @admin.display(description="تاریخ ارسال")
    def created_at_jalali_display(self, obj) -> str:
        return to_jalali_string(obj.created_at)
