FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY scripts/ingest.py ./scripts/ingest.py
COPY scripts/fetch_transcripts_ytdlp.py ./scripts/fetch_transcripts_ytdlp.py

# Pre-download the embedding model so first request isn't slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

EXPOSE 8001

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8001}
