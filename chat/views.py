from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import ChatSession, ChatMessage
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from .serializers import (
    ChatSessionListSerializer,
    ChatSessionSerializer,
    ChatMessageSerializer,
    OnlyChatSessionSerializer,
)
from documents.services.pinecone_service import PineconeEmbedding
from documents.services.openai_service import OpenAIService


class ChatSessionListView(generics.ListAPIView):
    """
    List all chat sessions for the authenticated user with pagination
    """

    serializer_class = ChatSessionListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get base queryset
        base_queryset = ChatSession.objects.filter(
            user=self.request.user, deleted_at__isnull=True
        )
        sessions_count = base_queryset.count()

        # Get pagination parameters
        page = int(self.request.GET.get("page", 1))
        length = int(self.request.GET.get("length", 5))
        skip = self.request.GET.get("skip")

        # Validate length parameter
        if length > 100:
            length = 100
        elif length < 1:
            length = 10

        # Calculate offset
        if skip is not None:
            offset = int(skip)
            current_page = (offset // length) + 1
        else:
            if page < 1:
                page = 1
            offset = (page - 1) * length
            current_page = page

        # Get sessions with custom pagination
        paginated_sessions = base_queryset.order_by("-created_at")[
            offset : offset + length
        ]

        # Calculate pagination metadata
        total_pages = (sessions_count + length - 1) // length  # Ceiling division
        has_next = offset + length < sessions_count
        has_previous = offset > 0

        # Store pagination data for response
        self.pagination_data = {
            "message": "Chat sessions retrieved successfully",
            "statistics": {"total_sessions": sessions_count},
            "sessions": {
                "total_count": sessions_count,
                "page": current_page,
                "length": length,
                "skip": offset,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "results": paginated_sessions,
            },
        }

        return paginated_sessions

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Update the results with serialized data
        self.pagination_data["sessions"]["results"] = serializer.data

        return Response(self.pagination_data, status=status.HTTP_200_OK)


class ChatSessionDetailView(generics.RetrieveAPIView):
    """
    Retrieve details of a specific chat session, including messages and documents.
    """

    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def chat_session_messages(request, session_id):
    """
    Get all messages for a specific chat session, including documents if attached
    """
    try:
        session = get_object_or_404(
            ChatSession, id=session_id, user=request.user, deleted_at__isnull=True
        )
        messages = session.messages.all().order_by("created_at")

        # Serialize and return the session with its messages
        session_data = OnlyChatSessionSerializer(session).data

        return Response(
            {
                "session": session_data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Error retrieving messages: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# @api_view(['POST'])
# @permission_classes([permissions.IsAuthenticated])
# def create_chat_session(request):
#     """
#     Create a new chat session for the user, if not existing
#     """
#     try:
#         title = request.data.get('title', 'New Chat Session')
#         session = ChatSession.objects.create(
#             user=request.user,
#             title=title
#         )
#         return Response({
#             'message': 'Chat session created successfully.',
#             'session': ChatSessionSerializer(session).data
#         }, status=status.HTTP_201_CREATED)

#     except Exception as e:
#         return Response({
#             'error': f'Error creating chat session: {str(e)}'
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatView(generics.CreateAPIView):
    """
    Endpoint to send a message and receive AI response for a chat session
    """

    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        session_id = request.data.get("session_id")
        message = request.data.get("message", "").strip()
        user = request.user

        if not session_id:
            return Response(
                {"error": "session_id is required for chat."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message:
            return Response(
                {"error": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found or you do not have permission to access it."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        openai_service = OpenAIService()
        pinecone_embedding = PineconeEmbedding(namespace=session.namespace)
        # Proceed with saving the message and generating the AI response
        user_message = ChatMessage.objects.create(
            session=session,
            message_type="user",
            content=message,
            token_count=openai_service.count_tokens(message),
        )

        ai_response = "AI response to message..."  # Use your AI service here

        try:
            # Search for relevant context in user's documents
            search_results = pinecone_embedding.similarity_search(message)

            matches = []
            if isinstance(search_results, dict):
                matches = search_results.get("matches", [])
            else:
                matches = getattr(search_results, "matches", []) or []

            context_texts = []
            for m in matches:
                md = getattr(m, "metadata", None) or m.get(
                    "metadata", {}
                )  # handle both
                t = md.get("text")
                if t:
                    context_texts.append(t)

            # Generate response using context
            if context_texts:
                context_text = "\n".join(context_texts)
                llm_response, openai_response = openai_service.generate_answer_by_llm(
                    similarity_text=context_text, user_query=message
                )
            else:
                # No relevant context found, generate general response
                llm_response, openai_response = openai_service.generate_answer_by_llm(
                    similarity_text="No relevant document context found.",
                    user_query=message,
                )

            # Track chat usage for analytics
            # if openai_response:
            #     AnalyticsHelper.log_chat_usage(
            #         user=user, openai_response=openai_response, message_content=message
            #     )

        except Exception as e:
            # Fallback response if RAG fails
            llm_response = f"I'm sorry, I encountered an error while processing your request: {str(e)}"

        assistant_message = ChatMessage.objects.create(
            session=session,
            message_type="assistant",
            content=llm_response,
            token_count=openai_service.count_tokens(llm_response),
        )

        return Response(
            {
                "session_id": session.id,
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
            },
            status=status.HTTP_201_CREATED,
        )
