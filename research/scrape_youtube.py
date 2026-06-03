import os
import json
import time
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load env variables from root .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

API_KEY = os.getenv("YT_DATA_API_KEY_V3")
CHANNEL_HANDLE = "@aleksgornik"

def get_youtube_client():
    if not API_KEY:
        raise ValueError("YT_DATA_API_KEY_V3 not found in environment or .env file.")
    return build("youtube", "v3", developerKey=API_KEY)

def get_channel_details(youtube, handle):
    print(f"Resolving channel handle: {handle}...")
    try:
        # Standard API for handles
        response = youtube.channels().list(
            part="id,snippet,contentDetails",
            forHandle=handle
        ).execute()
        
        if not response.get("items"):
            # Fallback to search query
            print(f"Handle search returned no results, trying search query for {handle}...")
            search_response = youtube.search().list(
                part="snippet",
                q=handle,
                type="channel",
                maxResults=1
            ).execute()
            if not search_response.get("items"):
                raise ValueError(f"Could not resolve channel for handle {handle}")
            channel_id = search_response["items"][0]["snippet"]["channelId"]
            response = youtube.channels().list(
                part="id,snippet,contentDetails",
                id=channel_id
            ).execute()
            
        channel = response["items"][0]
        channel_id = channel["id"]
        channel_title = channel["snippet"]["title"]
        uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
        print(f"Resolved to Channel ID: {channel_id} ('{channel_title}')")
        print(f"Uploads Playlist ID: {uploads_playlist_id}")
        return channel_id, uploads_playlist_id
    except HttpError as e:
        print(f"HTTP Error occurred: {e}")
        raise e

def get_channel_videos(youtube, playlist_id):
    print("Fetching channel videos from uploads playlist...")
    videos = []
    next_page_token = None
    
    while True:
        try:
            response = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            for item in response.get("items", []):
                snippet = item["snippet"]
                video_id = item["contentDetails"]["videoId"]
                videos.append({
                    "video_id": video_id,
                    "title": snippet["title"],
                    "description": snippet["description"],
                    "published_at": snippet["publishedAt"]
                })
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        except HttpError as e:
            print(f"Error fetching playlist items: {e}")
            break
            
    print(f"Found {len(videos)} videos.")
    return videos

def get_video_comments(youtube, video_id, video_title):
    comments = []
    next_page_token = None
    
    # We fetch top comments per video
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            textFormat="plainText",
            pageToken=next_page_token
        ).execute()
        
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id": item["id"],
                "video_id": video_id,
                "video_title": video_title,
                "author": snippet["authorDisplayName"],
                "text": snippet["textDisplay"],
                "like_count": snippet["likeCount"],
                "published_at": snippet["publishedAt"],
                "reply_count": item["snippet"]["totalReplyCount"]
            })
    except HttpError as e:
        # 403 error means comments are disabled for this video, which is normal
        if hasattr(e, 'resp') and e.resp.status == 403:
            pass
        elif "commentsDisabled" in str(e):
            pass
        else:
            print(f"Error fetching comments for video {video_id}: {e}")
            
    return comments

def main():
    try:
        youtube = get_youtube_client()
        channel_id, uploads_playlist_id = get_channel_details(youtube, CHANNEL_HANDLE)
        videos = get_channel_videos(youtube, uploads_playlist_id)
        
        all_comments = []
        total_videos = len(videos)
        
        print(f"Scraping comments for {total_videos} videos...")
        for i, video in enumerate(videos, 1):
            print(f"[{i}/{total_videos}] Scraping: {video['title']}...")
            comments = get_video_comments(youtube, video["video_id"], video["title"])
            all_comments.extend(comments)
            print(f"  -> Found {len(comments)} comments.")
            # Small sleep to be friendly to YouTube API limits
            time.sleep(0.05)
            
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        output_file = os.path.join(data_dir, "raw_comments.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_comments, f, indent=2, ensure_ascii=False)
            
        print(f"\nSuccess! Scraped {len(all_comments)} total comments and saved to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
