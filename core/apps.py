# core/apps.py

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):

        # Registers TenantSyncAPIKeySchemeExtension with drf-spectacular's extension registry 
        from core import openapi_extensions  # noqa: F401


