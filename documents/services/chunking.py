from typing import List, Dict
import hashlib
import re

try:
    import tiktoken
except ImportError:
    tiktoken = None  # optional but recommended


def _normalize(text: str) -> str:
    # cheap normalization to improve dedupe; keep punctuation for retrieval quality
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _encode_len(s: str, model_name: str = "cl100k_base") -> int:
    if tiktoken:
        enc = tiktoken.get_encoding(model_name)
        return len(enc.encode(s))
    # fallback heuristic ~4 chars/token
    return max(1, len(s) // 4)


def chunk_text(
    text: str,
    max_tokens: int = 800,
    overlap_tokens: int = 120,
    token_model: str = "cl100k_base",
) -> List[Dict]:
    """
    Returns a list of chunks: [{ 'text': str, 'hash': str, 'index': int }]
    Greedy packing by paragraphs with token overlap.
    """
    text = _normalize(text)
    if not text:
        return []

    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: List[Dict] = []
    buf: List[str] = []
    buf_tokens = 0

    def flush():
        nonlocal buf, buf_tokens
        if not buf:
            return
        chunk_text = "\n\n".join(buf).strip()
        h = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        chunks.append({"text": chunk_text, "hash": h, "index": len(chunks)})
        buf = []
        buf_tokens = 0

    for p in paras:
        p_tokens = _encode_len(p, token_model)
        if p_tokens > max_tokens:
            # hard split long paragraph into sentences (very rough)
            sentences = re.split(r"(?<=[.!?])\s+", p)
            cur = []
            cur_toks = 0
            for s in sentences:
                st = _encode_len(s, token_model)
                if cur_toks + st > max_tokens and cur:
                    buf.append(" ".join(cur))
                    flush()
                    cur, cur_toks = [], 0
                cur.append(s)
                cur_toks += st
            if cur:
                buf.append(" ".join(cur))
                flush()
            continue

        if buf_tokens + p_tokens <= max_tokens:
            buf.append(p)
            buf_tokens += p_tokens
        else:
            flush()
            buf.append(p)
            buf_tokens = p_tokens

    flush()

    # Add overlap
    if overlap_tokens > 0 and len(chunks) > 1:
        with_overlap: List[Dict] = []
        for i, c in enumerate(chunks):
            if i == 0:
                with_overlap.append(c)
                continue
            prev = chunks[i - 1]["text"]
            cur = c["text"]
            if tiktoken:
                enc = tiktoken.get_encoding(token_model)
                prev_tokens = enc.encode(prev)
                keep = enc.decode(prev_tokens[-overlap_tokens:]) if prev_tokens else ""
            else:
                keep = prev[-overlap_tokens * 4 :]  # heuristic
            merged = (
                keep + ("\n\n" if keep and not keep.endswith("\n\n") else "") + cur
            ).strip()
            h = hashlib.sha256(merged.encode("utf-8")).hexdigest()
            with_overlap.append({"text": merged, "hash": h, "index": i})
        chunks = with_overlap

    return chunks
