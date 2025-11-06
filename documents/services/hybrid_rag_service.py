"""
Hybrid RAG Service - Smart decision between full-context and embedding-based retrieval

For small documents: Send entire text as context (faster, more accurate)
For large documents: Use embeddings and retrieval (scalable, handles any size)
"""

import json
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache


class HybridRAGService:
    """
    Decides between full-context mode (small docs) and embedding mode (large docs)
    """

    def __init__(self):
        # Get threshold from settings
        self.full_context_limit = getattr(settings, 'FULL_CONTEXT_CHAR_LIMIT', 100000)

    def should_use_full_context(self, text: str) -> bool:
        """
        Determine if document should use full-context mode

        Args:
            text: Document text

        Returns:
            True if document should use full-context, False if should use embeddings
        """
        char_count = len(text)
        return char_count <= self.full_context_limit

    def get_processing_mode(self, text: str) -> Dict[str, Any]:
        """
        Get the processing mode and related info

        Returns:
            Dictionary with mode info
        """
        char_count = len(text)
        use_full_context = self.should_use_full_context(text)

        # Rough token estimation (1 token ≈ 4 chars)
        estimated_tokens = char_count // 4

        return {
            'mode': 'full_context' if use_full_context else 'embeddings',
            'char_count': char_count,
            'estimated_tokens': estimated_tokens,
            'threshold': self.full_context_limit,
            'reason': self._get_mode_reason(char_count, use_full_context)
        }

    def _get_mode_reason(self, char_count: int, use_full_context: bool) -> str:
        """Get human-readable reason for mode selection"""
        if use_full_context:
            return f"Document is small ({char_count:,} chars), using full context for maximum accuracy"
        else:
            return f"Document is large ({char_count:,} chars), using embeddings for scalability"

    def store_full_context(self, session_id: str, document_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """
        Store full document text in cache for fast retrieval

        Args:
            session_id: Chat session ID
            document_id: Document ID
            text: Full document text
            metadata: Additional metadata (tables, etc.)
        """
        cache_key = f"full_context:{session_id}:{document_id}"

        data = {
            'text': text,
            'metadata': metadata,
            'char_count': len(text),
            'stored_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        # Store for 24 hours (can be adjusted)
        cache.set(cache_key, json.dumps(data), timeout=86400)

    def get_full_context(self, session_id: str, document_id: Optional[str] = None) -> Optional[str]:
        """
        Retrieve full document text from cache

        Args:
            session_id: Chat session ID
            document_id: Specific document ID, or None to get all documents in session

        Returns:
            Full text or None if not found/expired
        """
        if document_id:
            # Get specific document
            cache_key = f"full_context:{session_id}:{document_id}"
            cached = cache.get(cache_key)
            if cached:
                data = json.loads(cached)
                return data['text']
            return None
        else:
            # Get all documents in session (merge them)
            return self.get_all_session_context(session_id)

    def get_all_session_context(self, session_id: str) -> Optional[str]:
        """
        Get combined full context from all documents in a session

        Args:
            session_id: Chat session ID

        Returns:
            Combined text from all documents in session
        """
        # This requires getting all document IDs for the session
        # For now, we'll use a session-level cache key
        cache_key = f"full_context_session:{session_id}"
        cached = cache.get(cache_key)
        if cached:
            data = json.loads(cached)
            return data['combined_text']
        return None

    def store_session_context(self, session_id: str, combined_text: str, document_ids: list) -> None:
        """
        Store combined context for all documents in a session

        Args:
            session_id: Chat session ID
            combined_text: Combined text from all documents
            document_ids: List of document IDs
        """
        cache_key = f"full_context_session:{session_id}"

        data = {
            'combined_text': combined_text,
            'document_ids': document_ids,
            'char_count': len(combined_text),
            'stored_at': __import__('datetime').datetime.utcnow().isoformat()
        }

        # Store for 24 hours
        cache.set(cache_key, json.dumps(data), timeout=86400)

    def clear_session_context(self, session_id: str) -> None:
        """
        Clear cached context for a session

        Args:
            session_id: Chat session ID
        """
        cache_key = f"full_context_session:{session_id}"
        cache.delete(cache_key)


def format_full_context_prompt(text: str, query: str) -> list:
    """
    Format the full document text and user query into a prompt

    Args:
        text: Full document text
        query: User query

    Returns:
        List of messages for OpenAI API
    """
    system_prompt = """
    You are a helpful assistant that answers questions based on the provided document.

Rules:
- Answer based ONLY on the information in the document
- If the answer isn't in the document, say "I don't have that information in the document"
- Be specific and cite relevant sections when possible
- For financial/numerical questions, provide exact values from the document
- For dates, use the exact format from the document
- For yes/no questions, give a clear answer followed by supporting details

The entire document content is provided below."""

    user_prompt = f"""Document Content:
{text}

---

Question: {query}

Instructions:
1. First, determine the question type:
   - YES/NO questions: Questions asking if/whether something is true, exists, or is allowed
   - FACTUAL questions: Questions asking for specific information, values, definitions, or explanations
   - CALCULATION questions: Questions requiring computation from context data

2. Format your response based on question type:

   For YES/NO questions:
   Assessment: <Likely Yes | Likely No | Unclear>
   Detail: [1-3 sentence explanation]

   For FACTUAL or CALCULATION questions:
   Answer: [Direct answer with specific value/information]
   Detail: [1-3 sentence explanation with source reference]

3. Rules:
   - For factual questions, provide the direct answer immediately after "Answer:"
   - For calculations, show the result clearly and explain the computation briefly
   - If information is missing, use "Unclear" for yes/no or "Information not found" for factual questions
   - Keep explanations concise and scannable
   - Always cite the relevant clause/section from context when possible
   - For legal/contractual questions, add: "Caution: This is informational only and not legal advice. Consult a qualified professional for decisions."

Please answer the question based on the document content above."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


# Helper function for backward compatibility
def get_hybrid_retrieval_strategy(text_length: int) -> str:
    """
    Determine retrieval strategy based on text length

    Args:
        text_length: Length of document text in characters

    Returns:
        'full_context' or 'embeddings'
    """
    service = HybridRAGService()
    return 'full_context' if service.should_use_full_context('x' * text_length) else 'embeddings'
