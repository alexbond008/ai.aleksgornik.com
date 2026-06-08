#!/usr/bin/env python3
"""
Weekly auto-ingestion: fetch only new YouTube videos and add them to Pinecone.

How it works:
  1. List all videos on the channel.
  2. Skip any video already saved in content/transcripts/.
  3. Fetch transcripts for new videos only (via yt-dlp).
  4. Chunk + embed + upsert to Pinecone (same pipeline as ingest.py).

Run via cron weekly, or manually after publishing a new video:
    python scripts/ingest_new.py

Idempotent: safe to run any time.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

TRANSCRIPT_DIR = Path(__file__).parent.parent / "content" / "transcripts"
CHANNEL_URL = "https://www.youtube.com/@aleksgornik"
YT_DLP_BIN = "yt-dlp"
DELAY_BETWEEN_VIDEOS = 3
RETRY_MAX = 3
RETRY_BASE_DELAY = 30


def get_video_list():
    print(f"Listing videos on {CHANNEL_URL}...")
    cmd = [
        YT_DLP_BIN,
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        "--no-warnings",
        CHANNEL_URL,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr}")
        sys.exit(1)

    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        vid = parts[0].strip()
        title = parts[1].strip()
        upload_date = parts[2].strip() if len(parts) > 2 else "unknown"
        if re.match(r"^\d{8}$", upload_date):
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        videos.append({"video_id": vid, "title": title, "published_at": upload_date})
    return videos


def fetch_transcript(video_id, work_dir):
    url = f"https://www.youtube.com/watch?v={video_id}"
    for attempt in range(RETRY_MAX):
        cmd = [
            YT_DLP_BIN,
            "--skip-download",
            "--write-sub", "--write-auto-sub",
            "--sub-langs", "en-orig,en",
            "--no-warnings", "--ignore-errors",
            "-o", os.path.join(work_dir, "%(id)s.%(ext)s"),
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if "429" in result.stderr or "Too Many Requests" in result.stderr:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"  Rate limited. Waiting {delay}s...")
            time.sleep(delay)
            continue

        vtt_file = None
        for suffix in [f"{video_id}.en-orig.vtt", f"{video_id}.en.vtt"]:
            candidate = Path(work_dir) / suffix
            if candidate.exists():
                vtt_file = candidate
                break

        if vtt_file:
            vtt_text = vtt_file.read_text(encoding="utf-8", errors="replace")
            from scripts.fetch_transcripts_ytdlp import parse_vtt
            transcript = parse_vtt(vtt_text)
            for f in Path(work_dir).glob(f"{video_id}*"):
                f.unlink(missing_ok=True)
            return transcript if transcript.strip() else None
        break

    for f in Path(work_dir).glob(f"{video_id}*"):
        f.unlink(missing_ok=True)
    return None


def main():
    videos = get_video_list()
    existing_ids = {p.stem for p in TRANSCRIPT_DIR.glob("*.json")}

    new_videos = [v for v in videos if v["video_id"] not in existing_ids]
    if not new_videos:
        print(f"No new videos found ({len(videos)} total, all already ingested).")
        return

    print(f"Found {len(new_videos)} new video(s) to ingest.")

    work_dir = Path(__file__).parent.parent / "content" / ".tmp_subs"
    work_dir.mkdir(parents=True, exist_ok=True)

    new_transcripts = []
    try:
        for i, video in enumerate(new_videos, 1):
            vid = video["video_id"]
            print(f"[{i}/{len(new_videos)}] {video['title']} ({vid})...")
            transcript = fetch_transcript(vid, str(work_dir))
            if transcript:
                data = {
                    "video_id": vid,
                    "title": video["title"],
                    "published_at": video["published_at"],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "transcript": transcript,
                }
                out = TRANSCRIPT_DIR / f"{vid}.json"
                out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                new_transcripts.append(data)
                print(f"  Saved ({len(transcript)} chars)")
            else:
                print(f"  No transcript available, skipping.")

            if i < len(new_videos):
                time.sleep(DELAY_BETWEEN_VIDEOS)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    if not new_transcripts:
        print("No new transcripts could be fetched.")
        return

    # Embed and upsert new chunks only
    from scripts.ingest import (
        build_chunks,
        embed_chunks,
        get_or_create_index,
        load_embedding_model,
        upsert_to_pinecone,
    )
    from pinecone import Pinecone

    model = load_embedding_model()
    chunks = build_chunks(new_transcripts)
    print(f"Built {len(chunks)} new chunks.")
    chunks = embed_chunks(chunks, model)

    pc = Pinecone(api_key=os.getenv("PINECONE_DEFAULT_API_KEY"))
    index = get_or_create_index(pc)
    upsert_to_pinecone(chunks, index)

    stats = index.describe_index_stats()
    print(f"\nDone. Pinecone now has {stats['total_vector_count']} total vectors.")


if __name__ == "__main__":
    main()
