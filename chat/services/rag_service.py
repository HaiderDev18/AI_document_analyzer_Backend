from typing import List, Dict, Any, Optional
from documents.services.openai_service import OpenAIService
from documents.services.pinecone_service import PineconeService


class RAGService:
    """
    Service class for Retrieval-Augmented Generation (RAG)
    """

    def __init__(self, user_namespace: str = None):
        self.openai_service = OpenAIService()
        self.pinecone_service = (
            PineconeService(namespace=user_namespace) if user_namespace else None
        )

    def search_relevant_context(
        self,
        query: str,
        user,
        namespace,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Search for relevant document chunks based on user query
        """
        try:
            # Get user namespace
            # user_namespace = user.get_or_create_namespace()

            # Initialize pinecone service with user namespace if not already set
            if not self.pinecone_service:
                self.pinecone_service = PineconeService(namespace=namespace)

            # Generate embedding for the query
            query_embedding = self.openai_service.generate_embedding(query)

            # Search similar chunks in Pinecone
            similar_chunks = self.pinecone_service.search_similar_chunks(
                query_embedding, str(user.id), top_k
            )

            # Extract context and source information
            context_chunks = []
            source_documents = []

            for chunk in similar_chunks:
                metadata = chunk.metadata
                context_chunks.append(
                    {
                        "text": metadata["text"],
                        "score": chunk.score,
                        "document_id": metadata["document_id"],
                        "chunk_index": metadata["chunk_index"],
                    }
                )

                # Track unique source documents
                doc_info = {
                    "document_id": metadata["document_id"],
                    "chunk_index": metadata["chunk_index"],
                    "relevance_score": chunk.score,
                }
                if doc_info not in source_documents:
                    source_documents.append(doc_info)

            # Combine context text
            context_text = "\n\n".join([chunk["text"] for chunk in context_chunks])

            return {
                "context_text": context_text,
                "context_chunks": context_chunks,
                "source_documents": source_documents,
                "total_chunks": len(context_chunks),
            }

        except Exception as e:
            raise Exception(f"Error searching relevant context: {str(e)}")

    def generate_rag_response(
        self,
        query: str,
        user,
        chat_history: List[Dict[str, str]] = None,
        namespace: str = None,
    ) -> Dict[str, Any]:
        """
        Generate response using RAG (Retrieval-Augmented Generation)
        """
        try:
            # Search for relevant context
            context_data = self.search_relevant_context(query, user, namespace)

            # Prepare chat messages
            messages = []

            # Add chat history if provided
            if chat_history:
                for msg in chat_history[-10:]:  # Limit to last 10 messages
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current user query
            messages.append({"role": "user", "content": query})

            # Generate response with context
            response = self.openai_service.chat_completion(
                messages=messages,
                context=context_data["context_text"]
                if context_data["context_text"]
                else None,
            )

            return {
                "response": response,
                "context_used": context_data["context_text"],
                "source_documents": context_data["source_documents"],
                "context_chunks_count": context_data["total_chunks"],
            }

        except Exception as e:
            raise Exception(f"Error generating RAG response: {str(e)}")

    def generate_simple_response(
        self, query: str, chat_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Generate simple response without RAG (when no relevant context found)
        """
        try:
            messages = []

            # Add chat history if provided
            if chat_history:
                for msg in chat_history[-10:]:  # Limit to last 10 messages
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current user query
            messages.append({"role": "user", "content": query})

            # Generate response without context
            response = self.openai_service.chat_completion(messages=messages)

            return response

        except Exception as e:
            raise Exception(f"Error generating simple response: {str(e)}")

    def get_chat_title_suggestion(self, first_message: str) -> str:
        """
        Generate a title for the chat session based on the first message
        """
        try:
            prompt = f"Generate a short, descriptive title (max 50 characters) for a chat that starts with: '{first_message[:100]}'"

            messages = [
                {
                    "role": "developer",
                    "content": "You generate short, descriptive titles for chat conversations. Respond with only the title, no quotes or extra text.",
                },
                {"role": "user", "content": prompt},
            ]

            title = self.openai_service.chat_completion(messages=messages)
            return title[:50]  # Ensure max 50 characters

        except Exception:
            # Fallback to first few words of the message
            words = first_message.split()[:5]
            return " ".join(words) + ("..." if len(words) == 5 else "")
