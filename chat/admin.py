from django.contrib import admin
from django.utils.html import format_html
from .models import ChatSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    """
    Inline admin for ChatMessage
    """

    model = ChatMessage
    extra = 0
    readonly_fields = ("id", "token_count", "created_at")
    fields = ("message_type", "content", "token_count", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("created_at")


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """
    Admin interface for ChatSession model
    """

    list_display = ["id", "user", "title", "created_at", "updated_at", "deleted_at"]
    list_filter = ["created_at", "updated_at", "deleted_at"]
    search_fields = ["user__email", "user__username", "title"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
    inlines = [ChatMessageInline]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "user", "title")}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "deleted_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_message_count(self, obj):
        """Display the number of messages in the session"""
        return obj.messages.count()

    get_message_count.short_description = "Messages"

    def is_deleted(self, obj):
        """Display if session is soft deleted"""
        return obj.deleted_at is not None

    is_deleted.boolean = True
    is_deleted.short_description = "Deleted"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .prefetch_related("messages")
        )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """
    Admin interface for simplified ChatMessage model
    """

    list_display = [
        "id",
        "message_type",
        "session",
        "get_content_preview",
        "token_count",
        "created_at",
    ]
    list_filter = ["message_type", "created_at", "session__user"]
    search_fields = ("content", "session__title", "session__user__email")
    readonly_fields = ("id", "token_count", "created_at")
    ordering = ["-created_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "session", "message_type")}),
        ("Content", {"fields": ("content",)}),
        (
            "Metadata",
            {"fields": ("token_count", "created_at"), "classes": ("collapse",)},
        ),
    )

    def get_content_preview(self, obj):
        """Display a preview of the message content"""
        preview = obj.content[:100]
        if len(obj.content) > 100:
            preview += "..."
        return preview

    get_content_preview.short_description = "Content Preview"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("session", "session__user")
