from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import re

from django.conf import settings
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from pinecone.openapi_support.exceptions import NotFoundException

try:
    from documents.services.chunking import chunk_text
except Exception:

    def chunk_text(
        text: str,
        max_tokens: int = 800,
        overlap_tokens: int = 120,
        token_model: str = "cl100k_base",
    ):
        paras = [
            p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()
        ]
        chunks = []
        for i, p in enumerate(paras):
            h = hashlib.sha256(p.encode("utf-8")).hexdigest()
            chunks.append({"text": p, "hash": h, "index": i})
        return chunks


def _model_for_dim(dim: int) -> str:
    return "text-embedding-3-large" if dim == 3072 else "text-embedding-3-small"


def _embedding_dim(model_name: str) -> int:
    return 3072 if "large" in model_name else 1536


# Helper to infer section labels from chunk text
def _infer_section_label(text: str) -> Optional[str]:
    """
    Cheap heuristic to tag chunks with a section label like "6.0 RETENTION" if present
    at the beginning of the chunk. Helps retrieval ranking and UX display.
    """
    try:
        head = (text or "").strip().split("\n", 1)[0][:120]
        m = re.search(r"\b(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s]{2,})\b", head)
        if m:
            return f"{m.group(1)} {m.group(2).strip()}"
    except Exception:
        return None
    return None


class PineconeEmbedding:
    """
    Chunk → embed → upsert to Pinecone, idempotent per-document.

    - Deterministic vector IDs: <doc_id>:<chunk_index>:<hash8>
    - Deletes previous vectors for the same document (in the same namespace) before upsert
    - Metadata kept concise; includes 'text' (optionally truncate if you want)
    """

    def __init__(
        self,
        index_name: Optional[str] = None,
        namespace: Optional[str] = None,
        embed_model: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.index_name = index_name or getattr(
            settings, "PINECONE_INDEX_NAME", "ai-docs-index"
        )
        self.namespace = namespace or "default"
        self.embed_model = embed_model or getattr(
            settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.dimension = _embedding_dim(self.embed_model)
        self.region = region or getattr(settings, "PINECONE_REGION", "us-east-1")

        # Clients
        api_key = getattr(settings, "PINECONE_API_KEY", None)
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY not configured")
        self.pc = Pinecone(api_key=api_key)

        oai_key = getattr(settings, "OPENAI_API_KEY", None)
        if not oai_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        self.oa = OpenAI(api_key=oai_key)

        # Ensure index
        self._ensure_index()
        self.index = self.pc.Index(self.index_name)

    # ---------- Index / namespace utilities ----------

    def _ensure_index(self):
        if not self.pc.has_index(self.index_name):
            # create with the requested model's dim
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=self.region),
            )
        else:
            desc = self.pc.describe_index(self.index_name)
            idx_dim = getattr(desc, "dimension", None)
            if not idx_dim:
                raise RuntimeError(
                    f"Could not read dimension for index {self.index_name}"
                )

            # If index exists with a different dim, switch the embed model to match the index
            if idx_dim != self.dimension:
                self.dimension = idx_dim
                self.embed_model = _model_for_dim(idx_dim)

    def list_namespaces(self) -> List[str]:
        stats = self.pc.Index(self.index_name).describe_index_stats()
        return list(stats.get("namespaces", {}).keys())

    def delete_namespace_index(self, namespace: Optional[str] = None):
        ns = namespace or self.namespace
        try:
            self.pc.Index(self.index_name).delete(delete_all=True, namespace=ns)
        except NotFoundException:
            return

    def _delete_vectors_for_document(self, document_id: str):
        """Remove previous vectors for this document within this namespace (if present)."""
        # Skip if namespace doesn't exist yet (first upsert will create it)
        if not self._namespace_exists():
            return
        try:
            self.index.delete(
                namespace=self.namespace,
                filter={"document_id": {"$eq": document_id}},
            )
        except NotFoundException:
            # 404 when ns doesn't exist or nothing matched — treat as no-op
            return

    # ---------- Embeddings ----------

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        resp = self.oa.embeddings.create(model=self.embed_model, input=texts)
        return [d.embedding for d in resp.data]

    # ---------- Public API ----------

    def create_vector_embeddings(
        self,
        text: str,
        *,
        document_id: Optional[str],
        file_name: Optional[str],
        file_path: Optional[str],
        user: Any = None,
        truncate_metadata_text_to: Optional[int] = None,  # e.g., 1000 chars
    ) -> List[Dict[str, Any]]:
        """
        Chunk a single text, embed, and build Pinecone vectors (not upserted yet).
        """
        max_tokens = getattr(settings, "CHUNK_SIZE", 1000)
        overlap_tokens = getattr(settings, "CHUNK_OVERLAP", 200)
        chunks = chunk_text(text, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
        if not chunks:
            return []

        vectors: List[Dict[str, Any]] = []
        BATCH = 100
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            embeds = self._embed_batch([c["text"] for c in batch])
            for c, vec in zip(batch, embeds):
                meta_text = c["text"]
                if (
                    truncate_metadata_text_to
                    and len(meta_text) > truncate_metadata_text_to
                ):
                    meta_text = meta_text[:truncate_metadata_text_to]

                # Deterministic vector ID for idempotency
                base = f"{document_id or 'noid'}:{c['index']}:{c['hash'][:8]}"
                # Build metadata without nulls (Pinecone rejects null values)
                metadata: Dict[str, Any] = {
                    "document_id": document_id,
                    "file_name": file_name,
                    "file_path": file_path,
                    "chunk_index": c["index"],
                    "chunk_hash": c["hash"],
                    "text": meta_text,
                    "embedding_model": self.embed_model,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                inferred = _infer_section_label(meta_text)
                if inferred:
                    metadata["section_label"] = inferred
                # Financial tagging to help filtering/boosting
                try:
                    if re.search(r"£[\d,]+|contractor shall pay|subcontract sum", meta_text, re.I):
                        metadata["contains_financial_info"] = True
                except Exception:
                    pass
                vectors.append(
                    {
                        "id": base,
                        "values": vec,
                        "metadata": metadata,
                    }
                )
        return vectors

    def _namespace_exists(self) -> bool:
        """Return True if namespace exists; False otherwise."""
        try:
            stats = self.index.describe_index_stats()
            return self.namespace in (stats.get("namespaces") or {})
        except Exception:
            # If stats call fails, be conservative
            return False

    def upsert_vectors(self, vectors: List[Dict[str, Any]]):
        if not vectors:
            return
        BATCH = 100
        for i in range(0, len(vectors), BATCH):
            self.index.upsert(vectors=vectors[i : i + BATCH], namespace=self.namespace)

    def similarity_search(self, query: str, top_k: int = 7, filters: Optional[Dict[str, Any]] = None):
        emb = self._embed_batch([query])[0]
        return self.index.query(
            namespace=self.namespace,
            vector=emb,
            top_k=top_k,
            include_metadata=True,
            filter=filters or None,
        )

    def main(
        self,
        *,
        text: Optional[str],
        id: Optional[str] = None,
        file_name: Optional[str] = None,
        file_path: Optional[str] = None,
        user: Any = None,
        delete_namespace: Optional[str] = None,
        truncate_metadata_text_to: Optional[int] = 1200,
    ):
        """
        Entry point kept compatible with your view.
        - If file_path is like 'db://<uuid>', we treat that UUID as the canonical document_id.
        - Otherwise we fall back to `id` or a hash of `file_name+text`.
        """
        # Optional: nuke a namespace (used rarely)

        if delete_namespace:
            self.delete_namespace_index(delete_namespace)

        # Document identity
        document_id = self._parse_document_id(file_path) or id
        if not document_id:
            seed = (file_name or "") + (text or "")[:128]
            document_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

        # Idempotency: clear old vectors for this document in this namespace
        if self._namespace_exists():
            self._delete_vectors_for_document(document_id)
        # else: no-op; upsert will auto-create the namespace

        # Create vectors (chunk → embed)
        vectors = self.create_vector_embeddings(
            text=text or "",
            document_id=document_id,
            file_name=file_name,
            file_path=file_path,
            user=user,
            truncate_metadata_text_to=truncate_metadata_text_to,
        )
        # Upsert
        self.upsert_vectors(vectors)
        return {
            "upserted": len(vectors),
            "document_id": document_id,
            "namespace": self.namespace,
        }

    @staticmethod
    def _parse_document_id(file_path: Optional[str]) -> Optional[str]:
        # expects "db://<uuid>" from your view
        if not file_path or not file_path.startswith("db://"):
            return None
        return file_path.split("db://", 1)[1]


# Optional thin wrapper if you want a service facade with extra helpers
class PineconeService:
    def __init__(self, namespace: Optional[str] = None):
        self.index_name = getattr(settings, "PINECONE_INDEX_NAME", "ai-docs-index")
        self.namespace = namespace
        self.engine = PineconeEmbedding(
            index_name=self.index_name, namespace=self.namespace
        )

    def store_text(
        self, *, document_id: str, text: str, file_name: str, file_path: str
    ):
        # Clears old vectors for this document and re-upserts new ones
        return self.engine.main(
            text=text, id=document_id, file_name=file_name, file_path=file_path
        )

    def search(self, query: str, top_k: int = 7):
        return self.engine.similarity_search(query, top_k=top_k)

    def wipe_document(self, document_id: str):
        self.engine._delete_vectors_for_document(document_id)

    def wipe_namespace(self):
        self.engine.delete_namespace_index(self.namespace)
