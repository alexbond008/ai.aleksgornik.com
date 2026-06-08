# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Aleks** — a RAG-powered chatbot that answers fan questions in the voice of Aleks Gornik (@aleksgornik on YouTube). Users exchange name + email (Kit.com lead capture) for access to a rate-limited chat interface backed by Aleks's full YouTube transcript library.

## Environment

All secrets live in `.env` at the project root. The venv is `.venv/` — always use `.venv/bin/python` and `.venv/bin/pip`.

Required env vars:
- `PINECONE_DEFAULT_API_KEY` — Pinecone vector DB
- `YT_DATA_API_KEY_V3` — YouTube Data API v3
- `KIT_API_KEY`, `KIT_FORM_ID`, `KIT_WAITLIST_FORM_ID` — Kit.com (ConvertKit) email capture
- `GEMINI_API_KEY`, `GROQ_API_KEY` — used by research scripts only
- `VOYAGEAI_API_KEY` — present but NOT used (switched to local bge-small)

## Common Commands

```bash
# Run any script
.venv/bin/python scripts/<script>.py

# Fetch all channel transcripts (idempotent — skips existing)
.venv/bin/python scripts/fetch_transcripts_ytdlp.py

# Full ingest: chunk → embed → upsert to Pinecone
.venv/bin/python scripts/ingest.py

# Dry run (shows chunk stats, skips embed/upsert)
.venv/bin/python scripts/ingest.py --dry-run

# Install a new dependency
.venv/bin/pip install <package>
```

## Architecture

### Data Pipeline (current state — complete)

```
YouTube channel (@aleksgornik)
  └─► scripts/fetch_transcripts_ytdlp.py   → content/transcripts/{video_id}.json
        └─► scripts/ingest.py              → Pinecone index "aleksgornik"
```

**Transcript format** (`content/transcripts/{video_id}.json`):
```json
{ "video_id": "...", "title": "...", "published_at": "YYYY-MM-DD", "url": "...", "transcript": "plain text" }
```

**Ingestion pipeline** (`scripts/ingest.py`):
- Chunks transcripts at 400-word windows with 50-word overlap
- Embeds locally using `BAAI/bge-small-en-v1.5` via `sentence_transformers` — **no API key, no cost, 384 dims**
- `normalize_embeddings=True` is required for bge models (cosine similarity)
- Upserts to Pinecone index `aleksgornik` (384 dims, cosine, AWS us-east-1)
- Chunk IDs are `{video_id}_{chunk_index}` — safe to re-run (upsert overwrites)
- Pinecone vector metadata: `video_id`, `title`, `url`, `published_at`, `chunk_index`, `total_chunks`

**Transcript fetching** (`scripts/fetch_transcripts_ytdlp.py`):
- Uses system `yt-dlp` (Homebrew) — no ffmpeg needed
- Downloads `.vtt` files and parses them natively (custom `parse_vtt()` deduplicates overlapping cue lines)
- Prefers manual captions (`en-orig.vtt`) over auto-generated (`en.vtt`)
- Idempotent — skips videos where `content/transcripts/{video_id}.json` already exists

### Application (to be built)

Planned stack:
- **Backend**: FastAPI (Python) in `backend/`
- **Frontend**: Landing page + chat UI in `frontend/`
- **RAG query flow**: embed user query with bge-small → query Pinecone top-k → inject retrieved chunks into Claude system prompt → stream response
- **Auth/lead gate**: name + email → POST to Kit.com API → issue session token → rate-limited chat access
- **Weekly auto-ingest**: `scripts/ingest_new.py` — fetch only new videos since last run, re-embed, upsert

### Research Scripts (reference only — not part of the app)

`research/` contains one-off EDA scripts:
- `scrape_youtube.py` — scraped raw comments via YouTube Data API → `research/data/raw_comments.json`
- `analyze_comments.py` — classified comments as questions/not-questions
- `advanced_analysis.py` — clustered questions into 8 topic categories using Gemini/Groq → `research/data/advanced_analysis.json`

The 8 topic clusters (from the research) are the canonical map of what AI Aleks needs to answer well: Incoming Freshmen, Major Selection, Math Difficulty, Career Paths, Study Resources, Career Prep/Internships, Motivation/Non-traditional Students, Creator Q&A.

## Key Constraints

- **Python 3.9** (system venv) — no union type hints (`X | Y`), use `Optional[X]` and `list` not `list[str]`
- Pinecone index dimensions are fixed at creation — changing the embedding model requires recreating the index
- yt-dlp requires no ffmpeg; do not add `--convert-subs srt` flags
