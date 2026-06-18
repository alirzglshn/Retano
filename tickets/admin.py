from django.contrib import admin
from .models import Ticket , TicketMessage  


# Register your models here.
 

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "subject",
        "user",
        "status",
        "priority",
        "created_at",
    )
    list_filter = ("status" , "priority" , "created_at",)
    search_fields = ("subject" , "user__username" , "user__email",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at" , "updated_at",)
    

@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket" , "user" , "is_staff_reply" , "created_at",)
    list_filter = ("is_staff_reply" , "created_at",)
    search_fields = ("message" , "user__username",)
    ordering = ("created_at",)
    
# @admin.register(TicketCategory)
# class TicketCategoryAdmin(admin.ModelAdmin):
#     list_display = ("name",)
    

# @admin.register(TicketAttachment)
# class TicketAttachmentAdmin(admin.ModelAdmin):
#     list_display = ("message" , "uploaded_at")
    