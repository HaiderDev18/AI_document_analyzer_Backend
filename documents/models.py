from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class Document(models.Model):
    """
    Model to store uploaded documents
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    raw_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    # file
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_type = models.CharField(max_length=10, null=True, blank=True)
    file_size = models.PositiveIntegerField()  # in bytes
    # relations
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    session = models.ForeignKey(
        "chat.ChatSession",
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )

    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_processed = models.BooleanField(default=False)

    # Extracted content
    risk_factors = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # For soft delete

    def __str__(self):
        return f"{self.title} - Session: {self.session.title if self.session else 'No Session'}"

    def soft_delete(self):
        """Soft delete the document"""
        self.deleted_at = timezone.now()
        self.save()

    def is_deleted(self):
        """Check if document is soft deleted"""
        return self.deleted_at is not None

    class Meta:
        ordering = ["-created_at"]
