from django.urls import reverse

from rest_framework import serializers

from core.models import UploadJob


class UploadHistorySerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(source="id", read_only=True)
    progress_percentage = serializers.FloatField(read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadJob
        fields = [
            "job_id",
            "upload_type",
            "status",
            "total_rows",
            "processed_rows",
            "rows_saved",
            "progress_percentage",
            "error_type",
            "message",
            "created_at",
            "updated_at",
            "original_filename",
            "column_headers",
            "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj) -> str:
        request = self.context.get("request")
        path = reverse("upload-job-download", kwargs={"job_id": obj.id})
        return request.build_absolute_uri(path) if request else path
