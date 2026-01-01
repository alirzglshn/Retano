from django.urls import path
from .views import (
    CampaignListCreateAPIView,
    CampaignDetailAPIView
)

urlpatterns = [
    path("api/campaigns/", CampaignListCreateAPIView.as_view()),
    path("api/campaigns/<int:pk>/", CampaignDetailAPIView.as_view()),
]
