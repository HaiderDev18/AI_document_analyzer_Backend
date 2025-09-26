# documents/admin.py
from django.contrib import admin
from .models import Document, FileAsset


class FileAssetInline(admin.StackedInline):
    model = FileAsset
    can_delete = False
    extra = 0
    fields = ("size", "mime_type", "checksum")
    readonly_fields = ("size", "mime_type", "checksum")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "file_name",
        "file_ext",
        "file_mime",
        "file_size",
        "status",
        "user",
        "session",
        "created_at",
    )
    list_filter = ("status", "file_ext", "file_mime", "created_at")
    search_fields = (
        "title",
        "file_name",
        "user__username",
        "user__email",
        "session__title",
    )
    readonly_fields = ("checksum", "processing_error", "created_at", "updated_at")
    inlines = [FileAssetInline]
    ordering = ("-created_at",)
