# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):

    email = models.EmailField(unique=True)
    shop_name = models.CharField(max_length=255, default="نام فروشگاه")
    shop_website_address = models.URLField(
        max_length=100, default="آدرس وبسایت فروشگاه"
    )
    is_premium = models.BooleanField(default=False)
    first_name = models.CharField(max_length=20, null=True, blank=True)
    last_name = models.CharField(max_length=20, null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    website_address = models.URLField(max_length=500, blank=True, null=True)
    position = models.CharField(max_length=50, null=True, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    about_me = models.TextField(blank=True, null=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
