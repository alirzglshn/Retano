# notifications/models.py
"""
One-way, admin-authored notifications shown to a tenant on the
"موجودی پیامک" bell / notification list page (Image 1 / Image 2 of the
product's UI).

This deliberately replaces the old ``tickets`` app. There is no
two-way messaging here: a ``Notification`` is created exclusively by
staff through the Django admin panel. Tenants can only ever read
(list + retrieve) their own notifications and, as a side effect of
retrieving one, mark it read. There is no tenant-facing create/update/
delete of any kind, and no notion of a "thread" — each row is fully
independent, and a tenant may have any number of them.

Fields map 1:1 onto what the UI actually needs (see Image 1's table
columns — عنوان / تاریخ ارسال / وضعیت / نمایش — and Image 2's detail
view — عنوان + body + تاریخ):
    title      -> عنوان (list column, and header on the detail view)
    content    -> the body shown on the detail view after مشاهده
    created_at -> تاریخ ارسال (list) / تاریخ (detail) — stored as a
                  normal Gregorian DateTimeField so it stays sortable
                  and queryable and admin's date filters keep working;
                  the Jalali string the frontend actually displays is
                  computed at serialization time, not stored.
    is_read    -> وضعیت (خوانده شده / خوانده نشده)
"""

from django.conf import settings
from django.db import models

from core.models import Tenant


class Notification(models.Model):
    """
    A single notification sent to a single tenant.

    A tenant can have arbitrarily many of these over time — this is a
    plain ForeignKey (many notifications per tenant), not a
    OneToOneField "thread". There is intentionally no sender field:
    every notification is authored by "us" (staff, via the admin
    panel), so who on the staff side wrote it isn't part of the
    tenant-facing product and doesn't need to be modeled.
    """

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="The tenant this notification is addressed to.",
    )
    title = models.CharField(
        max_length=255,
        help_text="عنوان — shown in the notification list.",
    )
    content = models.TextField(
        help_text="Full body — shown when the tenant clicks مشاهده.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(
        default=False,
        help_text="خوانده شده (True) / خوانده نشده (False).",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "is_read"]),
            models.Index(fields=["tenant", "created_at"]),
        ]
        verbose_name = "notification"
        verbose_name_plural = "notifications"

    def __str__(self) -> str:
        return f"[{'read' if self.is_read else 'unread'}] {self.title} -> Tenant #{self.tenant_id}"
