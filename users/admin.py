from django.contrib import admin

from .models import OTP, CustomUser

# Register your models here.

admin.site.register(CustomUser)


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ["otp_code", "created_at"]
    readonly_fields = ["otp_code", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self, request):
        OTP.objects.purge_expired()
        return super().get_queryset(request).active()

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
