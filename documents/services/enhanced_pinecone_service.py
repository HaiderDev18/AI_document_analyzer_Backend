"""
Enhanced Pinecone Service with Semantic Awareness

This extends the base Pinecone service to support semantic metadata
and improved retrieval strategies inspired by RAG-Anything.
"""

from typing import List, Dict, Any, Optional
from documents.services.pinecone_service import PineconeEmbedding, PineconeService
from documents.services.chunking import chunk_text
from documents.services.semantic_processor import SemanticProcessor, enhance_chunks_for_rag
from django.conf import settings
import json


class EnhancedPineconeService(PineconeService):
    """
    Enhanced Pinecone service with semantic metadata support
    """

    def __init__(self, namespace: Optional[str] = None, use_semantic_enrichment: bool = True):
        super().__init__(namespace=namespace)
        self.use_semantic_enrichment = use_semantic_enrichment
        self.semantic_processor = SemanticProcessor(use_llm_extraction=False)  # Start with regex-based

    def store_text_with_semantics(
        self,
        *,
        document_id: str,
        text: str,
        file_name: str,
        file_path: str,
        use_llm_enrichment: bool = False
    ):
        """
        Store text with semantic enrichment

        Args:
            document_id: Unique document identifier
            text: Document text to process
            file_name: Name of the document file
            file_path: Path/URI to the file
            use_llm_enrichment: Whether to use LLM for deeper semantic extraction (slower)

        Returns:
            Dictionary with upsert results and metadata
        """
        # Step 1: Basic chunking
        max_tokens = getattr(settings, "CHUNK_SIZE", 1000)
        overlap_tokens = getattr(settings, "CHUNK_OVERLAP", 200)

        print(f"[Enhanced Pinecone] Chunking text...")
        print(f"  - Text length: {len(text)} chars")
        print(f"  - Max tokens: {max_tokens}, Overlap: {overlap_tokens}")

        base_chunks = chunk_text(text, max_tokens=max_tokens, overlap_tokens=overlap_tokens)

        print(f"  - Created {len(base_chunks)} base chunks")
        if base_chunks:
            for i, chunk in enumerate(base_chunks[:3]):
                print(f"    Chunk {i}: {chunk.get('tokens', 0)} tokens, section: {chunk.get('section', 'N/A')}")

        if not base_chunks:
            return {"upserted": 0, "document_id": document_id, "namespace": self.namespace}

        # Step 2: Enhance chunks with semantic metadata
        if self.use_semantic_enrichment:
            enhanced_chunks = enhance_chunks_for_rag(base_chunks, use_llm_enrichment=use_llm_enrichment)
        else:
            enhanced_chunks = base_chunks

        # Step 3: Create vectors with enhanced metadata
        vectors = self._create_enhanced_vectors(
            enhanced_chunks,
            document_id=document_id,
            file_name=file_name,
            file_path=file_path
        )

        # Step 4: Clear old vectors and upsert new ones
        if self.engine._namespace_exists():
            self.engine._delete_vectors_for_document(document_id)

        self.engine.upsert_vectors(vectors)

        return {
            "upserted": len(vectors),
            "document_id": document_id,
            "namespace": self.namespace,
            "semantic_enrichment": self.use_semantic_enrichment,
            "chunks_processed": len(enhanced_chunks)
        }

    def _create_enhanced_vectors(
        self,
        enhanced_chunks: List[Dict[str, Any]],
        document_id: str,
        file_name: str,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Create vectors with rich semantic metadata
        """
        from datetime import datetime
        import hashlib

        vectors = []
        BATCH = 100

        # Prepare texts for embedding
        texts_for_embedding = []
        for chunk in enhanced_chunks:
            # Use enriched text if available, otherwise use original
            embedding_text = chunk.get('embedding_text', chunk['text'])
            texts_for_embedding.append(embedding_text)

        # Generate embeddings in batches
        for i in range(0, len(enhanced_chunks), BATCH):
            batch_chunks = enhanced_chunks[i:i + BATCH]
            batch_texts = texts_for_embedding[i:i + BATCH]

            # Get embeddings
            embeddings = self.engine._embed_batch(batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings):
                # Build comprehensive metadata
                metadata = self._build_enhanced_metadata(
                    chunk=chunk,
                    document_id=document_id,
                    file_name=file_name,
                    file_path=file_path
                )

                # Create deterministic vector ID
                chunk_hash = chunk.get('hash') or hashlib.sha256(
                    chunk['text'].encode('utf-8')
                ).hexdigest()
                vector_id = f"{document_id}:{chunk['index']}:{chunk_hash[:8]}"

                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": metadata
                })

        return vectors

    def _build_enhanced_metadata(
        self,
        chunk: Dict[str, Any],
        document_id: str,
        file_name: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Build rich metadata for Pinecone vector
        """
        from datetime import datetime

        # Start with base metadata
        metadata = {
            "document_id": document_id,
            "file_name": file_name,
            "file_path": file_path,
            "chunk_index": chunk['index'],
            "chunk_hash": chunk.get('hash', '')[:16],  # Truncate for space
            "text": chunk['text'][:1500],  # Store truncated text
            "embedding_model": self.engine.embed_model,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add section information
        if chunk.get('section'):
            metadata["section"] = chunk['section']

        # Add semantic metadata if available
        semantic_meta = chunk.get('semantic_metadata', {})
        if semantic_meta:
            # Add content types
            if semantic_meta.get('content_types'):
                metadata["content_types"] = semantic_meta['content_types']

            # Add entity counts
            entity_counts = semantic_meta.get('entity_counts', {})
            for entity_type, count in entity_counts.items():
                if count > 0:
                    metadata[f"has_{entity_type}"] = True
                    metadata[f"{entity_type}_count"] = count

            # Add extracted values (for filtering)
            for value_type in ['amount_values', 'percentage_values', 'date_values']:
                values = semantic_meta.get(value_type, [])
                if values:
                    # Store as JSON string for Pinecone
                    metadata[value_type] = json.dumps(values[:3])  # Limit to 3

            # Add key phrases
            if semantic_meta.get('key_phrases'):
                # Store as concatenated string for full-text search
                metadata["key_phrases"] = " | ".join(semantic_meta['key_phrases'][:5])

            # Add LLM-extracted data if available
            llm_data = semantic_meta.get('llm_extracted', {})
            if llm_data:
                if llm_data.get('topic'):
                    metadata["topic"] = llm_data['topic'][:200]
                if llm_data.get('key_phrases'):
                    metadata["llm_key_phrases"] = " | ".join(llm_data['key_phrases'][:3])

        return metadata

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        content_type_filter: Optional[List[str]] = None,
        entity_filter: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Perform hybrid search with semantic filtering

        Args:
            query: User query
            top_k: Number of results to return
            content_type_filter: Filter by content types (e.g., ['financial', 'obligation'])
            entity_filter: Filter by entity presence (e.g., {'has_amounts': True})

        Returns:
            Search results with matched chunks
        """
        # Build Pinecone filter
        pinecone_filter = {}

        if content_type_filter:
            # Pinecone filter for content types
            pinecone_filter["content_types"] = {"$in": content_type_filter}

        if entity_filter:
            # Add entity filters
            for key, value in entity_filter.items():
                pinecone_filter[key] = {"$eq": value}

        # Perform semantic search
        results = self.engine.similarity_search(
            query=query,
            top_k=top_k,
            filters=pinecone_filter if pinecone_filter else None
        )

        return results

    def smart_retrieval(
        self,
        query: str,
        top_k: int = 10,
        auto_filter: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Intelligent retrieval that automatically determines the best search strategy

        Args:
            query: User query
            top_k: Number of results
            auto_filter: Automatically detect and apply content type filters

        Returns:
            List of matched chunks with metadata
        """
        import re

        # Detect query intent and auto-apply filters
        content_filters = []
        entity_filters = {}

        if auto_filter:
            query_lower = query.lower()

            # Financial queries
            if re.search(r'(?:sum|amount|payment|pay|price|cost|total|value|money)', query_lower):
                content_filters.append('financial')
                entity_filters['has_amounts'] = True

            # Retention queries
            if re.search(r'(?:retention|holdback|withhold|percentage)', query_lower):
                content_filters.append('retention')
                entity_filters['has_percentages'] = True

            # Date/timeline queries
            if re.search(r'(?:when|date|deadline|commence|start|complete|duration)', query_lower):
                content_filters.append('temporal')
                entity_filters['has_dates'] = True

            # Insurance queries
            if re.search(r'(?:insurance|liability|indemnity|cover|policy)', query_lower):
                content_filters.append('insurance')

            # Obligation queries
            if re.search(r'(?:shall|must|require|obligation|responsible|liable)', query_lower):
                content_filters.append('obligation')

        # Perform primary semantic search
        primary_results = self.hybrid_search(
            query=query,
            top_k=top_k,
            content_type_filter=content_filters if content_filters else None,
            entity_filter=entity_filters if entity_filters else None
        )

        # Extract matches
        matches = []
        if isinstance(primary_results, dict):
            matches = primary_results.get("matches", [])
        else:
            matches = getattr(primary_results, "matches", []) or []

        # If filtered search returned too few results, do unfiltered search
        if len(matches) < max(3, top_k // 2):
            fallback_results = self.engine.similarity_search(query=query, top_k=top_k)
            if isinstance(fallback_results, dict):
                matches = fallback_results.get("matches", [])
            else:
                matches = getattr(fallback_results, "matches", []) or []

        # Normalize matches to dict format
        normalized_matches = []
        for m in matches:
            match_dict = {
                "id": getattr(m, "id", None) or m.get("id"),
                "score": getattr(m, "score", None) or m.get("score"),
                "metadata": getattr(m, "metadata", None) or m.get("metadata", {})
            }
            normalized_matches.append(match_dict)

        return normalized_matches


# Helper function to migrate existing namespace to semantic enrichment
def migrate_namespace_to_semantic(
    namespace: str,
    sample_document_ids: Optional[List[str]] = None,
    use_llm: bool = False
):
    """
    Re-process documents in a namespace with semantic enrichment

    This is useful for upgrading existing documents to use the new semantic metadata.
    Only re-processes specified documents or can be run on sample for testing.
    """
    # This would need to be implemented with your document retrieval logic
    # Just a placeholder showing the concept
    pass
