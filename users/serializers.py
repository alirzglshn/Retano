# users/serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .auth.phone import normalize_iranian_phone
from .models import CustomUser


# ─────────────────────────────────────────────────────────────────────────────
# Auth (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────


class PhoneNumberField(serializers.CharField):
    """
    CharField that normalizes any accepted Iranian phone format to E.164
    before it reaches view/service logic.
    """

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        try:
            return normalize_iranian_phone(raw)
        except Exception as exc:  # ValidationError from django.core.exceptions
            raise serializers.ValidationError(str(exc))


class OTPRequestSerializer(serializers.Serializer):
    """POST /api/v1/auth/otp/request/ — accepts a phone number to OTP."""

    phone_number = PhoneNumberField()


class OTPVerifySerializer(serializers.Serializer):
    """
    POST /api/v1/auth/otp/verify/

    Verifies the OTP and, on success, issues Simple JWT access/refresh
    tokens. Creates the user on first verification (so verify also acts
    as implicit login-or-register for users who skip /auth/register/).
    """

    phone_number = PhoneNumberField()
    code = serializers.RegexField(
        regex=r"^[0-9]{4}$",
        min_length=4,
        max_length=4,
        trim_whitespace=False,
        write_only=True,
        error_messages={"invalid": "OTP code must contain exactly 4 digits."},
    )

    def create_tokens(self, user: CustomUser) -> dict:
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class RegisterSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/auth/register/

    Creates a CustomUser from a phone number. Optional profile fields may
    be supplied up front; everything else is filled in later via
    /api/v1/profile/. Saving triggers the existing post_save signal on
    CustomUser, which creates the user's Tenant.
    """

    phone_number = PhoneNumberField()

    class Meta:
        model = CustomUser
        fields = [
            "phone_number",
            "first_name",
            "last_name",
            "shop_name",
        ]

    def validate_phone_number(self, value):
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )
        return value

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)


class LogoutSerializer(serializers.Serializer):
    """POST /api/v1/auth/logout/ — blacklists the given refresh token."""

    refresh = serializers.CharField()


# ─────────────────────────────────────────────────────────────────────────────
# Profile (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────


class ProfileSerializer(serializers.ModelSerializer):
    """
    GET/PATCH /api/v1/profile/

    phone_number is intentionally read-only here: changing the auth
    identifier is a security-sensitive operation (would need its own
    OTP-reverification flow) and is out of scope for this endpoint.

    profile_picture accepts multipart/form-data uploads — the global
    DRF parser config in config/settings/base.py already includes
    MultiPartParser and FormParser alongside JSONParser, so PATCHing
    this field with an image works with no view-level changes.

    business_domain is a fixed set of choices (حوزه کاری dropdown) —
    see BUSINESS_DOMAIN_CHOICES in users/models.py for the current list.
    """

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "phone_number",
            "username",
            "email",
            "first_name",
            "last_name",
            "shop_name",
            "website_address",
            "position",
            "birth_date",
            "about_me",
            "is_premium",
            "profile_picture",
            "business_domain",
        ]
        read_only_fields = ["id", "phone_number", "is_premium"]
