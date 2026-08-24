from django.urls import path

from .views import (
    FreeConsultCreateView,
    FreeConsultDetailView,
    FreeConsultListView,
)

app_name = "consultations"

urlpatterns = [
    path(
        "free-consults/",
        FreeConsultCreateView.as_view(),
        name="free-consult-create",
    ),
    path(
        "free-consults/all/",
        FreeConsultListView.as_view(),
        name="free-consult-list",
    ),
    path(
        "free-consults/by-id/",
        FreeConsultDetailView.as_view(),
        name="free-consult-detail",
    ),
]
