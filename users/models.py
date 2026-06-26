# users/models.py
"""
CustomUser model.

Phase 2 change:
    - ``phone_number`` is now the canonical authentication identifier
      (``USERNAME_FIELD``).
    - ``email`` is preserved as an optional, unique-when-present field.
    - ``username`` is preserved as an optional, unique-when-present field
      so the Django admin and any legacy code that introspects
      ``get_username()`` keep working.

Nothing about the existing Tenant-creation signal or the rest of the
data pipeline is touched — registration still flows through the
standard ``post_save`` on ``CustomUser`` and the existing handler in
``core`` will create the Tenant exactly as before.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models


# ─────────────────────────────────────────────────────────────────────────────
# Validators
# ─────────────────────────────────────────────────────────────────────────────

#: Canonical E.164 form for Iranian mobile numbers, e.g. ``+989121234567``.
#: Inbound values are normalised to this shape before being stored.
IRANIAN_PHONE_REGEX = RegexValidator(
    regex=r"^\+989\d{9}$",
    message=(
        "Phone number must be a valid Iranian mobile number in E.164 form, "
        "e.g. +989121234567."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Manager
# ─────────────────────────────────────────────────────────────────────────────


class CustomUserManager(BaseUserManager):
    """
    Manager keyed on ``phone_number`` instead of ``username``.

    Passwords are optional: the primary auth flow is OTP-based and most
    users will never have a usable password. ``create_superuser`` still
    requires one because the Django admin needs it.
    """

    use_in_migrations = True

    def _create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("The phone_number field is required.")
        email = extra_fields.pop("email", None)
        if email:
            email = self.normalize_email(email)
            extra_fields["email"] = email
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if not password:
            raise ValueError("Superuser must have a password.")
        return self._create_user(phone_number, password, **extra_fields)


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────


class CustomUser(AbstractUser):
    """
    Auth identity for the platform.

    Identifier:
        phone_number  — required, unique, E.164 form (validated above).

    Optional contact / profile fields:
        email, username, first_name, last_name, shop_name,
        shop_website_address, website_address, position, birth_date,
        about_me, is_premium.
    """

    # Override AbstractUser.username so it is optional but still unique when set.
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text=(
            "Optional. Kept for Django admin and legacy compatibility. "
            "Authentication uses phone_number."
        ),
    )

    # Email is optional now — phone is the identifier.
    email = models.EmailField(unique=True, null=True, blank=True)

    phone_number = models.CharField(
        max_length=20,
        unique=True,
        validators=[IRANIAN_PHONE_REGEX],
        help_text="Iranian mobile number in E.164 form, e.g. +989121234567.",
    )

    shop_name = models.CharField(max_length=255, default="نام فروشگاه")
    shop_website_address = models.URLField(
        max_length=100, default="آدرس وبسایت فروشگاه"
    )
    is_premium = models.BooleanField(default=False)
    first_name = models.CharField(max_length=20, null=True, blank=True)
    last_name = models.CharField(max_length=20, null=True, blank=True)
    website_address = models.URLField(max_length=500, blank=True, null=True)
    position = models.CharField(max_length=50, null=True, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    about_me = models.TextField(blank=True, null=True)

    num_available_sms = models.PositiveIntegerField(
        default=0,
        help_text="Number of SMS credits available. Set manually via admin.",
    )
    

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []  # phone_number is implicit; nothing else is mandatory

    objects = CustomUserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.phone_number
