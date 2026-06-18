# core/urls.py

from django.urls import path
from .views import (
    CampaignListView,
    CampaignDetailView,
    CampaignUpdateView,
    CampaignDeleteView,
    CampaignCreateView,
    CampaignExcelFilesView,
    DashBoardView,
)

urlpatterns = [
    path("", DashBoardView, name="dashboard-view"),
    path("campaigns/", CampaignListView.as_view(), name="campaign-list"),
    path("campaigns/create/", CampaignCreateView.as_view(), name="campaign-create"),
    path("campaigns/excel-files/", CampaignExcelFilesView.as_view(), name="campaign-excel-files"),
    path("campaigns/<int:pk>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("campaigns/<int:pk>/edit/", CampaignUpdateView.as_view(), name="campaign-update"),
    path("campaigns/<int:pk>/delete/", CampaignDeleteView.as_view(), name="campaign-delete"),
]