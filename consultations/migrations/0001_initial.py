import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FreeConsult",
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
                    "phone_number",
                    models.CharField(
                        max_length=13,
                        validators=[
                            django.core.validators.RegexValidator(
                                message=(
                                    "Enter an Iranian phone number starting with "
                                    "09 or +989."
                                ),
                                regex="^(?:09[0-9]{9}|\\+989[0-9]{9})$",
                            )
                        ],
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
