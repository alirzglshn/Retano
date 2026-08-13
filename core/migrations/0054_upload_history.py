import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_supabaseorder_supabaseorderitem_supabaseuser_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="uploadjob",
            name="column_headers",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="customerfileupload",
            name="upload_job",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="customer_upload_record",
                to="core.uploadjob",
            ),
        ),
        migrations.AddField(
            model_name="productfileupload",
            name="upload_job",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="product_upload_record",
                to="core.uploadjob",
            ),
        ),
        migrations.AddField(
            model_name="couponfileupload",
            name="upload_job",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="coupon_upload_record",
                to="core.uploadjob",
            ),
        ),
    ]
