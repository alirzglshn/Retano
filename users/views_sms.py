# users/views_sms.py
"""
SMS activation request, pricing config, and balance endpoints.

No payment gateway. Flow:
    1. Frontend GETs /sms/packages/ on page load → gets price_per_sms and
       discount tiers → drives the slider and price breakdown locally.
    2. User moves slider, frontend computes قیمت اصلی / مبلغ تخفیف / هزینه نهایی
       entirely client-side using the config from step 1.
    3. User clicks خرید و فعال‌سازی → POST /sms/request-activation/ with sms_count.
    4. Backend posts a standard Persian message into the ticket thread.
    5. Frontend receives HTTP 201 and shows the toast for 5 seconds (frontend concern).
    6. Admin sees the message in the support chat, collects payment manually,
       then sets num_available_sms in Django admin.
    7. Frontend polls or reads GET /sms/balance/ to show موجودی پیامک.
"""

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.models import Message, Thread
from core.schema import SMS_PACKAGES_SCHEMA, SMS_ACTIVATION_REQUEST_SCHEMA, SMS_BALANCE_SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
# Pricing configuration
# Single source of truth. Change these constants when pricing changes.
# The frontend receives this via /sms/packages/ and does all arithmetic
# locally — no price calculations happen on the backend.
# ─────────────────────────────────────────────────────────────────────────────

PRICE_PER_SMS = 380  # تومان per SMS (هزینه هر پیام)

SMS_SLIDER_MIN = 1_000
SMS_SLIDER_MAX = 500_000

# Discount tiers: (minimum_sms_count, discount_percentage)
# Evaluated top-to-bottom; first matching tier wins.
DISCOUNT_TIERS = [
    (300_000, 40),
    (150_000, 30),
    (60_000,  20),
    (25_000,  15),
    (5_000,   10),
    (1_000,    5),
    (0,        0),
]


# ─────────────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────────────


class SMSActivationRequestSerializer(serializers.Serializer):
    sms_count = serializers.IntegerField(
        min_value=SMS_SLIDER_MIN,
        max_value=SMS_SLIDER_MAX,
        error_messages={
            "min_value": f"تعداد پیامک باید حداقل {SMS_SLIDER_MIN:,} باشد.",
            "max_value": f"تعداد پیامک نمی‌تواند بیشتر از {SMS_SLIDER_MAX:,} باشد.",
            "invalid":  "تعداد پیامک باید یک عدد صحیح باشد.",
            "required": "تعداد پیامک الزامی است.",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────


@SMS_PACKAGES_SCHEMA
class SMSPackagesView(APIView):
    """
    GET /api/v1/sms/packages/

    Returns the pricing configuration the frontend needs to drive the
    slider and the price breakdown panel. No authentication required —
    public pricing page.

    Response shape:
    {
        "price_per_sms": 380,
        "slider": {"min": 1000, "max": 500000},
        "discount_tiers": [
            {"min_sms": 300000, "discount_percent": 40},
            {"min_sms": 150000, "discount_percent": 30},
            ...
        ]
    }
    """

    permission_classes = [IsAuthenticated]  # page is behind login

    def get(self, request):
        tiers = [
            {"min_sms": min_sms, "discount_percent": pct}
            for min_sms, pct in DISCOUNT_TIERS
        ]
        return Response(
            {
                "price_per_sms": PRICE_PER_SMS,
                "slider": {
                    "min": SMS_SLIDER_MIN,
                    "max": SMS_SLIDER_MAX,
                },
                "discount_tiers": tiers,
            },
            status=status.HTTP_200_OK,
        )


@SMS_ACTIVATION_REQUEST_SCHEMA
class SMSActivationRequestView(APIView):
    """
    POST /api/v1/sms/request-activation/

    Body:  {"sms_count": 1000}

    Validates sms_count is within slider bounds, then opens (or reuses)
    the tenant's ticket Thread and posts the standard Persian
    activation-request message as the tenant user.

    Returns HTTP 201 with the Persian confirmation string.
    The frontend reads `detail` and displays it as a toast for 5 seconds.
    Clearing the toast after 5 seconds is entirely a frontend concern.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SMSActivationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sms_count = serializer.validated_data["sms_count"]
        tenant = request.user.tenant

        thread, _ = Thread.objects.get_or_create(tenant=tenant)

        body = (
            f"با سلام و عرض خسته نباشید ، "
            f"قصد فعال سازی تعداد {sms_count} پیامک را دارم."
        )

        Message.objects.create(
            thread=thread,
            sender_type=Message.TENANT,
            sender=request.user,
            body=body,
        )

        return Response(
            {"detail": "درخواست فعال سازی SMS شما برای تیم پشتیبانی ارسال شد."},
            status=status.HTTP_201_CREATED,
        )


@SMS_BALANCE_SCHEMA 
class SMSBalanceView(APIView):
    """
    GET /api/v1/sms/balance/

    Returns the user's current SMS credit (موجودی پیامک).
    This value is set manually in Django admin after payment confirmation.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {"num_available_sms": request.user.num_available_sms},
            status=status.HTTP_200_OK,
        )