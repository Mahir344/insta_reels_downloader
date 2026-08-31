from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import instaloader
import re

app = FastAPI(
    title="Instagram Reel Downloader API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# Enable CORS for web frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Instaloader (disable saving metadata locally)
L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_history=False
)

def extract_shortcode(url: str) -> str:
    """Extracts the Instagram shortcode from a Reel/Post URL."""
    pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:reel|p)/([^/?#&]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Instagram Reel URL format.")

@app.get("/api/download")
async def download_reel(url: str = Query(..., description="Instagram Reel URL")):
    try:
        shortcode = extract_shortcode(url)
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        if not post.is_video:
            raise HTTPException(status_code=400, detail="Provided URL is not a video/reel.")

        return {
            "status": "success",
            "data": {
                "title": post.caption if post.caption else "Instagram Reel",
                "shortcode": shortcode,
                "video_url": post.video_url,
                "thumbnail_url": post.url,
                "duration": post.video_duration,
                "owner": post.owner_username,
                "likes": post.likes,
                "comments": post.comments
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except instaloader.exceptions.InstaloaderException as ie:
        raise HTTPException(status_code=500, detail=f"Instagram extraction error: {str(ie)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "API is operational"}
  
