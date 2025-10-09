"""
Semantic Document Processor - Enhanced RAG with Knowledge Extraction

This module implements RAG-Anything-inspired techniques without the heavy dependency.
It extracts entities, relationships, and semantic metadata to improve RAG retrieval.

Key improvements over basic chunking:
1. Entity extraction (amounts, dates, parties, clauses)
2. Relationship identification
3. Content type classification
4. Semantic metadata enrichment
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Entity:
    """Represents an extracted entity from document"""
    type: str  # 'amount', 'date', 'party', 'clause', 'percentage', 'obligation'
    value: str
    context: str  # surrounding text
    position: int  # character position in document


@dataclass
class Relationship:
    """Represents a relationship between entities"""
    source: Entity
    relation_type: str  # 'pays', 'requires', 'deadline', 'percentage_of'
    target: Entity
    confidence: float


class SemanticProcessor:
    """
    Extracts semantic information from document text to enhance RAG retrieval
    """

    # Entity patterns for legal/financial documents
    PATTERNS = {
        'amount': [
            r'£[\d,]+(?:\.\d{2})?',  # £181,726.19
            r'\$[\d,]+(?:\.\d{2})?',  # $1,234.56
            r'(?:sum of|amount of|total of|payment of)\s+[£$]?[\d,]+(?:\.\d{2})?',
        ],
        'percentage': [
            r'\d+(?:\.\d+)?%',  # 5%, 10.5%
            r'\d+(?:\.\d+)?\s*(?:percent|percentage)',
        ],
        'date': [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # 19/05/25, 01-05-2025
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
        ],
        'party': [
            r'(?:Contractor|Subcontractor|Client|Employer|Supplier|Vendor)(?:\s+shall)?',
            r'(?:the\s+)?(?:Contractor|Subcontractor|Client|Employer)\b',
        ],
        'clause_reference': [
            r'(?:Clause|Section|Article|Paragraph)\s+\d+(?:\.\d+)*',
            r'\b\d+\.\d+\s+[A-Z][A-Z\s]+',  # 6.0 RETENTION
        ],
        'obligation': [
            r'(?:shall|must|will|required to|obliged to)\s+\w+',
            r'(?:responsible for|liable for|duty to)',
        ],
        'insurance': [
            r'(?:insurance|liability|indemnity|cover)',
            r'(?:Public Liability|Professional Indemnity|Employers Liability)',
        ],
    }

    # Content type classifiers
    CONTENT_TYPES = {
        'financial': ['sum', 'payment', 'price', 'cost', 'value', 'amount', '£', '$', 'vat', 'invoice'],
        'temporal': ['commence', 'deadline', 'duration', 'period', 'date', 'completion', 'delay'],
        'obligation': ['shall', 'must', 'require', 'obligation', 'duty', 'responsible', 'liable'],
        'insurance': ['insurance', 'liability', 'indemnity', 'cover', 'policy', 'claim'],
        'retention': ['retention', 'holdback', 'withhold', 'release', 'percentage'],
        'scope': ['scope', 'works', 'services', 'materials', 'labour', 'supply', 'provide'],
        'termination': ['terminate', 'suspension', 'cancel', 'breach', 'default'],
        'variation': ['variation', 'change', 'modification', 'amendment', 'instruction'],
    }

    def __init__(self, use_llm_extraction: bool = True):
        """
        Initialize semantic processor

        Args:
            use_llm_extraction: If True, use OpenAI to extract entities and relationships
                               If False, use regex-based extraction only
        """
        self.use_llm_extraction = use_llm_extraction
        self.openai_service = None

        if use_llm_extraction:
            try:
                from documents.services.openai_service import OpenAIService
                self.openai_service = OpenAIService()
            except Exception:
                self.use_llm_extraction = False

    def extract_entities(self, text: str) -> List[Entity]:
        """
        Extract entities from text using pattern matching
        """
        entities = []

        for entity_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Get surrounding context (50 chars before and after)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()

                    entity = Entity(
                        type=entity_type,
                        value=match.group(0),
                        context=context,
                        position=match.start()
                    )
                    entities.append(entity)

        return entities

    def identify_relationships(self, entities: List[Entity], text: str) -> List[Relationship]:
        """
        Identify relationships between extracted entities
        """
        relationships = []

        # Simple relationship patterns
        relationship_patterns = [
            (r'(\w+)\s+shall\s+pay\s+(?:to\s+)?(\w+)', 'pays'),
            (r'(\w+)\s+(?:shall|must)\s+provide\s+(\w+)', 'provides'),
            (r'retention\s+(?:of|percentage)\s+([\d.]+%)', 'retention_percentage'),
            (r'commence\s+on\s+([\d/]+)', 'start_date'),
            (r'complete\s+by\s+([\d/]+)', 'deadline'),
        ]

        for pattern, relation_type in relationship_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Create relationships based on matched patterns
                # This is simplified - in production, you'd use NLP for better accuracy
                pass  # Implementation would create Relationship objects

        return relationships

    def classify_content_type(self, text: str) -> List[str]:
        """
        Classify the type of content in the text chunk
        """
        text_lower = text.lower()
        content_types = []

        for content_type, keywords in self.CONTENT_TYPES.items():
            # Check if any keywords are present
            if any(keyword in text_lower for keyword in keywords):
                content_types.append(content_type)

        return content_types

    def extract_key_phrases(self, text: str) -> List[str]:
        """
        Extract important phrases that should be searchable
        """
        phrases = []

        # Extract numbered clauses/sections with their titles
        clause_pattern = r'(\d+\.\d*)\s+([A-Z][A-Z\s]+)'
        for match in re.finditer(clause_pattern, text):
            phrase = f"{match.group(1)} {match.group(2).strip()}"
            phrases.append(phrase)

        # Extract amounts with context
        amount_pattern = r'((?:sum|amount|payment|price|cost|total|value)\s+(?:of\s+)?[£$]?[\d,]+(?:\.\d{2})?)'
        for match in re.finditer(amount_pattern, text, re.IGNORECASE):
            phrases.append(match.group(1).strip())

        # Extract obligations
        obligation_pattern = r'(\w+\s+(?:shall|must|will)\s+\w+(?:\s+\w+){0,5})'
        for match in re.finditer(obligation_pattern, text, re.IGNORECASE):
            phrase = match.group(1).strip()
            if len(phrase.split()) <= 8:  # Keep phrases reasonably short
                phrases.append(phrase)

        return phrases

    def enrich_chunk_with_llm(self, chunk_text: str) -> Dict[str, Any]:
        """
        Use LLM to extract structured information from chunk
        """
        if not self.openai_service:
            return {}

        try:
            system_prompt = """You are a document analysis AI that extracts structured information from legal/financial documents.

Extract the following from the text:
1. Key entities (parties, amounts, dates, percentages, clauses)
2. Main topic/subject of this section
3. Content type (financial, obligation, insurance, scope, temporal, etc.)
4. Key searchable phrases (3-5 phrases that someone might search for)
5. Any important numbers or percentages with their context

Return ONLY a JSON object with this structure:
{
    "entities": {"parties": [], "amounts": [], "dates": [], "percentages": [], "clauses": []},
    "topic": "brief topic description",
    "content_types": ["type1", "type2"],
    "key_phrases": ["phrase1", "phrase2", "phrase3"],
    "important_values": [{"type": "amount/date/percentage", "value": "...", "context": "..."}]
}"""

            user_prompt = f"""Extract structured information from this document section:

{chunk_text[:1500]}

Return only the JSON object, no other text."""

            response = self.openai_service.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            extracted = json.loads(response.choices[0].message.content)
            return extracted

        except Exception as e:
            print(f"LLM enrichment failed: {e}")
            return {}

    def create_enhanced_metadata(
        self,
        chunk_text: str,
        chunk_index: int,
        section: Optional[str] = None,
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Create rich metadata for a chunk to improve retrieval

        Returns:
            Dictionary with enhanced metadata including entities, content types, and key phrases
        """
        # Basic extraction (always done)
        entities = self.extract_entities(chunk_text)
        content_types = self.classify_content_type(chunk_text)
        key_phrases = self.extract_key_phrases(chunk_text)

        # Build basic metadata
        metadata = {
            'chunk_index': chunk_index,
            'section': section,
            'content_types': content_types,
            'key_phrases': key_phrases,
            'entity_counts': {
                'amounts': len([e for e in entities if e.type == 'amount']),
                'dates': len([e for e in entities if e.type == 'date']),
                'percentages': len([e for e in entities if e.type == 'percentage']),
                'parties': len([e for e in entities if e.type == 'party']),
                'clauses': len([e for e in entities if e.type == 'clause_reference']),
            },
        }

        # Add extracted entity values (for better searchability)
        for entity_type in ['amount', 'percentage', 'date', 'party']:
            entity_values = [e.value for e in entities if e.type == entity_type]
            if entity_values:
                metadata[f'{entity_type}_values'] = entity_values[:5]  # Limit to 5

        # LLM-based enrichment (optional, more accurate but slower)
        if use_llm and self.use_llm_extraction:
            llm_metadata = self.enrich_chunk_with_llm(chunk_text)
            if llm_metadata:
                metadata['llm_extracted'] = llm_metadata

        return metadata

    def create_enhanced_embedding_text(
        self,
        chunk_text: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Create enriched text for embedding that includes semantic context

        This improves retrieval by adding searchable semantic information to the embedding
        """
        enriched_parts = [chunk_text]

        # Add section context
        if metadata.get('section'):
            enriched_parts.append(f"\n[Section: {metadata['section']}]")

        # Add content type tags
        if metadata.get('content_types'):
            types_str = ", ".join(metadata['content_types'])
            enriched_parts.append(f"\n[Content: {types_str}]")

        # Add key phrases for better searchability
        if metadata.get('key_phrases'):
            phrases_str = " | ".join(metadata['key_phrases'][:3])
            enriched_parts.append(f"\n[Key terms: {phrases_str}]")

        # Add important entity values
        entity_tags = []
        for entity_type in ['amount', 'percentage', 'date']:
            values = metadata.get(f'{entity_type}_values', [])
            if values:
                entity_tags.append(f"{entity_type}: {', '.join(str(v) for v in values[:2])}")

        if entity_tags:
            enriched_parts.append(f"\n[Entities: {' | '.join(entity_tags)}]")

        # Add LLM-extracted topic if available
        llm_data = metadata.get('llm_extracted', {})
        if llm_data.get('topic'):
            enriched_parts.append(f"\n[Topic: {llm_data['topic']}]")

        return "\n".join(enriched_parts)

    def process_chunk(
        self,
        chunk_text: str,
        chunk_index: int,
        section: Optional[str] = None,
        use_llm_enrichment: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Process a single chunk to create enhanced embedding text and metadata

        Args:
            chunk_text: The raw chunk text
            chunk_index: Index of this chunk in the document
            section: Section identifier if available
            use_llm_enrichment: Whether to use LLM for deeper analysis

        Returns:
            Tuple of (enriched_text_for_embedding, enhanced_metadata)
        """
        # Create enhanced metadata
        metadata = self.create_enhanced_metadata(
            chunk_text,
            chunk_index,
            section,
            use_llm=use_llm_enrichment
        )

        # Create enriched text for embedding
        enriched_text = self.create_enhanced_embedding_text(chunk_text, metadata)

        return enriched_text, metadata


# Utility functions for backward compatibility

def enhance_chunks_for_rag(
    chunks: List[Dict[str, Any]],
    use_llm_enrichment: bool = False
) -> List[Dict[str, Any]]:
    """
    Enhance existing chunks with semantic metadata

    Args:
        chunks: List of chunks from the chunking service
        use_llm_enrichment: Whether to use LLM for enrichment (slower but better)

    Returns:
        Enhanced chunks with enriched embedding text and metadata
    """
    processor = SemanticProcessor(use_llm_extraction=use_llm_enrichment)
    enhanced_chunks = []

    for chunk in chunks:
        enriched_text, metadata = processor.process_chunk(
            chunk_text=chunk['text'],
            chunk_index=chunk['index'],
            section=chunk.get('section'),
            use_llm_enrichment=use_llm_enrichment
        )

        # Create enhanced chunk
        enhanced_chunk = {
            **chunk,  # Keep original fields
            'embedding_text': enriched_text,  # New: enriched text for embedding
            'semantic_metadata': metadata,  # New: rich metadata
        }

        enhanced_chunks.append(enhanced_chunk)

    return enhanced_chunks
