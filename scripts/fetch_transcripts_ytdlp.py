#!/usr/bin/env python3
"""
Fetch YouTube transcripts for @aleksgornik and save to content/transcripts/.

Uses yt-dlp to download VTT subtitle files (manual or auto-generated),
parses them into clean text, and saves as JSON. No ffmpeg required.

Idempotent: skips videos already saved. Re-run to resume after interruption.

Usage:
    python scripts/fetch_transcripts_ytdlp.py
"""

import json
import os
import re
import subprocess
import sys
import time
import shutil
from pathlib import Path
from typing import List, Optional

CHANNEL_URL = "https://www.youtube.com/@aleksgornik"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "content", "transcripts")
YT_DLP_BIN = "yt-dlp"

DELAY_BETWEEN_VIDEOS = 3
RETRY_MAX = 3
RETRY_BASE_DELAY = 30


def parse_vtt(vtt_text: str) -> str:
    """
    Parse a WebVTT file into clean transcript text.

    YouTube auto-generated VTT has overlapping cue lines (each cue shows
    the current + previous sentence). We deduplicate by only taking cues
    that represent a completed sentence boundary (the short duplicate cues
    with only a timestamp gap), then strip inline timing tags.
    """
    lines = []
    seen = set()

    for line in vtt_text.splitlines():
        line = line.strip()
        # Skip header, blank lines, and cue timing lines
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r"\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+", line):
            continue
        # Strip inline timing tags like <00:00:01.000><c> ... </c>
        line = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
        line = re.sub(r"</?c>", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        line = line.strip()
        if not line:
            continue
        # Deduplicate — VTT lines repeat as cues overlap
        if line not in seen:
            seen.add(line)
            lines.append(line)

    return " ".join(lines)


def get_video_list() -> List[dict]:
    """Enumerate all videos on the channel without downloading."""
    print(f"Listing all videos on {CHANNEL_URL} ...")
    cmd = [
        YT_DLP_BIN,
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        "--no-warnings",
        CHANNEL_URL,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        print(f"yt-dlp error listing videos:\n{result.stderr}")
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

    print(f"Found {len(videos)} videos.\n")
    return videos


def fetch_transcript(video_id: str, work_dir: str) -> Optional[str]:
    """
    Download VTT subtitles for a single video.
    Prefers manual captions (en-orig) over auto-generated (en).
    Returns clean transcript text, or None if unavailable.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(RETRY_MAX):
        cmd = [
            YT_DLP_BIN,
            "--skip-download",
            "--write-sub",
            "--write-auto-sub",
            "--sub-langs", "en-orig,en",
            # No --convert-subs — keep native VTT to avoid ffmpeg dependency
            "--no-warnings",
            "--ignore-errors",
            "-o", os.path.join(work_dir, "%(id)s.%(ext)s"),
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

        if "429" in result.stderr or "Too Many Requests" in result.stderr:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"         Rate limited (429). Waiting {delay}s (retry {attempt + 1}/{RETRY_MAX})...")
            time.sleep(delay)
            continue

        # Prefer manual captions (en-orig) over auto-generated (en)
        vtt_file = None
        for suffix in [f"{video_id}.en-orig.vtt", f"{video_id}.en.vtt"]:
            candidate = Path(work_dir) / suffix
            if candidate.exists():
                vtt_file = candidate
                break

        if vtt_file:
            vtt_text = vtt_file.read_text(encoding="utf-8", errors="replace")
            transcript = parse_vtt(vtt_text)
            for f in Path(work_dir).glob(f"{video_id}*"):
                f.unlink(missing_ok=True)
            return transcript if transcript.strip() else None

        # No VTT found and no rate limit — subtitles genuinely unavailable
        break

    for f in Path(work_dir).glob(f"{video_id}*"):
        f.unlink(missing_ok=True)
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        ver = subprocess.run([YT_DLP_BIN, "--version"], capture_output=True, text=True, timeout=10)
        print(f"Using yt-dlp version: {ver.stdout.strip()}")
    except FileNotFoundError:
        print("yt-dlp not found. Install via: brew install yt-dlp")
        sys.exit(1)

    videos = get_video_list()
    if not videos:
        print("No videos found. Exiting.")
        sys.exit(1)

    work_dir = os.path.join(os.path.dirname(__file__), "..", "content", ".tmp_subs")
    os.makedirs(work_dir, exist_ok=True)

    fetched = 0
    skipped = 0
    failed = 0
    failed_videos = []

    try:
        for i, video in enumerate(videos, 1):
            vid = video["video_id"]
            out_path = os.path.join(OUTPUT_DIR, f"{vid}.json")

            if os.path.exists(out_path):
                print(f"[{i}/{len(videos)}] Skipping {vid} (already exists)")
                skipped += 1
                continue

            print(f"[{i}/{len(videos)}] Fetching: {video['title']} ({vid})...")
            transcript = fetch_transcript(vid, work_dir)

            if transcript:
                data = {
                    "video_id": vid,
                    "title": video["title"],
                    "published_at": video["published_at"],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "transcript": transcript,
                }
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                fetched += 1
                print(f"         Saved ({len(transcript)} chars)")
            else:
                failed += 1
                failed_videos.append(f"{video['title']} ({vid})")
                print(f"         No transcript available")

            if i < len(videos):
                time.sleep(DELAY_BETWEEN_VIDEOS)

    except KeyboardInterrupt:
        print("\nInterrupted. Run again to resume (existing files are skipped).")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    total_on_disk = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")])
    print(f"\n{'='*60}")
    print(f"Done!")
    print(f"  New transcripts fetched : {fetched}")
    print(f"  Skipped (already exist) : {skipped}")
    print(f"  Failed / no subtitles   : {failed}")
    print(f"  Total transcripts saved : {total_on_disk}")
    print(f"{'='*60}")

    if failed_videos:
        print(f"\nVideos without transcripts:")
        for v in failed_videos:
            print(f"  - {v}")


if __name__ == "__main__":
    main()
