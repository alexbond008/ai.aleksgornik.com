"""
RAG query pipeline: embed query → Pinecone top-k → build prompt.
Embedding uses the same local bge-small-en-v1.5 as ingest.py.
"""

import os
from typing import List, Optional

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

INDEX_NAME = "aleksgornik"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
TOP_K = 5

_embedding_model: Optional[SentenceTransformer] = None
_pinecone_index = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        api_key = os.getenv("PINECONE_DEFAULT_API_KEY")
        pc = Pinecone(api_key=api_key)
        _pinecone_index = pc.Index(INDEX_NAME)
    return _pinecone_index


def retrieve_context(query: str) -> List[dict]:
    """Embed query and retrieve top-k relevant chunks from Pinecone."""
    model = get_embedding_model()
    embedding = model.encode(query, normalize_embeddings=True).tolist()

    index = get_pinecone_index()
    results = index.query(vector=embedding, top_k=TOP_K, include_metadata=True)

    chunks = []
    for match in results.get("matches", []):
        meta = match.get("metadata", {})
        chunks.append({
            "text": meta.get("text", ""),
            "title": meta.get("title", ""),
            "url": meta.get("url", ""),
            "score": match.get("score", 0),
        })
    return chunks


def build_rag_prompt(query: str, chunks: List[dict]) -> str:
    """Build the user message that includes retrieved context."""
    if not chunks:
        return query

    context_lines = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk['title']}]({chunk['url']})" if chunk.get("url") else chunk.get("title", "")
        context_lines.append(f"--- Excerpt {i} from {source} ---\n{chunk['text']}")

    context_block = "\n\n".join(context_lines)

    return f"""Here are relevant excerpts from my YouTube videos to help answer this question:

{context_block}

---

Question: {query}

Answer based on the excerpts above where relevant. Speak in my voice as described in your instructions."""
