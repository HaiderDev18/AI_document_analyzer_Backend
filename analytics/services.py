# from django.contrib.auth import get_user_model
# from django.utils import timezone
# from .models import TokenUsage, UserTokenSummary
# import logging
#
# User = get_user_model()
# logger = logging.getLogger(__name__)
#
#
# class TokenUsageTracker:
#     """
#     Service to track OpenAI token usage
#     """
#
#     @staticmethod
#     def log_usage(
#         user, feature, openai_response, operation_description="", model_used=""
#     ):
#         """
#         Log token usage from OpenAI API response
#
#         Args:
#             user: User instance
#             feature: Feature name (must be in TokenUsage.FEATURE_CHOICES)
#             openai_response: OpenAI API response object
#             operation_description: Description of the operation
#             model_used: OpenAI model used
#         """
#         try:
#             # Extract token usage from OpenAI response
#             usage_data = TokenUsageTracker._extract_usage_from_response(openai_response)
#
#             if not usage_data:
#                 logger.warning(
#                     f"Could not extract token usage from OpenAI response for user {user.email}"
#                 )
#                 return None
#
#             # Create token usage record
#             token_usage = TokenUsage.objects.create(
#                 user=user,
#                 feature=feature,
#                 operation_description=operation_description,
#                 tokens=usage_data.get("total_tokens", 0),
#                 model_used=model_used or usage_data.get("model", ""),
#                 request_id=usage_data.get("request_id", ""),
#             )
#
#             # Update user summary
#             TokenUsageTracker._update_user_summary(user)
#
#             logger.info(
#                 f"Logged token usage: {token_usage.tokens} tokens for {user.email} - {feature}"
#             )
#             return token_usage
#
#         except Exception as e:
#             logger.error(f"Error logging token usage for user {user.email}: {str(e)}")
#             return None
#
#     @staticmethod
#     def _extract_usage_from_response(response):
#         """
#         Extract token usage data from different types of OpenAI responses
#         """
#         try:
#             usage_data = {}
#
#             # Handle different response formats
#             if hasattr(response, "usage"):
#                 # Standard chat/completion response
#                 usage = response.usage
#                 usage_data = {
#                     "total_tokens": getattr(usage, "total_tokens", 0),
#                 }
#             elif hasattr(response, "data") and hasattr(response, "usage"):
#                 # Embedding response
#                 usage = response.usage
#                 usage_data = {
#                     "total_tokens": getattr(usage, "total_tokens", 0),
#                 }
#             elif isinstance(response, dict):
#                 # Dictionary response
#                 if "usage" in response:
#                     usage = response["usage"]
#                     usage_data = {
#                         "total_tokens": usage.get("total_tokens", 0),
#                     }
#
#             # Add model and request ID if available
#             if hasattr(response, "model"):
#                 usage_data["model"] = response.model
#             elif isinstance(response, dict) and "model" in response:
#                 usage_data["model"] = response["model"]
#
#             if hasattr(response, "id"):
#                 usage_data["request_id"] = response.id
#             elif isinstance(response, dict) and "id" in response:
#                 usage_data["request_id"] = response["id"]
#
#             return usage_data if usage_data else None
#
#         except Exception as e:
#             logger.error(f"Error extracting usage from OpenAI response: {str(e)}")
#             return None
#
#     @staticmethod
#     def _update_user_summary(user):
#         """
#         Update or create user token summary
#         """
#         try:
#             summary, created = UserTokenSummary.objects.get_or_create(user=user)
#             summary.update_summary()
#
#         except Exception as e:
#             logger.error(f"Error updating user summary for {user.email}: {str(e)}")
#
#     @staticmethod
#     def get_user_usage_stats(user, days=30):
#         """
#         Get user usage statistics for the last N days
#         """
#         from django.utils import timezone
#         from datetime import timedelta
#         from django.db.models import Sum, Count
#
#         try:
#             start_date = timezone.now() - timedelta(days=days)
#
#             # Get usage for the period
#             usage_stats = TokenUsage.objects.filter(
#                 user=user, created_at__gte=start_date
#             ).aggregate(
#                 total_tokens=Sum("tokens") or 0, total_requests=Count("id") or 0
#             )
#
#             # Get usage by feature
#             feature_stats = {}
#             for feature, feature_name in TokenUsage.FEATURE_CHOICES:
#                 feature_usage = TokenUsage.objects.filter(
#                     user=user, feature=feature, created_at__gte=start_date
#                 ).aggregate(tokens=Sum("tokens") or 0, requests=Count("id") or 0)
#                 feature_stats[feature] = {
#                     "name": feature_name,
#                     "tokens": feature_usage["tokens"],
#                     "requests": feature_usage["requests"],
#                 }
#
#             return {
#                 "period_days": days,
#                 "total_stats": usage_stats,
#                 "feature_stats": feature_stats,
#                 "start_date": start_date,
#             }
#
#         except Exception as e:
#             logger.error(f"Error getting usage stats for {user.email}: {str(e)}")
#             return None
#
#
# class AnalyticsHelper:
#     """
#     Helper methods for analytics operations
#     """
#
#     @staticmethod
#     def log_chat_usage(user, openai_response, message_content=""):
#         """
#         Convenience method to log chat token usage
#         """
#         return TokenUsageTracker.log_usage(
#             user=user,
#             feature="chat",
#             openai_response=openai_response,
#             operation_description=f"Chat message: {message_content[:100]}...",
#         )
#
#     @staticmethod
#     def log_summarization_usage(user, openai_response, document_title=""):
#         """
#         Convenience method to log document summarization usage
#         """
#         return TokenUsageTracker.log_usage(
#             user=user,
#             feature="summarization",
#             openai_response=openai_response,
#             operation_description=f"Document summarization: {document_title}",
#         )
#
#     @staticmethod
#     def log_embedding_usage(user, openai_response, text_length=0):
#         """
#         Convenience method to log embedding generation usage
#         """
#         return TokenUsageTracker.log_usage(
#             user=user,
#             feature="embedding",
#             openai_response=openai_response,
#             operation_description=f"Text embedding generation ({text_length} chars)",
#         )
#
#     @staticmethod
#     def log_rag_usage(user, openai_response, session_id, query=""):
#         """
#         Convenience method to log RAG query usage
#         """
#         return TokenUsageTracker.log_usage(
#             user=user,
#             feature="rag_query",
#             openai_response=openai_response,
#             operation_description=f"RAG query: {query[:100]}...",
#             session_id=session_id,
#         )
