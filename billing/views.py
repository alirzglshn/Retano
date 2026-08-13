from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BusinessLogicError
from core.serializers_schema import ErrorResponseSerializer

from .models import Bill, BillingConstant
from .serializers import BillingConstantSerializer, BillSerializer


@extend_schema(
    tags=["Billing"],
    summary="Get public billing constants",
    description=(
        "Public pricing configuration for billing interfaces. Returns the current "
        "price of one SMS, all seven SMS-count options with their discount "
        "percentages, and the administrator-managed privileges text. No "
        "authentication is required. Existing pending bills are recalculated "
        "when this configuration changes; paid bills retain their snapshots."
    ),
    responses={200: BillingConstantSerializer},
    auth=[],
)
class BillingConstantView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        constants = BillingConstant.get_solo()
        return Response(BillingConstantSerializer(constants).data)


@extend_schema_view(
    list=extend_schema(
        tags=["Billing"],
        summary="List this tenant's bills",
        description=(
            "Returns only bills belonging to the authenticated user's tenant, "
            "newest first. Supports page and page_size pagination parameters. "
            "No search, filtering, or client-selected ordering is supported."
        ),
        responses={200: BillSerializer(many=True), 401: ErrorResponseSerializer},
    ),
    create=extend_schema(
        tags=["Billing"],
        summary="Create a pending bill",
        description=(
            "JSON input contains only sms_count. The tenant, billing ID, status, "
            "unit price, discount, calculated prices, card number, and Bale ID "
            "are assigned by the backend. Creation returns 409 while this tenant "
            "already has a pending bill."
        ),
        request=BillSerializer,
        responses={
            201: BillSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=["Billing"],
        summary="Retrieve a bill by billing ID",
        description=(
            "Looks up the public billing_id within the authenticated user's "
            "tenant. A bill owned by another tenant returns 404."
        ),
        responses={
            200: BillSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
    update=extend_schema(
        tags=["Billing"],
        summary="Replace the editable bill data",
        description=(
            "The JSON body must contain only sms_count. Pricing is recalculated "
            "server-side. Paid bills cannot be modified and return 409."
        ),
        request=BillSerializer,
        responses={
            200: BillSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    ),
    partial_update=extend_schema(
        tags=["Billing"],
        summary="Change a pending bill's SMS count",
        description=(
            "The JSON body may contain only sms_count. Pricing is recalculated "
            "server-side. Paid bills cannot be modified and return 409."
        ),
        request=BillSerializer,
        responses={
            200: BillSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    ),
    destroy=extend_schema(
        tags=["Billing"],
        summary="Delete a pending bill",
        description=(
            "Deletes a bill belonging to the authenticated user's tenant. "
            "Paid bills are retained and return 409."
        ),
        responses={
            204: OpenApiResponse(description="Deleted. No response body."),
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    ),
)
class BillViewSet(viewsets.ModelViewSet):
    serializer_class = BillSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = []
    lookup_field = "billing_id"
    lookup_url_kwarg = "billing_id"
    http_method_names = [
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
    ]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bill.objects.none()
        return Bill.objects.filter(tenant=self.request.user.tenant).select_related(
            "tenant", "tenant__owner"
        )

    def perform_destroy(self, instance):
        if instance.status == Bill.Status.PAID:
            raise BusinessLogicError("Paid bills cannot be deleted.")
        instance.delete()
