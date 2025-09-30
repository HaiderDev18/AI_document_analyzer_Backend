# scripts/rag_query_env.py
# Purpose: run a RAG query by pulling *all* config from .env (no CLI).
# Required .env keys are validated up front with a helpful error.

import os
from textwrap import shorten
from typing import List
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
from pinecone import Pinecone

# --- load all env from .env (nearest upwards) ---
load_dotenv(find_dotenv(), override=True)

# --- required & optional envs ---
REQUIRED_KEYS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
    "PINECONE_NAMESPACE",
]

OPTIONAL_DEFAULTS = {
    "OPENAI_EMBED_MODEL": "text-embedding-3-large",  # 3072-dim; use -3-small (1536) if your index is 1536
    "OPENAI_CHAT_MODEL": "gpt-4o-mini",
    "RAG_TOP_K": "7",
    "RAG_MAX_CONTEXT_CHARS": "5000",
}

# --- validate env ---
missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
if missing:
    pretty = ", ".join(missing)
    raise RuntimeError(
        f"Missing required .env keys: {pretty}\n"
        "Create/update your .env (see template below) and rerun."
    )

# pull required
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE")
RAG_QUERY = "What is this doc about"

# pull optional with defaults
OPENAI_EMBED_MODEL = os.getenv(
    "OPENAI_EMBED_MODEL", OPTIONAL_DEFAULTS["OPENAI_EMBED_MODEL"]
)
OPENAI_CHAT_MODEL = os.getenv(
    "OPENAI_CHAT_MODEL", OPTIONAL_DEFAULTS["OPENAI_CHAT_MODEL"]
)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", OPTIONAL_DEFAULTS["RAG_TOP_K"]))
RAG_MAX_CONTEXT_CHARS = int(
    os.getenv("RAG_MAX_CONTEXT_CHARS", OPTIONAL_DEFAULTS["RAG_MAX_CONTEXT_CHARS"])
)

# --- clients ---
oai = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)


def embed_query(text: str, model: str) -> List[float]:
    resp = oai.embeddings.create(model=model, input=[text])
    return resp.data[0].embedding


def build_context(matches, max_chars: int = 5000) -> str:
    parts = []
    total = 0
    for m in matches:
        md = m.get("metadata") or {}
        text = md.get("text") or ""
        header = f"[source {m['id']}]"
        chunk = f"{header}\n{text}\n"
        if total + len(chunk) > max_chars:
            remain = max_chars - total
            if remain > 0:
                parts.append(chunk[:remain])
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n---\n".join(parts).strip()


def pretty_sources(matches, max_items=10):
    for m in matches[:max_items]:
        md = m.get("metadata") or {}
        fname = md.get("file_name") or "client"
        idx = md.get("chunk_index")
        score = m.get("score")
        snippet = shorten(
            (md.get("text") or "").replace("\n", " "), width=140, placeholder="…"
        )
        print(
            f"- id={m['id']} | file={fname} | chunk={idx} | score={score:.4f} | {snippet}"
        )


def main():
    # 1) embed question
    q_vec = embed_query(RAG_QUERY, OPENAI_EMBED_MODEL)

    # 2) pinecone search
    results = index.query(
        namespace=PINECONE_NAMESPACE,
        vector=q_vec,
        top_k=RAG_TOP_K,
        include_metadata=True,
    )
    matches = (
        results.get("matches", [])
        if isinstance(results, dict)
        else getattr(results, "matches", [])
    )
    context = build_context(matches, max_chars=RAG_MAX_CONTEXT_CHARS)

    # 3) call chat model with context
    system_prompt = (
        "You are a helpful assistant. Use the provided context to answer. "
        "If context is insufficient, say so briefly and avoid speculation."
    )
    user_prompt = f"Question:\n{RAG_QUERY}\n\nContext:\n{context if context else '[no context found]'}"

    chat = oai.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    answer = chat.choices[0].message.content

    # 4) print
    print("\n=== ANSWER ===\n")
    print(answer.strip())
    print("\n=== SOURCES ===\n")
    if matches:
        pretty_sources(matches)
    else:
        print("No matches found (answered without context).")


if __name__ == "__main__":
    main()
