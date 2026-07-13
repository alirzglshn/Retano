# core/migrations/0051_upload_job_and_staging_nullable_ids.py
#
# 1. Creates UploadJob.
# 2. Makes user_id/order_id nullable on UsersUnNormalizedDataStaging and
#    product_id nullable on ProductsUnNormalizedDataStaging.
#
#    Why this is actually needed (corrected after reviewing core/models.py):
#    UsersUnNormalizedDataStaging.user_id and .order_id are currently
#    models.IntegerField() with NO null=True -- same for
#    ProductsUnNormalizedDataStaging.product_id. In the old synchronous
#    pipeline this was fine because Python always allocated the ID in
#    memory before constructing the staging model instance, so the
#    column was never actually written as NULL.
#
#    In the new pipeline, COPY loads a chunk's rows into staging before
#    allocate_user_and_order_ids() / allocate_product_ids() has run, so
#    for the window between "chunk COPY'd" and "allocation SQL executed",
#    these columns must be able to hold NULL. This migration is required,
#    not optional, given the new write order -- if these columns stay
#    NOT NULL, the COPY statements in core/tasks/uploads.py (which do not
#    include user_id/order_id/product_id in their column list) will fail
#    at the database level.
#
#    Note: this only loosens the staging tables. The corresponding
#    permanent tables (UsersUnNormalizedData.user_id/order_id,
#    ProductsUnNormalizedData.product_id) are untouched and remain
#    NOT NULL, since flush_customers_staging / flush_products_staging
#    only ever move fully-allocated rows into them -- exactly as before.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_campaign_description"),  
    ]

    operations = [
        migrations.CreateModel(
            name="UploadJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "upload_type",
                    models.CharField(
                        choices=[
                            ("customers", "Customers"),
                            ("products", "Products"),
                            ("coupons", "Coupons"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("processing", "Processing"),
                            ("success", "Success"),
                            ("partial", "Partial"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("storage_key", models.CharField(max_length=500)),
                (
                    "original_filename",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("mapping", models.JSONField()),
                ("total_rows", models.PositiveIntegerField(blank=True, null=True)),
                ("processed_rows", models.PositiveIntegerField(default=0)),
                ("rows_saved", models.PositiveIntegerField(default=0)),
                (
                    "error_type",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ("message", models.TextField(blank=True, default="")),
                (
                    "celery_task_id",
                    models.CharField(blank=True, max_length=155, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="upload_jobs",
                        to="core.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "upload_job",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="uploadjob",
            index=models.Index(
                fields=["tenant", "status"], name="upload_job_tenant_status_idx"
            ),
        ),

        # -- Staging table column nullability --------------------------------
        # UsersUnNormalizedDataStaging and ProductsUnNormalizedDataStaging
        # are managed = False (created via RunSQL in migration 0044/0045).
        # A plain AlterField only updates Django's model state -- it will
        # NOT emit an ALTER TABLE for an unmanaged model, and the actual
        # Postgres columns would stay NOT NULL, which breaks the COPY
        # statements in core/tasks/uploads.py the moment they try to load
        # a row without user_id/order_id/product_id populated yet.
        #
        # SeparateDatabaseAndState is used so the database side runs the
        # real ALTER TABLE via RunSQL, while the state side keeps
        # Django's ORM model definition in sync for makemigrations/
        # migrate bookkeeping, matching how 0044/0045 already handle
        # these two tables.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="usersunnormalizeddatastaging",
                    name="user_id",
                    field=models.IntegerField(null=True, blank=True),
                ),
                migrations.AlterField(
                    model_name="usersunnormalizeddatastaging",
                    name="order_id",
                    field=models.IntegerField(null=True, blank=True),
                ),
                migrations.AlterField(
                    model_name="productsunnormalizeddatastaging",
                    name="product_id",
                    field=models.IntegerField(null=True, blank=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE users_unnormalized_data_staging
                            ALTER COLUMN user_id DROP NOT NULL,
                            ALTER COLUMN order_id DROP NOT NULL;
                        ALTER TABLE products_unnormalized_data_staging
                            ALTER COLUMN product_id DROP NOT NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE users_unnormalized_data_staging
                            ALTER COLUMN user_id SET NOT NULL,
                            ALTER COLUMN order_id SET NOT NULL;
                        ALTER TABLE products_unnormalized_data_staging
                            ALTER COLUMN product_id SET NOT NULL;
                    """,
                ),
            ],
        ),
    ]
