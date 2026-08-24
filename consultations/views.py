from django.shortcuts import get_object_or_404

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions
from rest_framework.throttling import ScopedRateThrottle

from core.serializers_schema import ErrorResponseSerializer

from .models import FreeConsult
from .permissions import IsDjangoSuperuser
from .serializers import FreeConsultIdQuerySerializer, FreeConsultSerializer


@extend_schema(
    tags=["Free Consultations"],
    summary="Request a free consultation",
    description=(
        "Public endpoint for submitting an Iranian phone number in either "
        "09xxxxxxxxx or +989xxxxxxxxx format. Authentication is not required."
    ),
    request=FreeConsultSerializer,
    responses={
        201: FreeConsultSerializer,
        400: ErrorResponseSerializer,
        429: ErrorResponseSerializer,
    },
    auth=[],
)
class FreeConsultCreateView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "free_consult_create"
    queryset = FreeConsult.objects.all()
    serializer_class = FreeConsultSerializer


@extend_schema(
    tags=["Free Consultations"],
    summary="List all free consultation requests",
    description="Returns every submitted phone number. Django superuser only.",
    responses={
        200: FreeConsultSerializer(many=True),
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
    },
)
class FreeConsultListView(generics.ListAPIView):
    permission_classes = [IsDjangoSuperuser]
    pagination_class = None
    queryset = FreeConsult.objects.all()
    serializer_class = FreeConsultSerializer


@extend_schema(
    tags=["Free Consultations"],
    summary="Get a free consultation request by ID",
    description="Returns one submitted phone number. Django superuser only.",
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Free consultation request ID.",
        )
    ],
    responses={
        200: FreeConsultSerializer,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
class FreeConsultDetailView(generics.RetrieveAPIView):
    permission_classes = [IsDjangoSuperuser]
    queryset = FreeConsult.objects.all()
    serializer_class = FreeConsultSerializer

    def get_object(self):
        query = FreeConsultIdQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        instance = get_object_or_404(
            self.get_queryset(),
            pk=query.validated_data["id"],
        )
        self.check_object_permissions(self.request, instance)
        return instance
