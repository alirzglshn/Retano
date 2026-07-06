# core/migrations/0046_sync_models.py
"""
Adds the three models backing the automated ETL synchronization system:
SyncConfig, SyncFieldMapping, SyncRun.

Renumber this file to match your actual latest migration number before
applying — 0046 assumes migrations 0044/0045 (referenced in the models'
docstrings) are the most recent ones. Run:
    python manage.py makemigrations --check --dry-run
to confirm the correct next number for your tree before applying this.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_upload_job_and_staging_nullable_ids"),  
    ]

    operations = [
        migrations.CreateModel(
            name="SyncConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_enabled", models.BooleanField(default=False)),
                (
                    "api_key_hash",
                    models.CharField(
                        blank=True, max_length=64, null=True, unique=True
                    ),
                ),
                (
                    "api_key_prefix",
                    models.CharField(blank=True, max_length=12, null=True),
                ),
                ("api_key_generated_at", models.DateTimeField(blank=True, null=True)),
                ("batch_size", models.PositiveIntegerField(default=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_config",
                        to="core.tenant",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="syncconfig",
            index=models.Index(
                fields=["api_key_hash"], name="core_syncco_api_key_ha_idx"
            ),
        ),
        migrations.CreateModel(
            name="SyncFieldMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "entity",
                    models.CharField(
                        choices=[("user", "User"), ("product", "Product")],
                        max_length=10,
                    ),
                ),
                ("field_name", models.CharField(max_length=100)),
                ("client_table", models.CharField(blank=True, default="", max_length=255)),
                ("client_column", models.CharField(blank=True, default="", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_field_mappings",
                        to="core.tenant",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="syncfieldmapping",
            index=models.Index(
                fields=["tenant", "entity"], name="core_syncfi_tenant__idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="syncfieldmapping",
            constraint=models.UniqueConstraint(
                fields=["tenant", "entity", "field_name"],
                name="uq_sync_field_mapping_tenant_entity_field",
            ),
        ),
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("success", "Success"),
                            ("partial", "Partial success"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=10,
                    ),
                ),
                (
                    "failure_stage",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("schema_table", "Missing table"),
                            ("schema_column", "Missing column"),
                            ("connection", "Could not connect to client database"),
                            ("ingest", "Rejected during ingest"),
                            ("unknown", "Unknown / unclassified"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("failure_detail", models.TextField(blank=True, default="")),
                ("users_rows_received", models.PositiveIntegerField(default=0)),
                ("users_rows_accepted", models.PositiveIntegerField(default=0)),
                ("users_rows_rejected", models.PositiveIntegerField(default=0)),
                ("products_rows_received", models.PositiveIntegerField(default=0)),
                ("products_rows_accepted", models.PositiveIntegerField(default=0)),
                ("products_rows_rejected", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_runs",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.AddIndex(
            model_name="syncrun",
            index=models.Index(
                fields=["tenant", "-started_at"], name="core_syncru_tenant__idx"
            ),
        ),
        migrations.AddIndex(
            model_name="syncrun",
            index=models.Index(fields=["status"], name="core_syncru_status_idx"),
        ),
    ]
