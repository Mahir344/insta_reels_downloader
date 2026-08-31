import os
import re
import base64
import tempfile

import instaloader
from flask import Flask, request, jsonify


app = Flask(__name__)


# =========================================================
# Instaloader configuration
# =========================================================

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    quiet=True,
)


SESSION_LOADED = False
SESSION_LOAD_ERROR = None


# =========================================================
# Load Instagram session from Vercel Environment Variables
# =========================================================

def load_session_from_env():
    global SESSION_LOADED
    global SESSION_LOAD_ERROR

    username = os.environ.get("IG_USERNAME")
    session_b64 = os.environ.get("IG_SESSION_B64")

    if not username:
        SESSION_LOAD_ERROR = "IG_USERNAME environment variable is missing."
        return

    if not session_b64:
        SESSION_LOAD_ERROR = "IG_SESSION_B64 environment variable is missing."
        return

    try:
        # Remove accidental spaces/newlines
        session_b64 = "".join(session_b64.split())

        session_bytes = base64.b64decode(
            session_b64,
            validate=True
        )

        session_path = os.path.join(
            tempfile.gettempdir(),
            f"session-{username}"
        )

        with open(session_path, "wb") as f:
            f.write(session_bytes)

        L.load_session_from_file(
            username,
            filename=session_path
        )

        SESSION_LOADED = True
        SESSION_LOAD_ERROR = None

    except Exception as e:
        SESSION_LOADED = False
        SESSION_LOAD_ERROR = (
            f"Failed to load Instagram session: {type(e).__name__}: {str(e)}"
        )


# Load session when the server starts
load_session_from_env()


# =========================================================
# Helpers
# =========================================================

def extract_shortcode(url):
    """
    Extract Instagram shortcode from:
    
    https://www.instagram.com/p/ABC123/
    https://www.instagram.com/reel/ABC123/
    https://www.instagram.com/tv/ABC123/
    """

    if not url:
        return None

    url = url.strip()

    match = re.search(
        r"(?:https?://)?(?:www\.)?instagram\.com/"
        r"(?:p|reel|tv)/([^/?#]+)",
        url,
        re.IGNORECASE
    )

    if not match:
        return None

    return match.group(1)


def clean_url(url):
    if not url:
        return None

    return url.strip()


# =========================================================
# Home
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "status": "online",
        "service": "Instagram Downloader API",
        "version": "2.0",
        "usage": "/api?url=https://www.instagram.com/reel/SHORTCODE/",
        "health": "/api/health"
    })


# =========================================================
# Health Check
# =========================================================

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "username_set": bool(
            os.environ.get("IG_USERNAME")
        ),
        "session_b64_set": bool(
            os.environ.get("IG_SESSION_B64")
        ),
        "session_loaded": SESSION_LOADED,
        "session_error": SESSION_LOAD_ERROR
    })


# =========================================================
# Instagram Downloader
# =========================================================

@app.route("/api", methods=["GET"])
@app.route("/api/index", methods=["GET"])
def download():

    url = request.args.get("url")

    if not url:
        return jsonify({
            "success": False,
            "error": "Missing 'url' query parameter.",
            "example": "/api?url=https://www.instagram.com/reel/SHORTCODE/"
        }), 400

    url = clean_url(url)

    shortcode = extract_shortcode(url)

    if not shortcode:
        return jsonify({
            "success": False,
            "error": "Invalid Instagram URL.",
            "supported": [
                "instagram.com/p/SHORTCODE/",
                "instagram.com/reel/SHORTCODE/",
                "instagram.com/tv/SHORTCODE/"
            ]
        }), 400

    try:

        post = instaloader.Post.from_shortcode(
            L.context,
            shortcode
        )

        media = []

        # =====================================================
        # Carousel / Sidecar
        # =====================================================

        if post.typename == "GraphSidecar":

            for node in post.get_sidecar_nodes():

                if node.is_video:

                    media.append({
                        "type": "video",
                        "url": node.video_url
                    })

                else:

                    media.append({
                        "type": "image",
                        "url": node.display_url
                    })

        # =====================================================
        # Single image / video
        # =====================================================

        else:

            if post.is_video:

                media.append({
                    "type": "video",
                    "url": post.video_url
                })

            else:

                media.append({
                    "type": "image",
                    "url": post.url
                })


        return jsonify({
            "success": True,
            "shortcode": shortcode,
            "type": post.typename,
            "caption": post.caption,
            "owner": post.owner_username,
            "likes": post.likes,
            "comments": post.comments,
            "media_count": len(media),
            "media": media
        })


    except instaloader.exceptions.QueryReturnedBadRequestException as e:

        return jsonify({
            "success": False,
            "error": "Instagram returned HTTP 400.",
            "message": str(e),
            "shortcode": shortcode
        }), 502


    except instaloader.exceptions.ConnectionException as e:

        return jsonify({
            "success": False,
            "error": "Instagram connection failed.",
            "message": str(e)
        }), 502


    except instaloader.exceptions.InstaloaderException as e:

        return jsonify({
            "success": False,
            "error": "Instagram fetch failed.",
            "message": str(e),
            "shortcode": shortcode
        }), 502


    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Unexpected server error.",
            "message": str(e)
        }), 500


# =========================================================
# Vercel
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
  )
