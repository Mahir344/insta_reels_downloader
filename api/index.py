import os
import re
import base64
import tempfile
import instaloader
from flask import Flask, request, jsonify

app = Flask(__name__)

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


def load_session_from_env():
    """
    Loads a pre-generated Instaloader session (base64-encoded) from env vars,
    so this serverless function can act as a logged-in user without ever
    doing an interactive login itself.

    Required env vars (set these in Vercel Project Settings -> Environment Variables):
      IG_USERNAME       - the Instagram username the session belongs to
      IG_SESSION_B64     - base64 contents of the session file generated locally
    """
    global SESSION_LOADED, SESSION_LOAD_ERROR

    username = os.environ.get("IG_USERNAME")
    session_b64 = os.environ.get("IG_SESSION_B64")

    if not username or not session_b64:
        SESSION_LOAD_ERROR = "No IG_USERNAME / IG_SESSION_B64 env vars set; running anonymously."
        return

    try:
        session_bytes = base64.b64decode(session_b64)
        # /tmp is the only writable directory in Vercel's serverless runtime
        session_path = os.path.join(tempfile.gettempdir(), f"session-{username}")
        with open(session_path, "wb") as f:
            f.write(session_bytes)

        L.load_session_from_file(username, filename=session_path)
        SESSION_LOADED = True
    except Exception as e:
        SESSION_LOAD_ERROR = f"Failed to load session: {str(e)}"


load_session_from_env()


def extract_shortcode(url: str):
    """Pull the shortcode out of a standard Instagram post/reel/tv URL."""
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url)
    return match.group(1) if match else None


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Instagram downloader API is running.",
        "usage": "/api?url=https://www.instagram.com/p/SHORTCODE/",
        "health_check": "/api/health",
    })


@app.route("/api/index", methods=["GET"])
@app.route("/api", methods=["GET"])
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing 'url' query parameter"}), 400

    shortcode = extract_shortcode(url)
    if not shortcode:
        return jsonify({"error": "Could not parse a valid Instagram post/reel URL"}), 400

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        media = []
        if post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                media.append({
                    "type": "video" if node.is_video else "image",
                    "url": node.video_url if node.is_video else node.display_url,
                })
        else:
            media.append({
                "type": "video" if post.is_video else "image",
                "url": post.video_url if post.is_video else post.url,
            })

        return jsonify({
            "success": True,
            "shortcode": shortcode,
            "caption": post.caption,
            "owner": post.owner_username,
            "likes": post.likes,
            "media": media,
        })

    except instaloader.exceptions.InstaloaderException as e:
        return jsonify({"error": f"Instagram fetch failed: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "session_loaded": SESSION_LOADED,
        "session_note": SESSION_LOAD_ERROR if not SESSION_LOADED else "Logged-in session active",
    })


# Vercel's Python runtime looks for a WSGI app named `app`
if __name__ == "__main__":
    app.run(debug=True)
  
