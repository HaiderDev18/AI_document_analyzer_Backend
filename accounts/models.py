from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid
import datetime


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser
    """

    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Admin"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    # Temporarily use default instead of auto_now_add for migration
    created_at = models.DateTimeField(auto_now_add=True)

    # Pinecone namespace for user's documents and chat
    pinecone_namespace = models.CharField(max_length=100, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    def save(self, *args, **kwargs):
        # If created_at is not set and this is an existing record, use date_joined
        if not self.created_at and self.date_joined:
            self.created_at = self.date_joined
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} - {self.get_full_name()} ({self.role})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_or_create_namespace(self):
        """Get or create unique Pinecone namespace for user"""
        if not self.pinecone_namespace:
            # Create unique namespace using user ID and UUID
            self.pinecone_namespace = f"user_{self.id}_{str(uuid.uuid4())[:8]}"
            self.save()
        return self.pinecone_namespace

    @property
    def is_admin_user(self):
        return self.role == "admin"

    class Meta:
        db_table = "auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"


class UserProfile(models.Model):
    """
    Extended user profile information
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profile"
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.email}'s Profile"
