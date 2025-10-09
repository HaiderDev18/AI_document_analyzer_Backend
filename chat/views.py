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
from documents.services.enhanced_pinecone_service import EnhancedPineconeService
from documents.services.pinecone_service import PineconeEmbedding
from documents.services.openai_service import OpenAIService
from documents.services.hybrid_rag_service import HybridRAGService, format_full_context_prompt
from django.conf import settings


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

        try:
            top_k = int(request.data.get("top_k", 10))
        except Exception:
            top_k = 10
        # Ensure a reasonable minimum for broader coverage
        if top_k < 12:
            top_k = 12
        debug_raw = str(request.data.get("debug", "false")).lower() == "true"

        # Proceed with saving the message and generating the AI response
        user_message = ChatMessage.objects.create(
            session=session,
            message_type="user",
            content=message,
            token_count=openai_service.count_tokens(message),
        )

        ai_response = "AI response to message..."

        # Check if enhanced RAG is enabled
        use_enhanced_rag = getattr(settings, 'USE_ENHANCED_RAG', False)

        try:
            # HYBRID RAG: Check if session has full-context documents
            hybrid_service = HybridRAGService()
            full_context = hybrid_service.get_all_session_context(str(session.id))

            # If cache is empty, check database for full_context mode documents
            if use_enhanced_rag and not full_context:
                full_context_docs = session.documents.filter(
                    processing_mode='full_context',
                    status='completed'
                ).values_list('full_text', flat=True)

                if full_context_docs:
                    full_context = "\n\n" + "="*80 + "\n\n".join(full_context_docs)
                    print(f"[HYBRID RAG] Loaded full context from database (cache was empty)")

            if use_enhanced_rag and full_context:
                # FULL CONTEXT MODE: Small document(s), send entire text as context
                print(f"\n{'='*60}")
                print(f"[FULL CONTEXT MODE] Session: {session.id}")
                print(f"  - Using complete document text as context")
                print(f"  - Context length: {len(full_context):,} chars")
                print(f"  - Query: {message}")
                print(f"{'='*60}\n")

                # Format prompt with full context
                messages = format_full_context_prompt(full_context, message)

                # Get response directly
                llm_response, openai_response = openai_service.client.chat.completions.create(
                    model=openai_service.model,
                    messages=messages
                ), None

                # Extract content
                if hasattr(llm_response, 'choices'):
                    llm_response = llm_response.choices[0].message.content.strip()

                # Create retrieval info for response
                retrieval = [{
                    "mode": "full_context",
                    "context_length": len(full_context),
                    "note": "Entire document sent as context (no embedding search needed)"
                }]

                norm_matches = []  # No matches needed

            elif use_enhanced_rag:
                # NEW: Use smart retrieval with automatic filtering
                print(f"\n{'='*60}")
                print(f"[SMART RETRIEVAL - ENHANCED] Session: {session.id}")
                print(f"[SMART RETRIEVAL] Query: {message}")
                print(f"[SMART RETRIEVAL] Top K: {top_k}")
                print(f"{'='*60}\n")

                pinecone_service = EnhancedPineconeService(
                    namespace=session.namespace,
                    use_semantic_enrichment=True
                )

                # Smart retrieval automatically detects query intent and applies filters
                norm_matches = pinecone_service.smart_retrieval(
                    query=message,
                    top_k=top_k,
                    auto_filter=True
                )

                # Print debug info
                print(f"[SMART RETRIEVAL] Retrieved {len(norm_matches)} matches")
                if debug_raw and norm_matches:
                    for i, m in enumerate(norm_matches[:5]):
                        md = m.get("metadata", {})
                        print(f"  [{i+1}] Score: {m.get('score', 0):.3f}")
                        print(f"      Content Types: {md.get('content_types', [])}")
                        print(f"      Has Amounts: {md.get('has_amounts', False)}")
                        print(f"      Section: {md.get('section', 'N/A')}")
                        print(f"      Text: {md.get('text', '')[:150]}...")
                        print()
            else:
                # OLD: Use classic retrieval (backward compatible)
                print(f"\n[RETRIEVAL - CLASSIC] Session: {session.id}, Query: {message}, Top K: {top_k}")

                pinecone_embedding = PineconeEmbedding(namespace=session.namespace)
                search_results = pinecone_embedding.similarity_search(message, top_k=top_k)

                # Normalize matches
                matches = []
                if isinstance(search_results, dict):
                    matches = search_results.get("matches", [])
                else:
                    matches = getattr(search_results, "matches", []) or []

                # Convert to dict format
                norm_matches = []
                for m in matches:
                    norm_matches.append({
                        "id": getattr(m, "id", None) or m.get("id"),
                        "score": getattr(m, "score", None) or m.get("score"),
                        "metadata": getattr(m, "metadata", None) or m.get("metadata", {})
                    })

                print(f"[RETRIEVAL] Retrieved {len(norm_matches)} matches")


            # Build context from matches (only if not using full context mode)
            if not full_context:
                context_texts = []
                if 'retrieval' not in locals():
                    retrieval = []

                for m in norm_matches:
                    md = m.get("metadata", {})
                    t = md.get("text")
                    if t:
                        context_texts.append(t)
                    # diagnostics record
                    try:
                        retrieval.append(
                            {
                                "score": m.get("score"),
                                "document_id": md.get("document_id"),
                                "chunk_index": md.get("chunk_index"),
                                "section_label": md.get("section_label"),
                                "snippet": (t[:200] + "…") if t and len(t) > 200 else t,
                            }
                        )
                    except Exception:
                        pass
            else:
                # Full context mode - context already used
                context_texts = []

            # When debug is enabled, print unique texts retrieved (deduped by content hash)
            if debug_raw:
                try:
                    seen_hashes = set()
                    unique_prints = []
                    import hashlib as _hashlib
                    for m in norm_matches:
                        md = m.get("metadata", {}) or {}
                        text_val = md.get("text") or ""
                        if not text_val:
                            continue
                        h = _hashlib.sha256(text_val.encode("utf-8")).hexdigest()
                        if h in seen_hashes:
                            continue
                        seen_hashes.add(h)
                        unique_prints.append(
                            {
                                "score": m.get("score"),
                                "document_id": md.get("document_id"),
                                "section_label": md.get("section_label"),
                                "chunk_index": md.get("chunk_index"),
                                "len": len(text_val),
                                "text": text_val,
                            }
                        )
                    print(f"[RAG] Unique texts from similarity_search: {len(unique_prints)}")
                    for i, item in enumerate(unique_prints):
                        snippet = item["text"]
                        snippet = (snippet[:800] + "…") if len(snippet) > 800 else snippet
                        print(
                            f"    [{i}] score={item['score']} doc={item['document_id']} section={item['section_label']} idx={item['chunk_index']} len={item['len']}\n      {snippet}"
                        )
                except Exception:
                    pass

            try:
                print(
                    f"[RAG] Summary: session={session.id} msg_len={len(message)} unique={len(norm_matches)}"
                )
            except Exception:
                pass

            # Generate response using context (skip if already done in full context mode)
            if not full_context:
                if context_texts:
                    context_text = "\n".join(context_texts)
                    if debug_raw:
                        try:
                            print("[RAG] Context passed to LLM:")
                            print(f"  total_chars={len(context_text)} total_chunks={len(context_texts)}")
                            head = context_text[:400]
                            tail = context_text[-400:] if len(context_text) > 400 else ""
                            print("  --- BEGIN CONTEXT HEAD ---\n" + head + "\n  --- END CONTEXT HEAD ---")
                            if tail:
                                print("  --- BEGIN CONTEXT TAIL ---\n" + tail + "\n  --- END CONTEXT TAIL ---")
                        except Exception:
                            pass
                    llm_response, openai_response = openai_service.generate_answer_by_llm(
                        similarity_text=context_text, user_query=message
                    )
                else:
                    # Log when no relevant context found
                    try:
                        print(
                            f"[RAG] No relevant context found for session={session.id}; sending fallback context."
                        )
                    except Exception:
                        pass
                    # No relevant context found, generate general response
                    llm_response, openai_response = openai_service.generate_answer_by_llm(
                        similarity_text="No relevant document context found.",
                        user_query=message,
                    )
            # else: llm_response already set in full context mode

            # Track chat usage for analytics
            # if openai_response:
            #     AnalyticsHelper.log_chat_usage(
            #         user=user, openai_response=openai_response, message_content=message
            #     )

        except Exception as e:
            # Fallback response if RAG fails
            try:
                print(f"[RAG] ERROR: {e}")
            except Exception:
                pass
            llm_response = f"I'm sorry, I encountered an error while processing your request: {str(e)}"

        assistant_message = ChatMessage.objects.create(
            session=session,
            message_type="assistant",
            content=llm_response,
            token_count=openai_service.count_tokens(llm_response),
        )

        resp_payload = {
            "session_id": session.id,
            "user_message": ChatMessageSerializer(user_message).data,
            "assistant_message": ChatMessageSerializer(assistant_message).data,
            "retrieval": {
                "namespace": session.namespace,
                "mode": "full_context" if full_context else "embeddings",
                "top_k": top_k if not full_context else None,
                "matches": retrieval,
                "smart_retrieval_enabled": True,
            },
        }
        if debug_raw:
            # include context text and enhanced metadata
            try:
                if full_context:
                    resp_payload["full_context_length"] = len(full_context)
                else:
                    resp_payload["similarity_text"] = context_text if context_texts else None
            except Exception:
                resp_payload["similarity_text"] = None

            if not full_context:
                resp_payload["enhanced_metadata"] = {
                    "total_matches": len(norm_matches),
                    "matches_with_semantic": sum(1 for m in norm_matches if m.get("metadata", {}).get("content_types")),
                }

        return Response(
            resp_payload,
            status=status.HTTP_201_CREATED,
        )
