from pathlib import Path

import django.db.models.deletion
from django.db import migrations, models


def install_global_identity_pipeline(apps, schema_editor):
    project_root = Path(__file__).resolve().parents[2]
    sql_path = project_root / "sql" / "global_identity_upload_pipeline.sql"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql_path.read_text(encoding="utf-8"))


class Migration(migrations.Migration):
    # The SQL performs audits, table rewrites, identity bootstrap, sequence
    # alignment, and function replacement as one transaction. It is
    # intentionally irreversible: discarding persistent identity registries
    # would invalidate the global-ID guarantee.
    atomic = True

    dependencies = [
        ("core", "0054_upload_history"),
    ]

    operations = [
        migrations.RunPython(install_global_identity_pipeline),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="usersunnormalizeddata",
                    name="user_id",
                    field=models.BigIntegerField(),
                ),
                migrations.AlterField(
                    model_name="usersunnormalizeddata",
                    name="order_id",
                    field=models.BigIntegerField(),
                ),
                migrations.AlterField(
                    model_name="usersunnormalizeddata",
                    name="product_id",
                    field=models.BigIntegerField(),
                ),
                migrations.AlterField(
                    model_name="productsunnormalizeddata",
                    name="product_id",
                    field=models.BigIntegerField(),
                ),
                migrations.AddField(
                    model_name="usersunnormalizeddatastaging",
                    name="upload_job",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="upload_job_id",
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="customer_staging_rows",
                        to="core.uploadjob",
                    ),
                ),
                migrations.AlterField(
                    model_name="usersunnormalizeddatastaging",
                    name="user_id",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
                migrations.AlterField(
                    model_name="usersunnormalizeddatastaging",
                    name="order_id",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
                migrations.AlterField(
                    model_name="usersunnormalizeddatastaging",
                    name="product_id",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="productsunnormalizeddatastaging",
                    name="upload_job",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="upload_job_id",
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_staging_rows",
                        to="core.uploadjob",
                    ),
                ),
                migrations.AlterField(
                    model_name="productsunnormalizeddatastaging",
                    name="product_id",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
            ],
        ),
    ]
