# users/migrations/0007_profile_picture_and_business_domain.py
"""
Adds the two fields needed for the تنظیمات (Settings) page:
    - profile_picture (ImageField, optional, local MEDIA_ROOT storage)
    - business_domain (CharField with choices, optional)

Depends on 0006_customuser_num_available_sms, the most recent migration
in the develop branch's history per the git log.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_customuser_num_available_sms"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="profile_picture",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="profile_pictures/",
                help_text="Optional avatar image shown in the sidebar (عکس پروفایل).",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="business_domain",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=50,
                choices=[
                    ("fashion_clothing", "مد و لباس"),
                    ("cosmetics_beauty", "لوازم آرایشی و بهداشتی"),
                    ("food_beverage", "غذا و نوشیدنی"),
                    ("home_kitchen", "لوازم خانه و آشپزخانه"),
                    ("digital_electronics", "لوازم دیجیتال و الکترونیک"),
                    ("other", "سایر"),
                ],
                help_text="Tenant's business category (حوزه کاری).",
            ),
        ),
    ]
