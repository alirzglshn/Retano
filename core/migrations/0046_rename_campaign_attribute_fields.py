# core/migrations/0046_rename_campaign_attribute_fields.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0045_attribute_column_refactor"),  
    ]

    operations = [
        migrations.RenameField(
            model_name="campaign",
            old_name="skin_type",
            new_name="first_product_attribute",
        ),
        migrations.RenameField(
            model_name="campaign",
            old_name="hair_type",
            new_name="second_product_attribute",
        ),
        migrations.AlterField(
            model_name="campaign",
            name="first_product_attribute",
            field=models.CharField(
                max_length=255,
                default="همه",
                verbose_name="ویژگی اول محصول",
                blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="campaign",
            name="second_product_attribute",
            field=models.CharField(
                max_length=255,
                default="همه",
                verbose_name="ویژگی دوم محصول",
                blank=True,
            ),
        ),
    ]