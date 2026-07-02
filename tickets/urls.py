# tickets/urls.py

from django.urls import path

from .views import (
    ChatView,
    SmsPurchaseRequestView,
    SupportChatView,
    UnreadCountView,
)

urlpatterns = [
    # Tenant-facing
    path("tickets/chat/", ChatView.as_view(), name="tickets-chat"),
    path("tickets/unread/", UnreadCountView.as_view(), name="tickets-unread"),
    path(
        "sms/purchase-request/",
        SmsPurchaseRequestView.as_view(),
        name="sms-purchase-request",
    ),
    # Support-facing (staff only)
    path(
        "tickets/support/<int:tenant_id>/",
        SupportChatView.as_view(),
        name="tickets-support-chat",
    ),
]
