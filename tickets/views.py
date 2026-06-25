# tickets/views.py

from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Tenant
from .models import Message, Thread
from .serializers import MessageSerializer, SendMessageSerializer


class IsStaffUser(permissions.BasePermission):
    """Allow only Django staff users (support team)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class ChatView(APIView):
    """
    GET  /api/v1/tickets/chat/
        Returns all messages in the tenant's thread, oldest first.
        Also updates tenant_last_seen_at so the unread badge resets.

    POST /api/v1/tickets/chat/
        Tenant sends a new message.
        Body: {"body": "..."}
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_thread(self, request) -> Thread:
        tenant = request.user.tenant
        thread, _ = Thread.objects.get_or_create(tenant=tenant)
        return thread

    def get(self, request):
        thread = self._get_thread(request)

        # Mark as seen — reset unread badge
        thread.tenant_last_seen_at = timezone.now()
        thread.save(update_fields=["tenant_last_seen_at"])

        messages = thread.messages.select_related("sender").all()
        serializer = MessageSerializer(messages, many=True)
        return Response(
            {"thread_id": thread.id, "messages": serializer.data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thread = self._get_thread(request)
        message = Message.objects.create(
            thread=thread,
            sender_type=Message.TENANT,
            sender=request.user,
            body=serializer.validated_data["body"],
        )
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class SupportChatView(APIView):
    """
    GET  /api/v1/tickets/support/{tenant_id}/
        Support reads a specific tenant's thread.

    POST /api/v1/tickets/support/{tenant_id}/
        Support sends a reply to a tenant's thread.
        Body: {"body": "..."}

    Only accessible to staff users.
    """

    permission_classes = [IsStaffUser]

    def _get_thread(self, tenant_id: int) -> Thread | None:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return None
        thread, _ = Thread.objects.get_or_create(tenant=tenant)
        return thread

    def get(self, request, tenant_id: int):
        thread = self._get_thread(tenant_id)
        if thread is None:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        messages = thread.messages.select_related("sender").all()
        serializer = MessageSerializer(messages, many=True)
        return Response(
            {"thread_id": thread.id, "messages": serializer.data},
            status=status.HTTP_200_OK,
        )

    def post(self, request, tenant_id: int):
        thread = self._get_thread(tenant_id)
        if thread is None:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            thread=thread,
            sender_type=Message.SUPPORT,
            sender=request.user,
            body=serializer.validated_data["body"],
        )
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class UnreadCountView(APIView):
    """
    GET /api/v1/tickets/unread/
    Returns the unread support message count for the dashboard badge.
    Does NOT update tenant_last_seen_at — polling this endpoint
    does not clear the badge.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            thread = request.user.tenant.thread
            count = thread.unread_count()
        except Thread.DoesNotExist:
            count = 0
        return Response({"unread_count": count}, status=status.HTTP_200_OK)