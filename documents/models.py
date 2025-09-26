import uuid
from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class DocumentQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class AliveManager(models.Manager):
    def get_queryset(self):
        return DocumentQuerySet(self.model, using=self._db).alive()


class Document(models.Model):
    """Metadata for an uploaded document (hot path)."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)

    # File metadata (actual bytes are in FileAsset)
    file_name = models.CharField(max_length=255)
    file_ext = models.CharField(max_length=16, blank=True)
    file_mime = models.CharField(max_length=128, blank=True)
    file_size = models.PositiveIntegerField()  # bytes
    checksum = models.CharField(max_length=64, db_index=True, blank=True)  # sha256

    # Relations
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    session = models.ForeignKey(
        "chat.ChatSession",
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )

    # Processing
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    processing_error = models.TextField(blank=True)

    # Lightweight, value-added outputs (keep small; no raw_text stored)
    summary = models.TextField(blank=True)
    risk_factors = models.JSONField(default=dict, blank=True)

    # Timestamps & soft delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AliveManager()  # default excludes soft-deleted
    all_objects = models.Manager()  # includes soft-deleted

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # one live document per (user, session, file_name)
            models.UniqueConstraint(
                fields=["user", "session", "file_name"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_live_doc_per_session_name",
            )
        ]
        indexes = [
            models.Index(fields=["user", "session", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        sess = getattr(self.session, "title", None) or "No Session"
        return f"{self.title} — Session: {sess}"

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class FileAsset(models.Model):
    """Raw/original bytes stored in DB (archival + reprocessing)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="asset"
    )
    blob = models.BinaryField()  # original file bytes
    size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=128, blank=True)
    checksum = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["checksum"])]
