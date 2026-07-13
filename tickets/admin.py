# tickets/admin.py

from django.contrib import admin

from .models import Message, Thread


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender_type", "sender", "body", "created_at"]
    ordering = ["created_at"]
    can_delete = False


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "tenant_last_seen_at", "created_at"]
    readonly_fields = ["tenant", "created_at", "tenant_last_seen_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "thread", "sender_type", "sender", "created_at"]
    list_filter = ["sender_type"]
    readonly_fields = ["thread", "sender_type", "sender", "body", "created_at"]
    ordering = ["-created_at"]