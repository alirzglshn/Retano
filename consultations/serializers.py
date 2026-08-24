from rest_framework import serializers

from .models import FreeConsult


class FreeConsultSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreeConsult
        fields = ["id", "phone_number"]
        read_only_fields = ["id"]


class FreeConsultIdQuerySerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
