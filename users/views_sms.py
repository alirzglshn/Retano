# users/views_sms.py
"""
SMS balance endpoint.

Everything about SMS *pricing* (price_per_sms, slider bounds, discount
tiers) and the *purchase flow* (the خرید و فعال‌سازی popup — order
code, card number, بابت name, amounts) is 100% frontend: hardcoded /
computed client-side, with zero backend involvement. There is no
Order/Invoice/Payment model and there never was meant to be one.

The only thing the backend is responsible for, for SMS billing, is
this: reporting how many SMS credits a tenant currently has, so the
frontend can render موجودی پیامک in the sidebar. That number is set by
hand in the Django admin after a manual bank-transfer payment is
confirmed via Bale — there is no automated flow that changes it, and
no endpoint that lets a tenant (or anything triggered by a tenant
action) create a message, request, or record of any kind.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.schema import SMS_BALANCE_SCHEMA


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
