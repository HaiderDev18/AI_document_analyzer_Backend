# from django.shortcuts import render
# from rest_framework import generics, permissions, status
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.response import Response
# from django.utils import timezone
# from datetime import timedelta
# from django.db.models import Sum, Count
# from .models import TokenUsage, UserTokenSummary
# from .serializers import (
#     TokenUsageSerializer,
#     UserTokenSummarySerializer,
#     TokenUsageStatsSerializer,
# )
# from .services import TokenUsageTracker
#
#
# class UserTokenSummaryView(generics.RetrieveAPIView):
#     """
#     Get current user's token usage summary
#     """
#
#     serializer_class = UserTokenSummarySerializer
#     permission_classes = [permissions.IsAuthenticated]
#
#     def get_object(self):
#         """
#         Get or create user token summary
#         """
#         summary, created = UserTokenSummary.objects.get_or_create(
#             user=self.request.user
#         )
#         if (
#             created
#             or not summary.updated_at
#             or (timezone.now() - summary.updated_at).total_seconds() > 3600
#         ):  # Update if older than 1 hour
#             summary.update_summary()
#         return summary
#
#
# class UserTokenUsageListView(generics.ListAPIView):
#     """
#     List current user's token usage history
#     """
#
#     serializer_class = TokenUsageSerializer
#     permission_classes = [permissions.IsAuthenticated]
#
#     def get_queryset(self):
#         """
#         Return token usage for current user only
#         """
#         return TokenUsage.objects.filter(user=self.request.user).order_by("-created_at")
#
#
# @api_view(["GET"])
# @permission_classes([permissions.IsAuthenticated])
# def user_token_stats(request):
#     """
#     Get detailed token usage statistics for current user
#     """
#     user = request.user
#     days = int(request.GET.get("days", 30))  # Default to 30 days
#
#     # Calculate date range
#     end_date = timezone.now()
#     start_date = end_date - timedelta(days=days)
#
#     # Get token usage in the specified period
#     usage_queryset = TokenUsage.objects.filter(
#         user=user, created_at__gte=start_date, created_at__lte=end_date
#     )
#
#     # Calculate statistics
#     total_stats = usage_queryset.aggregate(
#         total_tokens=Sum("tokens"), total_requests=Count("id")
#     )
#
#     # Feature breakdown
#     feature_breakdown = {}
#     for feature_choice in TokenUsage.FEATURE_CHOICES:
#         feature_code = feature_choice[0]
#         feature_tokens = (
#             usage_queryset.filter(feature=feature_code).aggregate(tokens=Sum("tokens"))[
#                 "tokens"
#             ]
#             or 0
#         )
#         feature_breakdown[feature_code] = feature_tokens
#
#     # Model breakdown
#     model_breakdown = {}
#     model_stats = (
#         usage_queryset.values("model_used")
#         .annotate(tokens=Sum("tokens"))
#         .order_by("-tokens")
#     )
#
#     for stat in model_stats:
#         if stat["model_used"]:
#             model_breakdown[stat["model_used"]] = stat["tokens"]
#
#     # Daily usage for the period
#     daily_usage = []
#     current_date = start_date.date()
#     while current_date <= end_date.date():
#         day_usage = (
#             usage_queryset.filter(created_at__date=current_date).aggregate(
#                 tokens=Sum("tokens")
#             )["tokens"]
#             or 0
#         )
#
#         daily_usage.append({"date": current_date.isoformat(), "tokens": day_usage})
#         current_date += timedelta(days=1)
#
#     # Prepare response data
#     stats_data = {
#         "total_tokens": total_stats["total_tokens"] or 0,
#         "total_requests": total_stats["total_requests"] or 0,
#         "feature_breakdown": feature_breakdown,
#         "model_breakdown": model_breakdown,
#         "daily_usage": daily_usage,
#         "period_start": start_date,
#         "period_end": end_date,
#     }
#
#     serializer = TokenUsageStatsSerializer(stats_data)
#     return Response(serializer.data, status=status.HTTP_200_OK)
#
#
# @api_view(["GET"])
# @permission_classes([permissions.IsAuthenticated])
# def refresh_user_summary(request):
#     """
#     Manually refresh user's token usage summary
#     """
#     user = request.user
#
#     # Get or create summary
#     summary, created = UserTokenSummary.objects.get_or_create(user=user)
#
#     # Force update
#     summary.update_summary()
#
#     serializer = UserTokenSummarySerializer(summary)
#     return Response(
#         {
#             "message": "Token usage summary refreshed successfully",
#             "summary": serializer.data,
#         },
#         status=status.HTTP_200_OK,
#     )
