from django.contrib import admin

from .models import Bill, BillingConstant


@admin.register(BillingConstant)
class BillingConstantAdmin(admin.ModelAdmin):
    fields = [
        "sms_unit_price",
        "discount_percentage_1000",
        "discount_percentage_5000",
        "discount_percentage_25000",
        "discount_percentage_60000",
        "discount_percentage_150000",
        "discount_percentage_300000",
        "discount_percentage_500000",
        "privileges",
    ]

    def has_add_permission(self, request):
        return not BillingConstant.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = [
        "billing_id",
        "tenant",
        "sms_count",
        "actual_price",
        "discount_percentage",
        "final_price",
        "status",
    ]
    list_editable = ["status"]
    list_filter = ["status", "sms_count", "tenant"]
    search_fields = [
        "billing_id",
        "tenant__owner__phone_number",
        "tenant__owner__shop_name",
    ]
    list_select_related = ["tenant", "tenant__owner"]
    ordering = ["-id"]
    raw_id_fields = ["tenant"]
    fields = [
        "billing_id",
        "tenant",
        "sms_count",
        "sms_unit_price",
        "discount_percentage",
        "actual_price",
        "discount_amount",
        "final_price",
        "status",
        "card_number",
        "bale_id",
    ]

    calculated_fields = (
        "billing_id",
        "sms_unit_price",
        "discount_percentage",
        "actual_price",
        "discount_amount",
        "final_price",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = set(self.calculated_fields)
        if obj is None:
            readonly_fields.add("status")
        else:
            readonly_fields.add("tenant")
            if obj.status == Bill.Status.PAID:
                readonly_fields.add("sms_count")
        if not request.user.is_superuser:
            readonly_fields.update({"card_number", "bale_id"})
        return tuple(readonly_fields)
