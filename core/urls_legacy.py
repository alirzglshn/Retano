# core/urls_legacy.py
"""
Legacy SSR URL routes — kept alive during the DRF transition period.
These will be removed once the React frontend is live and all API endpoints
are implemented and verified.

DO NOT add new routes here.  All new routes go into core/urls.py.
"""

from django.urls import path

from .views import (
    CampaignCreateView,
    CampaignDeleteView,
    CampaignDetailView,
    CampaignExcelFilesView,
    CampaignListView,
    CampaignUpdateView,
    DashBoardView,
)

urlpatterns = [
    path("", DashBoardView, name="dashboard-view"),
    path("campaigns/", CampaignListView.as_view(), name="campaign-list"),
    path("campaigns/create/", CampaignCreateView.as_view(), name="campaign-create"),
    path(
        "campaigns/excel-files/",
        CampaignExcelFilesView.as_view(),
        name="campaign-excel-files",
    ),
    path("campaigns/<int:pk>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path(
        "campaigns/<int:pk>/edit/",
        CampaignUpdateView.as_view(),
        name="campaign-update",
    ),
    path(
        "campaigns/<int:pk>/delete/",
        CampaignDeleteView.as_view(),
        name="campaign-delete",
    ),
]
