from rest_framework import serializers
from .models import ChatSession, ChatMessage
from documents.models import Document
# from documents.serializers import DocumentSerializer


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for individual ChatMessage model.
    """

    class Meta:
        model = ChatMessage
        fields = ["id", "message_type", "content", "token_count", "created_at"]
        read_only_fields = ["id", "token_count", "created_at"]


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for Document model attached to the session.
    """

    class Meta:
        model = Document
        fields = ["id", "title", "file_name", "file_size", "status"]


class ChatSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for ChatSession model with messages and documents.
    """

    messages = ChatMessageSerializer(many=True, read_only=True)
    documents = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()
    document_count = serializers.ReadOnlyField()
    has_documents = serializers.ReadOnlyField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "namespace",
            "message_count",
            "document_count",
            "has_documents",
            "created_at",
            "updated_at",
            "messages",
            "documents",
        ]
        read_only_fields = ["id", "namespace", "created_at", "updated_at"]

    def get_message_count(self, obj):
        """Returns the count of messages in the session."""
        return obj.messages.count()

    def get_documents(self, obj):
        """
        Returns documents associated with the session.
        If no documents, return an empty list.
        """
        if obj.has_documents:
            documents = obj.documents.all()
            return DocumentSerializer(documents, many=True).data
        return []


class OnlyChatSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for ChatSession model with messages and documents.
    """

    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    # documents = serializers.SerializerMethodField()
    # document_count = serializers.ReadOnlyField()
    # has_documents = serializers.ReadOnlyField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "namespace",
            "message_count",
            "created_at",
            "updated_at",
            "messages",
        ]
        read_only_fields = ["id", "namespace", "created_at", "updated_at"]

    def get_message_count(self, obj):
        """Returns the count of messages in the session."""
        return obj.messages.count()


class ChatSessionListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing chat sessions (without messages or documents details).
    """

    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "created_at",
            "updated_at",
            "message_count",
            "last_message",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        """Get the last message of the session."""
        last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            return {
                "content": last_msg.content[:100]
                + ("..." if len(last_msg.content) > 100 else ""),
                "message_type": last_msg.message_type,
                "created_at": last_msg.created_at,
            }
        return None


class SessionSerializer(serializers.ModelSerializer):
    """
    Simple serializer for session information only.
    Used for document-related operations and basic session info.
    """

    document_count = serializers.ReadOnlyField()
    has_documents = serializers.ReadOnlyField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "namespace",
            "document_count",
            "has_documents",
            "created_at",
        ]
        read_only_fields = ["id", "namespace", "created_at"]
