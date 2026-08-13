# notifications/views.py
"""
Tenant-facing notification endpoints.

All three views are strictly read-only from the tenant's perspective:
there is no POST/PUT/PATCH/DELETE anywhere in this module, and every
queryset is scoped to ``request.user.tenant`` so a tenant can only ever
see notifications addressed to them — never another tenant's.

Notifications themselves are authored exclusively through the Django
admin panel (see notifications/admin.py). Nothing here creates one.
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.schema import (
    NOTIFICATION_DETAIL_SCHEMA,
    NOTIFICATION_LIST_SCHEMA,
    NOTIFICATION_UNREAD_COUNT_SCHEMA,
)

from .models import Notification
from .serializers import NotificationDetailSerializer, NotificationListSerializer


@NOTIFICATION_LIST_SCHEMA
class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/

    Returns this tenant's notifications, newest first (Image 1's
    table). Purely a read — does not mark anything as read. Read
    state only changes when a specific notification's detail is
    fetched via NotificationDetailView.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationListSerializer
    filter_backends = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(tenant=self.request.user.tenant)


@NOTIFICATION_DETAIL_SCHEMA
class NotificationDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/notifications/{id}/

    Returns the full notification (Image 2) and, as a side effect,
    marks *this specific notification* as read. Other notifications
    belonging to the same tenant are untouched — read state is
    per-row, not thread-wide.

    Scoped to the requesting tenant, so a tenant cannot retrieve (or
    accidentally mark read) another tenant's notification by guessing
    an id — that lookup simply 404s.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationDetailSerializer

    def get_queryset(self):
        return Notification.objects.filter(tenant=self.request.user.tenant)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_read:
            instance.is_read = True
            instance.save(update_fields=["is_read"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)


@NOTIFICATION_UNREAD_COUNT_SCHEMA
class NotificationUnreadCountView(APIView):
    """
    GET /api/v1/notifications/unread-count/

    Returns the unread count for this tenant, for the red badge on the
    Telegram-like icon. Does not mutate anything — polling this
    endpoint never clears the badge; only viewing a notification's
    detail does.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            tenant=request.user.tenant, is_read=False
        ).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)
