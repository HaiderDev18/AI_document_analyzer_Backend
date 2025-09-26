# from django.db import models
# from django.conf import settings
#
# # from django.utils import timezone
# from django.contrib.auth import get_user_model
# import uuid
#
# User = get_user_model()
#
#
# class TokenUsage(models.Model):
#     """
#     Model to track OpenAI token usage per user and per feature
#     """
#
#     FEATURE_CHOICES = [
#         ("chat", "Chat"),
#         ("summarization", "Document Summarization"),
#         ("embedding", "Text Embedding"),
#     ]
#
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="token_usage")
#
#     # Feature/Operation details
#     feature = models.CharField(max_length=20, choices=FEATURE_CHOICES)
#     operation_description = models.CharField(max_length=255, blank=True)
#
#     # Token usage from OpenAI response
#     tokens = models.PositiveIntegerField(default=0)
#
#     # OpenAI API details
#     model_used = models.CharField(max_length=50, blank=True)
#     request_id = models.CharField(
#         max_length=100, blank=True
#     )  # OpenAI request ID if available
#
#     # Timestamps
#     created_at = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return f"{self.user.email} - {self.feature} - {self.tokens} tokens"
#
#     class Meta:
#         ordering = ["-created_at"]
#
#
# class UserTokenSummary(models.Model):
#     """
#     Model to store aggregated token usage per user (updated periodically)
#     """
#
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     user = models.OneToOneField(
#         User, on_delete=models.CASCADE, related_name="token_summary"
#     )
#
#     # Total usage across all features
#     total_tokens_used = models.PositiveBigIntegerField(default=0)
#
#     # Usage by feature
#     chat_tokens = models.PositiveBigIntegerField(default=0)
#     summarization_tokens = models.PositiveBigIntegerField(default=0)
#     embedding_tokens = models.PositiveBigIntegerField(default=0)
#
#     # Usage tracking
#     total_requests = models.PositiveIntegerField(default=0)
#     last_request_at = models.DateTimeField(null=True, blank=True)
#
#     # Timestamps
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return f"{self.user.email} - {self.total_tokens_used} total tokens"
#
#     def update_summary(self):
#         """
#         Update summary from TokenUsage records
#         """
#         from django.db.models import Sum, Count, Max
#
#         # Get aggregated data
#         usage_data = TokenUsage.objects.filter(user=self.user).aggregate(
#             total_tokens=Sum("tokens"),
#             total_requests=Count("id"),
#             last_request=Max("created_at"),
#         )
#
#         # Get usage by feature
#         feature_usage = {}
#         for feature, _ in TokenUsage.FEATURE_CHOICES:
#             tokens = TokenUsage.objects.filter(
#                 user=self.user, feature=feature
#             ).aggregate(total=Sum("tokens"))["total"]
#             feature_usage[f"{feature}_tokens"] = tokens or 0
#
#         # Update fields - handle None values properly
#         self.total_tokens_used = usage_data["total_tokens"] or 0
#         self.total_requests = usage_data["total_requests"] or 0
#         self.last_request_at = usage_data["last_request"]  # Can be None
#
#         # Update feature-specific usage
#         self.chat_tokens = feature_usage.get("chat_tokens", 0)
#         self.summarization_tokens = feature_usage.get("summarization_tokens", 0)
#         self.embedding_tokens = feature_usage.get("embedding_tokens", 0)
#
#         self.save()
