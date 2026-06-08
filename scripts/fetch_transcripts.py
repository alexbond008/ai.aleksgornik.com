#!/usr/bin/env python3
"""
Fetch all YouTube transcripts for @aleksgornik and save to content/transcripts/.

Uses youtube-transcript-api (v1.2.4) with the YouTube Data API v3 for
channel/video enumeration and the transcript API for subtitle retrieval.

If YouTube is blocking your IP, you can configure a proxy by setting
these environment variables in .env:
    PROXY_HTTP_URL=http://user:pass@proxy-host:port
    PROXY_HTTPS_URL=http://user:pass@proxy-host:port

Usage:
    python scripts/fetch_transcripts.py
"""

import os
import json
import time
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    RequestBlocked,
)

# Load env variables from root .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

YT_API_KEY = os.getenv("YT_DATA_API_KEY_V3")
CHANNEL_HANDLE = "@aleksgornik"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../content/transcripts")

# Proxy config (optional — set in .env if your IP is blocked)
PROXY_HTTP = os.getenv("PROXY_HTTP_URL")
PROXY_HTTPS = os.getenv("PROXY_HTTPS_URL")

# Rate limiting
DELAY_BETWEEN_VIDEOS = 2  # seconds between fetches
RETRY_MAX = 3
RETRY_DELAY = 30  # seconds, doubled each retry


def get_youtube_client():
    """Build the YouTube Data API v3 client."""
    if not YT_API_KEY:
        raise ValueError("YT_DATA_API_KEY_V3 not found in .env file.")
    return build("youtube", "v3", developerKey=YT_API_KEY)


def get_transcript_api():
    """
    Build the YouTubeTranscriptApi instance, optionally with proxy support.

    Per the docs (https://github.com/jdepoix/youtube-transcript-api):
      - Use GenericProxyConfig for any HTTP/HTTPS/SOCKS proxy
      - Use WebshareProxyConfig for Webshare residential proxies
    """
    proxy_config = None

    if PROXY_HTTP or PROXY_HTTPS:
        from youtube_transcript_api.proxies import GenericProxyConfig
        proxy_config = GenericProxyConfig(
            http_url=PROXY_HTTP,
            https_url=PROXY_HTTPS,
        )
        print(f"🔒 Using proxy: {PROXY_HTTPS or PROXY_HTTP}")

    return YouTubeTranscriptApi(proxy_config=proxy_config)


def get_channel_videos(youtube, handle):
    """Enumerate all videos on a channel using the YouTube Data API v3."""
    print(f"📋 Resolving channel handle: {handle}...")

    # Get channel ID & uploads playlist
    response = youtube.channels().list(
        part="id,snippet,contentDetails",
        forHandle=handle
    ).execute()

    if not response.get("items"):
        # Fallback to search
        print(f"   Handle search failed, trying keyword search for {handle}...")
        search_res = youtube.search().list(
            part="snippet", q=handle, type="channel", maxResults=1
        ).execute()
        if not search_res.get("items"):
            raise ValueError(f"Could not find channel for {handle}")
        channel_id = search_res["items"][0]["snippet"]["channelId"]
        response = youtube.channels().list(
            part="id,snippet,contentDetails", id=channel_id
        ).execute()

    channel = response["items"][0]
    channel_title = channel["snippet"]["title"]
    uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"   Channel: {channel_title} ({channel['id']})")
    print(f"   Uploads playlist: {uploads_playlist_id}")

    # Paginate through all videos
    videos = []
    next_page_token = None
    print("   Fetching video list...")

    while True:
        res = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in res.get("items", []):
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
            })

        next_page_token = res.get("nextPageToken")
        if not next_page_token:
            break

    print(f"✅ Found {len(videos)} videos.\n")
    return videos


def fetch_transcript(ytt_api, video_id):
    """
    Fetch English transcript for a video using youtube-transcript-api.

    Returns the full transcript as a single string, or None if unavailable.
    Includes retry logic with exponential backoff for RequestBlocked errors.
    """
    for attempt in range(RETRY_MAX):
        try:
            # Fetch the transcript — the API returns a FetchedTranscript object
            fetched = ytt_api.fetch(video_id, languages=['en'])

            # Join all snippet texts into a single string
            full_text = " ".join(snippet.text for snippet in fetched)
            return full_text

        except (TranscriptsDisabled, NoTranscriptFound):
            # Video genuinely has no transcripts
            return None

        except RequestBlocked:
            if attempt < RETRY_MAX - 1:
                delay = RETRY_DELAY * (2 ** attempt)
                print(f"         ⏳ IP blocked. Waiting {delay}s (retry {attempt + 1}/{RETRY_MAX})...")
                time.sleep(delay)
            else:
                print(f"         ⛔ IP blocked after {RETRY_MAX} retries. Stopping.")
                raise

        except Exception as e:
            print(f"         ⚠️  Unexpected error: {type(e).__name__}: {e}")
            return None

    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Build API clients
    youtube = get_youtube_client()
    ytt_api = get_transcript_api()

    # 2. Get all videos
    videos = get_channel_videos(youtube, CHANNEL_HANDLE)

    # 3. Fetch transcripts
    fetched = 0
    skipped = 0
    failed = 0
    failed_videos = []

    try:
        for i, video in enumerate(videos, 1):
            vid = video["video_id"]
            out_path = os.path.join(OUTPUT_DIR, f"{vid}.json")

            # Skip already-downloaded transcripts (idempotent)
            if os.path.exists(out_path):
                print(f"[{i}/{len(videos)}] ⏭  Skipping {vid} (already exists)")
                skipped += 1
                continue

            print(f"[{i}/{len(videos)}] 📥 Fetching: {video['title']} ({vid})...")
            transcript = fetch_transcript(ytt_api, vid)

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
                print(f"         ✅ Saved ({len(transcript)} chars)")
            else:
                failed += 1
                failed_videos.append(f"{video['title']} ({vid})")
                print(f"         ❌ No transcript available")

            # Rate limiting between requests
            if i < len(videos):
                time.sleep(DELAY_BETWEEN_VIDEOS)

    except RequestBlocked:
        print("\n⛔ YouTube is blocking your IP. Options:")
        print("   1. Wait a few hours and try again")
        print("   2. Set PROXY_HTTP_URL / PROXY_HTTPS_URL in .env")
        print("      (e.g. from webshare.io residential proxies)")
        print("   3. Run from a different network (mobile hotspot, VPN)")
        print("\n   Already-fetched transcripts are saved. Re-run to resume.\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted! Run again to resume (existing files will be skipped).")

    # Summary
    total_on_disk = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")])
    print(f"\n{'='*60}")
    print(f"🏁 Done!")
    print(f"   New transcripts fetched : {fetched}")
    print(f"   Skipped (already exist) : {skipped}")
    print(f"   Failed / no subtitles   : {failed}")
    print(f"   Total transcripts saved : {total_on_disk}")
    print(f"{'='*60}")

    if failed_videos:
        print(f"\n📋 Videos without transcripts:")
        for v in failed_videos:
            print(f"   - {v}")


if __name__ == "__main__":
    main()
