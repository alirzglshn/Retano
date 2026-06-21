# core/views.py
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Campaign
from .serializers import (
    CampaignListSerializer,
    CampaignSerializer,
    CampaignToggleSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Campaigns 
# ─────────────────────────────────────────────────────────────────────────────


class CampaignViewSet(viewsets.ModelViewSet):
    """
    /api/v1/campaigns/                 — list, create
    /api/v1/campaigns/{id}/            — retrieve, update, partial_update, destroy
    /api/v1/campaigns/{id}/toggle/     — PATCH, flips/sets is_active

    Tenant isolation: every queryset is scoped to the requesting user's
    own tenant. A campaign belonging to another tenant is invisible —
    not "403 Forbidden", just a 404, since DRF's get_object() raises
    Http404 when the filtered queryset doesn't contain the pk.
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
    ordering_fields = ["created_at", "name", "rule_number"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Campaign.objects.filter(tenant__owner=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return CampaignListSerializer
        if self.action == "toggle":
            return CampaignToggleSerializer
        return CampaignSerializer

    def perform_create(self, serializer):
        # tenant is never trusted from the client — derived from the
        # authenticated user's own Tenant (created via signal at registration).
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=["patch"])
    def toggle(self, request, pk=None):
        """
        PATCH /api/v1/campaigns/{id}/toggle/

        Body {} or omitted        → flips is_active.
        Body {"is_active": true}  → sets it explicitly.
        """
        campaign = self.get_object()

        if "is_active" in request.data:
            serializer = self.get_serializer(
                campaign, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            campaign.is_active = not campaign.is_active
            campaign.save(update_fields=["is_active"])
            serializer = self.get_serializer(campaign)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CampaignMetaView(APIView):
    """
    GET /api/v1/campaigns/meta/

    Returns every choice-field's available options so the frontend can
    build selects/dropdowns without hardcoding Persian labels.

    Shape:
        {
            "activation_base": [{"value": "...", "label": "..."}, ...],
            "comparison_type": [...],
            ...
        }
    """

    permission_classes = [permissions.IsAuthenticated]

    #: Campaign fields whose `choices` should be exposed. Listed explicitly
    #: rather than introspected so the response shape is stable even if
    #: unrelated choice fields get added to the model later.
    CHOICE_FIELDS = [
        "coupon_discount_percentage",
        "activation_base",
        "comparison_type",
        "value_unit",
        "gender",
        "buying_power",
        "priority",
        "product_source",
        "customer_type",
    ]

    def get(self, request):
        data = {}
        for field_name in self.CHOICE_FIELDS:
            field = Campaign._meta.get_field(field_name)
            choices = field.choices or []
            data[field_name] = [
                {"value": value, "label": label} for value, label in choices
            ]
        return Response(data, status=status.HTTP_200_OK)
