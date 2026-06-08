#!/usr/bin/env python3
"""
Ingest YouTube transcripts into Pinecone using local BAAI/bge-small-en-v1.5 embeddings.

Pipeline:
  1. Load each transcript JSON from content/transcripts/
  2. Chunk into overlapping windows (~400 words, 50-word overlap)
  3. Embed locally with bge-small-en-v1.5 (384 dims, no API key needed)
  4. Upsert into Pinecone index "aleksgornik"

Idempotent: safe to re-run; existing vectors are overwritten by the same IDs.
Also used by the weekly auto-ingestion job (scripts/ingest_new.py).

Usage:
    python scripts/ingest.py              # full ingest
    python scripts/ingest.py --dry-run    # show chunk stats, skip embed/upsert
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

PINECONE_API_KEY = os.getenv("PINECONE_DEFAULT_API_KEY")

TRANSCRIPT_DIR = Path(__file__).parent.parent / "content" / "transcripts"
INDEX_NAME = "aleksgornik"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMS = 384

# Chunking — word-based windows
CHUNK_WORDS = 400
OVERLAP_WORDS = 50

# Pinecone upsert batch limit
UPSERT_BATCH_SIZE = 100


def load_embedding_model() -> SentenceTransformer:
    print(f"Loading embedding model {EMBEDDING_MODEL} (downloads once, ~130MB)...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("Model ready.")
    return model


def chunk_text(text: str) -> list:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end == len(words):
            break
        start += CHUNK_WORDS - OVERLAP_WORDS
    return chunks


def load_transcripts() -> list:
    transcripts = []
    for path in sorted(TRANSCRIPT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("transcript", "").strip():
            transcripts.append(data)
    return transcripts


def build_chunks(transcripts: list) -> list:
    all_chunks = []
    for t in transcripts:
        vid = t["video_id"]
        chunks = chunk_text(t["transcript"])
        for i, text in enumerate(chunks):
            all_chunks.append({
                "id": f"{vid}_{i}",
                "text": text,
                "metadata": {
                    "video_id": vid,
                    "title": t["title"],
                    "url": t["url"],
                    "published_at": t.get("published_at", "unknown"),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            })
    return all_chunks


def embed_chunks(chunks: list, model: SentenceTransformer) -> list:
    print(f"Embedding {len(chunks)} chunks locally...")
    texts = [c["text"] for c in chunks]
    t0 = time.time()
    # normalize_embeddings=True is required for bge models (cosine similarity)
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=64)
    print(f"Embedding done in {time.time() - t0:.1f}s")
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()
    return chunks


def get_or_create_index(pc: Pinecone):
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{INDEX_NAME}' ({EMBEDDING_DIMS} dims, cosine)...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print("Waiting for index to be ready...", end=" ", flush=True)
        for _ in range(30):
            desc = pc.describe_index(INDEX_NAME)
            if desc.status.get("ready", False):
                break
            time.sleep(2)
            print(".", end="", flush=True)
        print(" ready.")
    else:
        print(f"Using existing Pinecone index '{INDEX_NAME}'.")
    return pc.Index(INDEX_NAME)


def upsert_to_pinecone(chunks: list, index) -> None:
    total = len(chunks)
    print(f"Upserting {total} vectors to Pinecone...")
    for batch_start in range(0, total, UPSERT_BATCH_SIZE):
        batch = chunks[batch_start: batch_start + UPSERT_BATCH_SIZE]
        vectors = [{"id": c["id"], "values": c["embedding"], "metadata": c["metadata"]} for c in batch]
        batch_num = batch_start // UPSERT_BATCH_SIZE + 1
        total_batches = (total + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(vectors)} vectors)...", end=" ", flush=True)
        index.upsert(vectors=vectors)
        print("done")
    print(f"All {total} vectors upserted.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show stats only, skip embed/upsert.")
    args = parser.parse_args()

    if not PINECONE_API_KEY and not args.dry_run:
        print("Error: PINECONE_DEFAULT_API_KEY not set in .env")
        sys.exit(1)

    print("Loading transcripts...")
    transcripts = load_transcripts()
    print(f"Loaded {len(transcripts)} transcripts.")

    chunks = build_chunks(transcripts)
    print(f"Built {len(chunks)} chunks ({sum(len(c['text'].split()) for c in chunks):,} total words)")

    if args.dry_run:
        from collections import Counter
        print("\n--- Top 5 videos by chunk count ---")
        for title, n in Counter(c["metadata"]["title"] for c in chunks).most_common(5):
            print(f"  {n:3d} chunks — {title[:60]}")
        return

    model = load_embedding_model()
    chunks = embed_chunks(chunks, model)

    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = get_or_create_index(pc)
    upsert_to_pinecone(chunks, index)

    stats = index.describe_index_stats()
    print(f"\nPinecone index stats: {stats['total_vector_count']} total vectors")
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
