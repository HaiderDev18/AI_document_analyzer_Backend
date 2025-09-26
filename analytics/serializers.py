# from rest_framework import serializers
# from .models import TokenUsage, UserTokenSummary
#
#
# class TokenUsageSerializer(serializers.ModelSerializer):
#     """
#     Serializer for individual token usage records
#     """
#
#     user_email = serializers.CharField(source="user.email", read_only=True)
#
#     class Meta:
#         model = TokenUsage
#         fields = [
#             "id",
#             "user_email",
#             "feature",
#             "operation_description",
#             "tokens",
#             "model_used",
#             "request_id",
#             "created_at",
#         ]
#         read_only_fields = ["id", "created_at"]
#
#
# class UserTokenSummarySerializer(serializers.ModelSerializer):
#     """
#     Serializer for user token usage summary
#     """
#
#     user_email = serializers.CharField(source="user.email", read_only=True)
#     username = serializers.CharField(source="user.username", read_only=True)
#
#     class Meta:
#         model = UserTokenSummary
#         fields = [
#             "user_email",
#             "username",
#             "total_tokens_used",
#             "chat_tokens",
#             "summarization_tokens",
#             "embedding_tokens",
#             "total_requests",
#             "last_request_at",
#             "created_at",
#             "updated_at",
#         ]
#         read_only_fields = ["created_at", "updated_at"]
#
#
# class TokenUsageStatsSerializer(serializers.Serializer):
#     """
#     Serializer for token usage statistics
#     """
#
#     total_tokens = serializers.IntegerField()
#     total_requests = serializers.IntegerField()
#     feature_breakdown = serializers.DictField()
#     model_breakdown = serializers.DictField()
#     daily_usage = serializers.ListField()
#     period_start = serializers.DateTimeField()
#     period_end = serializers.DateTimeField()
