# from django.contrib import admin
# from django.db.models import Sum, Count
# from django.utils.html import format_html
# from django.urls import reverse
# from django.utils import timezone
# from datetime import timedelta
# from .models import TokenUsage, UserTokenSummary
#
#
# @admin.register(TokenUsage)
# class TokenUsageAdmin(admin.ModelAdmin):
#     list_display = ["user_email", "feature", "tokens", "model_used", "created_at"]
#     list_filter = [
#         "feature",
#         "model_used",
#         "created_at",
#         ("user", admin.RelatedOnlyFieldListFilter),
#     ]
#     search_fields = ["user__email", "operation_description", "request_id"]
#     readonly_fields = [
#         "id",
#         "user",
#         "feature",
#         "operation_description",
#         "tokens",
#         "model_used",
#         "request_id",
#         "created_at",
#     ]
#     date_hierarchy = "created_at"
#     ordering = ["-created_at"]
#
#     def user_email(self, obj):
#         return obj.user.email
#
#     user_email.short_description = "User Email"
#     user_email.admin_order_field = "user__email"
#
#     def has_add_permission(self, request):
#         # Prevent manual addition of token usage records
#         return False
#
#     def has_change_permission(self, request, obj=None):
#         # Make records read-only
#         return False
#
#     def has_delete_permission(self, request, obj=None):
#         # Allow deletion for cleanup
#         return request.user.is_superuser
#
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related("user")
#
#
# @admin.register(UserTokenSummary)
# class UserTokenSummaryAdmin(admin.ModelAdmin):
#     list_display = [
#         "user_email",
#         "total_tokens_used",
#         "total_requests",
#         "chat_tokens",
#         "summarization_tokens",
#         "embedding_tokens",
#         "last_request_at",
#         "updated_at",
#     ]
#     list_filter = ["last_request_at", "updated_at"]
#     search_fields = ["user__email"]
#     readonly_fields = [
#         "user",
#         "total_tokens_used",
#         "chat_tokens",
#         "summarization_tokens",
#         "embedding_tokens",
#         "total_requests",
#         "last_request_at",
#         "created_at",
#         "updated_at",
#     ]
#     ordering = ["-total_tokens_used"]
#
#     def user_email(self, obj):
#         return obj.user.email
#
#     user_email.short_description = "User Email"
#     user_email.admin_order_field = "user__email"
#
#     def has_add_permission(self, request):
#         # Prevent manual addition
#         return False
#
#     def has_change_permission(self, request, obj=None):
#         # Make records read-only
#         return False
#
#     def has_delete_permission(self, request, obj=None):
#         # Allow deletion for cleanup
#         return request.user.is_superuser
#
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related("user")
#
#     actions = ["refresh_summaries"]
#
#     def refresh_summaries(self, request, queryset):
#         """
#         Action to refresh selected user summaries
#         """
#         updated_count = 0
#         for summary in queryset:
#             try:
#                 summary.update_summary()
#                 updated_count += 1
#             except Exception as e:
#                 self.message_user(
#                     request,
#                     f"Error updating summary for {summary.user.email}: {str(e)}",
#                     level="ERROR",
#                 )
#
#         self.message_user(
#             request,
#             f"Successfully refreshed {updated_count} user summaries.",
#             level="SUCCESS",
#         )
#
#     refresh_summaries.short_description = "Refresh selected user summaries"
#
#
# # Custom admin views for analytics dashboard
# class AnalyticsDashboard:
#     """
#     Custom analytics dashboard for admin
#     """
#
#     @staticmethod
#     def get_dashboard_stats():
#         """
#         Get overall analytics statistics
#         """
#         from django.db.models import Sum, Count, Avg
#         from django.contrib.auth import get_user_model
#
#         User = get_user_model()
#
#         # Overall stats
#         total_users = User.objects.count()
#         active_users = TokenUsage.objects.values("user").distinct().count()
#
#         # Token usage stats
#         total_usage = TokenUsage.objects.aggregate(
#             total_tokens=Sum("tokens") or 0,
#             total_requests=Count("id") or 0,
#             avg_tokens_per_request=Avg("tokens") or 0,
#         )
#
#         # Usage by feature
#         feature_stats = {}
#         for feature, feature_name in TokenUsage.FEATURE_CHOICES:
#             stats = TokenUsage.objects.filter(feature=feature).aggregate(
#                 tokens=Sum("tokens") or 0, requests=Count("id") or 0
#             )
#             feature_stats[feature] = {
#                 "name": feature_name,
#                 "tokens": stats["tokens"],
#                 "requests": stats["requests"],
#             }
#
#         # Recent activity (last 7 days)
#         week_ago = timezone.now() - timedelta(days=7)
#         recent_stats = TokenUsage.objects.filter(created_at__gte=week_ago).aggregate(
#             tokens=Sum("tokens") or 0,
#             requests=Count("id") or 0,
#             users=Count("user", distinct=True) or 0,
#         )
#
#         # Top users by token usage
#         top_users = UserTokenSummary.objects.order_by("-total_tokens_used")[:10]
#
#         return {
#             "total_users": total_users,
#             "active_users": active_users,
#             "total_usage": total_usage,
#             "feature_stats": feature_stats,
#             "recent_stats": recent_stats,
#             "top_users": top_users,
#         }
#
#
# # Register custom admin site modifications
# admin.site.site_header = "AI Document Processing - Admin"
# admin.site.site_title = "AI Doc Admin"
# admin.site.index_title = "Administration Dashboard"
