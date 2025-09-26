from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Admin interface for Document model
    """

    list_display = (
        "title",
        "file_name",
        "user",
        "file_type",
        "get_file_size",
        "status",
        "created_at",
        "is_deleted",
    )
    list_filter = ("status", "file_type", "created_at", "deleted_at")
    search_fields = ("title", "file_name", "user__email", "user__username")
    readonly_fields = (
        "id",
        "file_size",
        "raw_text",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "user", "title", "file_name", "file_path")},
        ),
        ("File Details", {"fields": ("file_type", "file_size", "status")}),
        ("Content", {"fields": ("raw_text", "summary"), "classes": ("collapse",)}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "deleted_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_file_size(self, obj):
        """Display file size in human readable format"""
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    get_file_size.short_description = "File Size"

    def is_deleted(self, obj):
        """Display if document is soft deleted"""
        return obj.is_deleted()

    is_deleted.boolean = True
    is_deleted.short_description = "Deleted"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")
