from rest_framework import serializers
from .models import Campaign


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign

        # tenant_id and rule_number are controlled by backend
        read_only_fields = [
            "id",
            "tenant_id",
            "rule_number",
            "created_at",
        ]

        fields = [
            "id",
            "rule_number",
            "name",  
            "week",
            "activation_base",
            "comparison_type",
            "comparison_value",
            "value_unit",
            "customer_type",
            "gender",
            "skin_type",
            "hair_type",
            "product_source",
            "customers_file",
            "message_pattern",
            "is_active",
            "created_at",
        ]
