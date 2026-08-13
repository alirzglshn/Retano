import tempfile
import uuid

import openpyxl

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from rest_framework import status
from rest_framework.test import APIClient

from core.models import CustomerFileUpload, UploadJob
from core.tasks.uploads import _inspect_workbook

User = get_user_model()

HISTORY_URL = "/api/v1/uploads/history/"


class WorkbookHeaderTests(SimpleTestCase):
    def test_inspection_preserves_exact_header_text(self):
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.append(["نام مشتری", " Product ID ", "شماره سفارش"])
        worksheet.append(["Ali", "P-1", "O-1"])

        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/headers.xlsx"
            workbook.save(path)
            total_rows, headers = _inspect_workbook(path)

        workbook.close()
        self.assertEqual(total_rows, 1)
        self.assertEqual(
            headers,
            ["نام مشتری", " Product ID ", "شماره سفارش"],
        )


class UploadHistoryTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            phone_number="+989122222222",
            password="testpass123",
        )

    def create_job(self, user, job_status, filename="customers.xlsx"):
        return UploadJob.objects.create(
            tenant=user.tenant,
            upload_type=UploadJob.UploadType.CUSTOMERS,
            status=job_status,
            storage_key=f"staging/{uuid.uuid4()}/{filename}",
            original_filename=filename,
            mapping={"internal_id": 0},
            column_headers=["نام مشتری", " Product ID ", "شماره سفارش"],
            total_rows=12,
            processed_rows=12,
            rows_saved=12,
            message="Upload completed.",
        )

    def attach_file(self, job, content=b"exact original excel bytes"):
        return CustomerFileUpload.objects.create(
            upload_job=job,
            tenant=job.tenant,
            customers_mapping=job.mapping,
            customers_file=SimpleUploadedFile(
                job.original_filename,
                content,
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        )

    def test_history_requires_authentication(self):
        response = self.client.get(HISTORY_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_history_contains_only_successful_jobs_for_current_tenant(self):
        successful_job = self.create_job(self.user, UploadJob.Status.SUCCESS)
        self.attach_file(successful_job)
        self.create_job(self.user, UploadJob.Status.PARTIAL, "partial.xlsx")
        self.create_job(self.user, UploadJob.Status.FAILED, "failed.xlsx")
        other_job = self.create_job(
            self.other_user,
            UploadJob.Status.SUCCESS,
            "other.xlsx",
        )
        self.attach_file(other_job)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(HISTORY_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["job_id"], str(successful_job.id))
        self.assertEqual(result["status"], UploadJob.Status.SUCCESS)
        self.assertEqual(
            result["column_headers"],
            ["نام مشتری", " Product ID ", "شماره سفارش"],
        )
        self.assertEqual(result["original_filename"], "customers.xlsx")
        self.assertTrue(
            result["download_url"].endswith(
                f"/api/v1/uploads/jobs/{successful_job.id}/download/"
            )
        )

    def test_history_includes_completed_polling_fields(self):
        job = self.create_job(self.user, UploadJob.Status.SUCCESS)
        self.attach_file(job)
        self.client.force_authenticate(user=self.user)

        result = self.client.get(HISTORY_URL).data["results"][0]

        polling_fields = {
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
        }
        self.assertTrue(polling_fields.issubset(result.keys()))

    def test_download_returns_exact_original_file(self):
        content = b"exact original excel bytes"
        job = self.create_job(self.user, UploadJob.Status.SUCCESS)
        self.attach_file(job, content)
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/uploads/jobs/{job.id}/download/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), content)
        self.assertIn(
            'filename="customers.xlsx"',
            response["Content-Disposition"],
        )

    def test_download_hides_other_tenant_jobs(self):
        job = self.create_job(self.other_user, UploadJob.Status.SUCCESS)
        self.attach_file(job)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/uploads/jobs/{job.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_rejects_non_successful_jobs(self):
        job = self.create_job(self.user, UploadJob.Status.PARTIAL)
        self.attach_file(job)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/uploads/jobs/{job.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
