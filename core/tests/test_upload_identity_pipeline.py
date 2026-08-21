from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pandas as pd

from django.test import override_settings

from core.tasks.uploads import (
    _allocate_flush_and_finalize,
    _copy_customers_chunk,
    _copy_products_chunk,
)


class UploadCopyJobScopingTests(TestCase):
    @patch("core.tasks.uploads.FlexibleDateParser.parse_series_to_dates")
    @patch("core.tasks.uploads._copy_buffer_into")
    def test_customer_copy_includes_upload_job_id(self, copy_mock, parse_dates):
        parse_dates.return_value = pd.Series(["2026-01-01"])
        frame = pd.DataFrame(
            [["u-1", "Ali", "R", "o-1", "2026-01-01", 2, 100, "+9891", "p-1", "m"]]
        )
        mapping = {
            "internal_id": 0,
            "first_name": 1,
            "last_name": 2,
            "internal_order_id": 3,
            "order_date": 4,
            "quantity": 5,
            "then_product_price": 6,
            "phone_number": 7,
            "internal_product_id": 8,
            "gender": 9,
        }

        saved, processed = _copy_customers_chunk(
            "00000000-0000-0000-0000-000000000001",
            9,
            frame,
            mapping,
            {},
            "2026-01-01T00:00:00Z",
        )

        self.assertEqual((saved, processed), (1, 1))
        sql, buffer = copy_mock.call_args.args
        self.assertIn("upload_job_id, tenant_id", sql)
        self.assertTrue(buffer.getvalue().startswith("00000000-0000-0000"))

    @patch("core.tasks.uploads._copy_buffer_into")
    def test_product_copy_includes_upload_job_id(self, copy_mock):
        frame = pd.DataFrame(
            [["p-1", "Product", "Cat", 100, "a", "b", "https://e.test"]]
        )
        mapping = {
            "internal_product_id": 0,
            "product_name": 1,
            "category": 2,
            "current_product_price": 3,
            "first_product_attribute": 4,
            "second_product_attribute": 5,
            "product_link": 6,
        }

        saved, processed = _copy_products_chunk(
            "00000000-0000-0000-0000-000000000002",
            9,
            frame,
            mapping,
            {},
            "2026-01-01T00:00:00Z",
        )

        self.assertEqual((saved, processed), (1, 1))
        sql, buffer = copy_mock.call_args.args
        self.assertIn("upload_job_id, tenant_id", sql)
        self.assertTrue(buffer.getvalue().startswith("00000000-0000-0000"))


class UploadFinalizationTests(TestCase):
    @override_settings(UPLOAD_DB_STATEMENT_TIMEOUT_MS=123456)
    @patch("core.tasks.uploads.connection.cursor")
    @patch("core.tasks.uploads.transaction.atomic")
    def test_allocation_and_flush_share_transaction_local_timeout(
        self, atomic_mock, cursor_mock
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        cursor_mock.return_value.__enter__.return_value = cursor
        job = MagicMock(id="00000000-0000-0000-0000-000000000003")

        rows = _allocate_flush_and_finalize(
            job,
            "flush_customers_upload_job",
            "success",
            "saved {rows_saved}",
        )

        self.assertEqual(rows, 42)
        atomic_mock.assert_called_once_with()
        self.assertEqual(
            cursor.execute.call_args_list[0].args,
            (
                "SELECT set_config('statement_timeout', %s, true)",
                ["123456"],
            ),
        )
        self.assertEqual(
            cursor.execute.call_args_list[1].args,
            ("SELECT allocate_upload_job_ids(%s)", [job.id]),
        )
        self.assertEqual(
            cursor.execute.call_args_list[2].args,
            ("SELECT flush_customers_upload_job(%s)", [job.id]),
        )
        self.assertEqual(job.rows_saved, 42)
        self.assertEqual(job.status, "success")
        self.assertEqual(job.message, "saved 42")
        job.save.assert_called_once_with(
            update_fields=["rows_saved", "status", "message", "updated_at"]
        )


class IdentitySqlContractTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        project_root = Path(__file__).resolve().parents[2]
        cls.sql = (
            project_root / "sql" / "global_identity_upload_pipeline.sql"
        ).read_text(encoding="utf-8")

    def test_identity_maps_enforce_stable_and_global_uniqueness(self):
        self.assertIn("PRIMARY KEY (tenant_id, internal_user_id)", self.sql)
        self.assertIn("PRIMARY KEY (tenant_id, internal_order_id)", self.sql)
        self.assertIn("PRIMARY KEY (tenant_id, internal_product_id)", self.sql)
        self.assertIn("UNIQUE (user_id)", self.sql)
        self.assertIn("UNIQUE (order_id)", self.sql)
        self.assertIn("UNIQUE (product_id)", self.sql)

    def test_customer_allocation_covers_all_three_id_types(self):
        self.assertIn("INSERT INTO global_user_identity", self.sql)
        self.assertIn("INSERT INTO global_order_identity", self.sql)
        self.assertIn("INSERT INTO global_product_identity", self.sql)
        self.assertIn(
            "user_id IS NULL OR order_id IS NULL OR product_id IS NULL", self.sql
        )
        self.assertIn("fill_missing_flat_product_identity", self.sql)
        self.assertIn("ALTER COLUMN product_id SET NOT NULL", self.sql)

    def test_flush_is_job_scoped(self):
        self.assertIn("flush_customers_upload_job(p_job_id uuid)", self.sql)
        self.assertIn("flush_products_upload_job(p_job_id uuid)", self.sql)
        self.assertIn("WHERE upload_job_id = p_job_id", self.sql)
        self.assertIn("INSERT INTO products (product_id, created_at)", self.sql)
