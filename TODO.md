# AI Aleks — Build TODO

Status legend: ✅ Done | 🔄 In Progress | ⬜ Not started

---

## Phase 1: Data Pipeline ✅

- ✅ Scrape YouTube comments (324 comments, 8 topic clusters identified)
- ✅ Fetch all channel transcripts — 87/93 videos (`scripts/fetch_transcripts_ytdlp.py`)
- ✅ Chunk + embed transcripts into Pinecone (`scripts/ingest.py`)
  - 399 chunks, BAAI/bge-small-en-v1.5 (384 dims), index: "aleksgornik"

---

## Phase 2: Backend API ✅

- ✅ Set up FastAPI project structure (`backend/`)
- ✅ RAG query endpoint — embed query → Pinecone top-k → LLM with context → streaming response
- ✅ Choose and integrate LLM (Claude claude-opus-4-8 with adaptive thinking, streaming SSE)
- ✅ Kit.com email-gate endpoint — POST name+email → subscribe to Kit form → return session token
- ✅ Rate limiting — 10 messages/day per user, in-memory (swap for Redis in production)
- ✅ Persona system prompt — crafted "sounds like Aleks" prompt in `backend/persona.py`
- ✅ Weekly auto-ingestion script (`scripts/ingest_new.py`) — fetch only new videos since last run

---

## Phase 3: Frontend ✅

- ✅ Landing page — cinematic hero, typewriter demo, ambient orb glows, grid bg
- ✅ Email gate flow — glassmorphic form → `/auth/register` → unlock chat
- ✅ Chat UI — streaming SSE display, typing dots, starter questions, auto-resize input
- ✅ Rate limit UI — live "X left today" badge in chat header, turns red at ≤2

---

## Phase 4: Deployment ⬜

- ⬜ Containerise backend (Dockerfile)
- ⬜ Deploy backend (Railway / Render / Fly.io)
- ⬜ Deploy frontend (Vercel)
- ⬜ Set up weekly ingest cron job
- ⬜ Connect custom domain (ai.aleksgornik.com)

---

## Phase 5: Growth / Monetisation ⬜

- ⬜ Analytics — track questions asked, most common topics
- ⬜ Paid tier — unlimited messages via Stripe
- ⬜ Promote on YouTube channel + newsletter
