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

        try:
            # Search for relevant context in user's documents
            # Primary semantic search
            search_results = pinecone_embedding.similarity_search(message, top_k=top_k)

            matches = []
            raw_primary = []
            if isinstance(search_results, dict):
                matches = search_results.get("matches", [])
            else:
                matches = getattr(search_results, "matches", []) or []
            # capture raw primary
            try:
                for m in matches:
                    raw_primary.append(
                        {
                            "id": getattr(m, "id", None) or m.get("id"),
                            "score": getattr(m, "score", None) or m.get("score"),
                            "metadata": getattr(m, "metadata", None)
                            or m.get("metadata", {}),
                        }
                    )
            except Exception:
                pass
            debug_raw = True
            if debug_raw:
                try:
                    print("[RAG] Primary retrieval:")
                    print(f"  session={session.id} top_k={top_k} message={message!r}")
                    print(f"  primary_matches={len(raw_primary)}")
                    for i, r in enumerate(raw_primary[:10]):
                        md = r.get("metadata", {}) or {}
                        snippet = md.get("text") or ""
                        snippet = (snippet[:200] + "…") if len(snippet) > 200 else snippet
                        print(
                            f"    [{i}] id={r.get('id')} score={r.get('score')} section={md.get('section_label')} doc={md.get('document_id')} idx={md.get('chunk_index')}\n      {snippet}"
                        )
                except Exception:
                    pass

            # Keyword-triggered secondary searches (hybrid-ish retrieval)
            import re as _re
            secondary_terms = []
            if _re.search(r"sum|amount|payment|pay|price|total|completion|cost|value", message, _re.I):
                secondary_terms.extend([
                    "Subcontract sum",
                    "Subcontract sum amount",
                    "total subcontract value",
                    "contractor shall pay",
                    "VAT exclusive sum",
                ])
            if _re.search(r"retention|holdback|withhold|percentage", message, _re.I):
                secondary_terms.append("Retention percentage")

            raw_secondary = []
            for term in secondary_terms:
                try:
                    extra_res = pinecone_embedding.similarity_search(term, top_k=5)
                    extra_matches = (
                        extra_res.get("matches", [])
                        if isinstance(extra_res, dict)
                        else getattr(extra_res, "matches", []) or []
                    )
                    matches.extend(extra_matches)
                    # capture raw secondary
                    try:
                        for m in extra_matches:
                            raw_secondary.append(
                                {
                                    "id": getattr(m, "id", None) or m.get("id"),
                                    "score": getattr(m, "score", None)
                                    or m.get("score"),
                                    "metadata": getattr(m, "metadata", None)
                                    or m.get("metadata", {}),
                                    "term": term,
                                }
                            )
                    except Exception:
                        pass
                except Exception:
                    pass

            if debug_raw and secondary_terms:
                try:
                    print("[RAG] Secondary retrieval:")
                    print(f"  terms={secondary_terms} secondary_matches={len(raw_secondary)}")
                    for i, r in enumerate(raw_secondary[:10]):
                        md = r.get("metadata", {}) or {}
                        snippet = md.get("text") or ""
                        snippet = (snippet[:200] + "…") if len(snippet) > 200 else snippet
                        print(
                            f"    [{i}] term={r.get('term')} id={r.get('id')} score={r.get('score')} section={md.get('section_label')} doc={md.get('document_id')} idx={md.get('chunk_index')}\n      {snippet}"
                        )
                except Exception:
                    pass

            # Deduplicate by vector id while keeping best score
            dedup = {}
            norm_matches = []
            for m in matches:
                # normalize obj/dict interface
                mid = getattr(m, "id", None) or m.get("id")
                mscore = getattr(m, "score", None) or m.get("score")
                mmd = getattr(m, "metadata", None) or m.get("metadata", {})
                if not mid:
                    continue
                if mid not in dedup or (mscore is not None and (dedup[mid]["score"] or 0) < mscore):
                    dedup[mid] = {"id": mid, "score": mscore, "metadata": mmd}
            for v in dedup.values():
                norm_matches.append(v)
            # sort by score desc
            norm_matches.sort(key=lambda x: (x["score"] is not None, x["score"]), reverse=True)
            print("norm_matches", len(norm_matches))


            context_texts = []
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
                    f"[RAG] Summary: session={session.id} msg_len={len(message)} matches_total={len(matches)} unique={len(norm_matches)}"
                )
            except Exception:
                pass

            # Generate response using context
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
                "top_k": top_k,
                "matches": retrieval,
            },
        }
        if debug_raw:
            # include raw pinecone results and the exact context text used
            try:
                resp_payload["similarity_text"] = context_text if context_texts else None
            except Exception:
                resp_payload["similarity_text"] = None
            resp_payload["raw_similarity"] = {
                "primary": raw_primary,
                "secondary": raw_secondary,
            }

        return Response(
            resp_payload,
            status=status.HTTP_201_CREATED,
        )
