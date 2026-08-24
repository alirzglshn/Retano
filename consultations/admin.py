from django.contrib import admin

from .models import FreeConsult


@admin.register(FreeConsult)
class FreeConsultAdmin(admin.ModelAdmin):
    list_display = ["id", "phone_number"]
    search_fields = ["phone_number"]
    ordering = ["id"]
    list_per_page = 50

    def has_module_permission(self, request):
        return self._is_superuser(request)

    def has_view_permission(self, request, obj=None):
        return self._is_superuser(request)

    def has_add_permission(self, request):
        return self._is_superuser(request)

    def has_change_permission(self, request, obj=None):
        return self._is_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_superuser(request)

    @staticmethod
    def _is_superuser(request):
        return bool(
            request.user
            and request.user.is_active
            and request.user.is_superuser
        )
