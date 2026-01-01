from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny , IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Campaign
from .serializers import CampaignSerializer


class TenantMixin:
    def get_tenant_id(self, request):
        tenant_id = getattr(request, "tenant_id", None)
        if not tenant_id:
            raise PermissionDenied("Authentication required")
        return tenant_id


class CampaignListCreateAPIView(APIView, TenantMixin):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        tenant_id = self.get_tenant_id(request)

        campaigns = Campaign.objects.filter(
            tenant_id=tenant_id
        ).order_by("-created_at")

        serializer = CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)

    def post(self, request):
        tenant_id = self.get_tenant_id(request)

        serializer = CampaignSerializer(data=request.data)
        if serializer.is_valid():
            campaign = serializer.save(tenant_id=tenant_id)
            return Response(
                CampaignSerializer(campaign).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignDetailAPIView(APIView, TenantMixin):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self, request, pk):
        tenant_id = self.get_tenant_id(request)
        return get_object_or_404(
            Campaign,
            pk=pk,
            tenant_id=tenant_id
        )

    def get(self, request, pk):
        campaign = self.get_object(request, pk)
        return Response(CampaignSerializer(campaign).data)

    def put(self, request, pk):
        campaign = self.get_object(request, pk)
        serializer = CampaignSerializer(
            campaign,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        campaign = self.get_object(request, pk)
        campaign.delete()
        return Response({"success": True}, status=status.HTTP_204_NO_CONTENT)
