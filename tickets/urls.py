from django.urls import path
from .views import (
    TicketListView,
    TicketCreateView,
    TicketDetailView,
    TicketStatusUpdateView,
)

urlpatterns = [
    path("", TicketListView.as_view(), name="ticket-list"),
    path("create/", TicketCreateView.as_view(), name="ticket-create"),
    path("<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("<int:pk>/status/", TicketStatusUpdateView.as_view(), name="ticket-status-update"),
]