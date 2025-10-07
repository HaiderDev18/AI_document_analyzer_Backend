import re
import hashlib
from typing import List, Dict, Any
import tiktoken


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate
        return len(text.split()) * 1.3


def is_section_header(line: str) -> bool:
    """Check if a line is a section header like '3.0 THE SUBCONTRACT SUM'"""
    stripped = line.strip()
    # Matches: "3.0 TITLE", "3.1 Title", "3.0 THE TITLE"
    return bool(re.match(r'^\d+\.\d*\s+[A-Z]', stripped))


def extract_section_number(text: str) -> str:
    """Extract section number from text like '3.1 Title' -> '3.1'"""
    match = re.match(r'^(\d+\.\d*)', text.strip())
    return match.group(1) if match else ""


def chunk_text(
        text: str,
        max_tokens: int = 800,
        overlap_tokens: int = 150,
        token_model: str = "cl100k_base",
) -> List[Dict[str, Any]]:
    """
    Chunk text intelligently for legal/financial documents.

    Strategy:
    1. Split by double newlines (paragraphs)
    2. Keep section headers with their content
    3. Ensure chunks don't exceed max_tokens
    4. Add overlap for context continuity
    """

    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_chunk = []
    current_tokens = 0
    current_section = None

    for para in paragraphs:
        para_tokens = count_tokens(para, token_model)

        # Check if this is a section header
        if is_section_header(para):
            # Save previous chunk if exists
            if current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'hash': hashlib.sha256(chunk_text.encode('utf-8')).hexdigest(),
                    'index': len(chunks),
                    'section': current_section,
                    'tokens': current_tokens,
                })

            # Start new chunk with this header
            current_section = extract_section_number(para) or para[:30]
            current_chunk = [para]
            current_tokens = para_tokens

        else:
            # Would adding this paragraph exceed max_tokens?
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'hash': hashlib.sha256(chunk_text.encode('utf-8')).hexdigest(),
                    'index': len(chunks),
                    'section': current_section,
                    'tokens': current_tokens,
                })

                # Start new chunk with overlap
                # Keep last paragraph(s) for context if they fit in overlap
                overlap_content = []
                overlap_tokens_count = 0

                for prev_para in reversed(current_chunk):
                    prev_tokens = count_tokens(prev_para, token_model)
                    if overlap_tokens_count + prev_tokens <= overlap_tokens:
                        overlap_content.insert(0, prev_para)
                        overlap_tokens_count += prev_tokens
                    else:
                        break

                current_chunk = overlap_content + [para]
                current_tokens = overlap_tokens_count + para_tokens

            else:
                # Add to current chunk
                current_chunk.append(para)
                current_tokens += para_tokens

    # Don't forget the last chunk!
    if current_chunk:
        chunk_text = '\n\n'.join(current_chunk)
        chunks.append({
            'text': chunk_text,
            'hash': hashlib.sha256(chunk_text.encode('utf-8')).hexdigest(),
            'index': len(chunks),
            'section': current_section,
            'tokens': current_tokens,
        })

    return chunks


def chunk_text_simple(text: str, max_chars: int = 3000) -> List[str]:
    """
    Simple fallback chunker by character count.
    Used if token-based chunking fails.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + max_chars

        # Try to break at paragraph boundary
        if end < len(text):
            # Look for double newline within last 500 chars
            search_start = max(start, end - 500)
            para_break = text.rfind('\n\n', search_start, end)
            if para_break > start:
                end = para_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end

    return chunks


# Example usage and testing
if __name__ == "__main__":
    # Test with sample text
    sample_text = """
SUBCONTRACT ORDER

1.0 SCOPE OF WORKS

The Subcontractor shall provide all labour and materials.

1.1 Including dot and dab work.

2.0 PROGRAMME

The works shall commence on 19/05/25.

3.0 THE SUBCONTRACT SUM

3.1 The Contractor shall pay to the Subcontractor the VAT exclusive sum of:
£181,726.19

One Hundred and Eighty One Thousand, Seven hundred and Twenty Six Pounds and Nineteen Pence only.

3.2 This sum is deemed a fixed price.

4.0 INSURANCES

4.1 Public Liability Insurance required.
"""

    chunks = chunk_text(sample_text, max_tokens=300, overlap_tokens=50)

    print(f"Created {len(chunks)} chunks:\n")
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i} (Section: {chunk['section']}, Tokens: {chunk['tokens']}) ---")
        print(chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'])
        print()