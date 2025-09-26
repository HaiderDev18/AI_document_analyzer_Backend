from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class ChatSession(models.Model):
    """
    Model to store chat sessions
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_sessions"
    )
    title = models.CharField(max_length=255, blank=True)
    namespace = models.CharField(
        max_length=100, unique=True
    )  # Unique namespace for Pinecone
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.namespace:
            # Create unique namespace using session ID
            self.namespace = f"session_{str(self.id).replace('-', '_')}"

        if not self.title:
            # Always use current time for title
            self.title = f"Session {timezone.now().strftime('%Y-%m-%d %H:%M')}"

        super().save(*args, **kwargs)

        # Set title after save if it's not set
        if not self.title:
            self.title = f"Session {self.created_at.strftime('%Y-%m-%d %H:%M')}"
            # Update without calling save again to avoid recursion
            ChatSession.objects.filter(id=self.id).update(title=self.title)

    def __str__(self):
        return f"Session {self.title} - {self.user.email}"

    @property
    def has_documents(self):
        return self.documents.exists()

    @property
    def document_count(self):
        return self.documents.count()

    class Meta:
        ordering = ["-created_at"]


class ChatMessage(models.Model):
    """
    Simplified model to store individual chat messages
    """

    MESSAGE_TYPES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="messages"
    )
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()

    # Metadata
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."
