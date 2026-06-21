# users/migrations/0005_phone_as_username_field.py
"""
Phase 2 — make ``phone_number`` the canonical authentication identifier.

This migration:
    * Makes ``phone_number`` NOT NULL and validated (Iranian E.164).
    * Makes ``email`` optional (nullable, still unique-when-present).
    * Makes ``username`` optional (nullable, still unique-when-present).

The data-pipeline tables in ``core`` are untouched.

Operational note
----------------
Before applying this migration in any environment that already has user
rows, run a one-off data backfill that populates ``phone_number`` for
every existing user. The migration will refuse to apply otherwise
because ``phone_number`` is being promoted to NOT NULL.
"""

from django.db import migrations, models

import users.models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_customuser_shop_website_address_and_more"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="customuser",
            managers=[
                ("objects", users.models.CustomUserManager()),
            ],
        ),
        migrations.AlterField(
            model_name="customuser",
            name="username",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=150,
                unique=True,
                help_text=(
                    "Optional. Kept for Django admin and legacy compatibility. "
                    "Authentication uses phone_number."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="customuser",
            name="email",
            field=models.EmailField(
                blank=True,
                null=True,
                max_length=254,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="customuser",
            name="phone_number",
            field=models.CharField(
                max_length=20,
                unique=True,
                validators=[users.models.IRANIAN_PHONE_REGEX],
                help_text=(
                    "Iranian mobile number in E.164 form, e.g. +989121234567."
                ),
            ),
        ),
    ]
