# tickets/models.py
"""
Ticketing system — one chat thread per tenant.

Architecture:
    Each Tenant has exactly one Thread (created on first message).
    Messages belong to a Thread and are sent by either the tenant
    (sender_type='tenant') or support (sender_type='support').

    Unread count for the dashboard badge = number of support messages
    sent after the tenant's last_seen_at timestamp on the Thread.
"""

from django.conf import settings
from django.db import models

from core.models import Tenant


class Thread(models.Model):
    """
    One chat thread per tenant.
    Created automatically on first message via get_or_create.
    """

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="thread",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Tenant's last visit to the chat — used to compute unread badge count.
    # NULL means the tenant has never opened the chat.
    tenant_last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Thread — Tenant #{self.tenant_id}"

    def unread_count(self) -> int:
        """
        Number of support messages the tenant has not yet seen.
        A message is unseen if it was created after tenant_last_seen_at.
        """
        qs = self.messages.filter(sender_type=Message.SUPPORT)
        if self.tenant_last_seen_at:
            qs = qs.filter(created_at__gt=self.tenant_last_seen_at)
        return qs.count()


class Message(models.Model):
    """
    A single message in a Thread.
    sender_type distinguishes tenant messages from support messages.
    """

    TENANT = "tenant"
    SUPPORT = "support"
    SENDER_TYPE_CHOICES = [
        (TENANT, "Tenant"),
        (SUPPORT, "Support"),
    ]

    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_type = models.CharField(
        max_length=10,
        choices=SENDER_TYPE_CHOICES,
    )
    # For tenant messages: the CustomUser who sent it.
    # For support messages: the staff CustomUser who replied.
    # NULL is allowed so support can post without a user account if needed.
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["sender_type"]),
        ]

    def __str__(self):
        return f"[{self.sender_type}] Thread#{self.thread_id} @ {self.created_at:%Y-%m-%d %H:%M}"