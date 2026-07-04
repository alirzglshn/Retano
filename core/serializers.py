# core/serializers.py
from rest_framework import serializers

from .models import Campaign


class CampaignListSerializer(serializers.ModelSerializer):
    """
    Condensed shape for GET /api/v1/campaigns/ (list action).

    Intentionally excludes the heavier targeting/messaging fields —
    those only matter once you're looking at a single campaign.
    """

    class Meta:
        model = Campaign
        fields = [
            "id",
            "rule_number",
            "name",
            "is_active",
            "priority",
            "campaign_start_date",
            "campaign_end_date",
            "created_at",
        ]
        read_only_fields = fields


class CampaignSerializer(serializers.ModelSerializer):
    """
    Full shape for create/update/retrieve.

    tenant and rule_number are backend-controlled:
        * tenant is set from request.user's tenant in the view, never
          accepted from the client.
        * rule_number is auto-incremented per-tenant in Campaign.save().
    """

    class Meta:
        model = Campaign
        fields = [
            "id",
            "tenant",
            "rule_number",
            "name",
            "coupon_discount_percentage",
            "campaign_start_date",
            "campaign_end_date",
            "send_sms_time",
            "activation_base",
            "comparison_type",
            "comparison_value",
            "value_unit",
            "priority",
            "buying_power",
            "customer_type",
            "gender",
            "first_product_attribute",
            "second_product_attribute",
            "product_source",
            "description",
            "is_active",
            "message_pattern",
            "created_at",
        ]
        read_only_fields = ["id", "tenant", "rule_number", "created_at"]

    def validate(self, attrs):
        start = attrs.get(
            "campaign_start_date",
            getattr(self.instance, "campaign_start_date", None),
        )
        end = attrs.get(
            "campaign_end_date",
            getattr(self.instance, "campaign_end_date", None),
        )
        if start and end and start > end:
            raise serializers.ValidationError(
                {
                    "campaign_end_date": (
                        "campaign_end_date must not be before campaign_start_date."
                    )
                }
            )
        return attrs


class CampaignToggleSerializer(serializers.ModelSerializer):
    """Body for PATCH /api/v1/campaigns/{id}/toggle/ — is_active only."""

    class Meta:
        model = Campaign
        fields = ["id", "is_active"]
        read_only_fields = ["id"]
