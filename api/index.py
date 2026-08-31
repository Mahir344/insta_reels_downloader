from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import instaloader
import re

app = FastAPI(
    title="Instagram Reel Downloader API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom User-Agent helps reduce instant 429/403 blocks from datacenter IPs
L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_history=False,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

def extract_shortcode(url: str) -> str:
    pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:reel|reels|p)/([^/?#&]+)'
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
            raise HTTPException(status_code=400, detail="Provided URL is not a video or reel.")

        return {
            "status": "success",
            "data": {
                "title": post.caption if post.caption else "",
                "shortcode": shortcode,
                "video_url": post.video_url,
                "thumbnail_url": post.url,
                "duration": post.video_duration,
                "owner": post.owner_username
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except instaloader.exceptions.ConnectionException:
        raise HTTPException(
            status_code=429, 
            detail="Instagram blocked the request (Rate Limited). Serverless IP blocked by Instagram."
        )
    except instaloader.exceptions.InstaloaderException as ie:
        raise HTTPException(status_code=500, detail=f"Instaloader error: {str(ie)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
  
