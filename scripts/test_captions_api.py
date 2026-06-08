import os
import json
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

API_KEY = os.getenv("YT_DATA_API_KEY_V3")
VIDEO_ID = "Z9ORNgEb4Kg" # From previous logs

def test_captions_api():
    if not API_KEY:
        print("API_KEY missing")
        return
        
    youtube = build("youtube", "v3", developerKey=API_KEY)
    
    try:
        print(f"Listing captions for video: {VIDEO_ID}")
        response = youtube.captions().list(
            part="snippet",
            videoId=VIDEO_ID
        ).execute()
        print(json.dumps(response, indent=2))
        
        if "items" in response and response["items"]:
            caption_id = response["items"][0]["id"]
            print(f"Attempting to download caption: {caption_id}")
            # This usually requires OAuth
            download = youtube.captions().download(id=caption_id).execute()
            print("Download successful (first 100 chars):")
            print(download.decode("utf-8")[:100])
        else:
            print("No caption tracks found.")
            
    except HttpError as e:
        print(f"HTTP Error: {e.resp.status} - {e.content.decode()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_captions_api()
