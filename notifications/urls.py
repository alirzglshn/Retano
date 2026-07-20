# notifications/urls.py

from django.urls import path

from .views import (
    NotificationDetailView,
    NotificationListView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path(
        "notifications/unread-count/",
        NotificationUnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "notifications/<int:pk>/",
        NotificationDetailView.as_view(),
        name="notifications-detail",
    ),
]
