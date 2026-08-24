from django.core.validators import RegexValidator
from django.db import models


iranian_phone_validator = RegexValidator(
    regex=r"^(?:09[0-9]{9}|\+989[0-9]{9})$",
    message="Enter an Iranian phone number starting with 09 or +989.",
)


class FreeConsult(models.Model):
    phone_number = models.CharField(
        max_length=13,
        validators=[iranian_phone_validator],
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.phone_number
