import re
import requests

from flask import Flask, request, jsonify


app = Flask(__name__)


# ============================================================
# Configuration
# ============================================================

APP_VERSION = "3.0"

INSTAGRAM_OEMBED_URL = (
    "https://graph.facebook.com/v25.0/instagram_oembed"
)

TIMEOUT = 15


# ============================================================
# HTTP session
# ============================================================

http = requests.Session()

http.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
})


# ============================================================
# Instagram URL parser
# ============================================================

def parse_instagram_url(url):
    """
    Supports:

    https://www.instagram.com/p/SHORTCODE/
    https://www.instagram.com/reel/SHORTCODE/
    https://www.instagram.com/tv/SHORTCODE/
    """

    if not url:
        return None

    url = url.strip()

    pattern = re.compile(
        r"^https?://"
        r"(?:www\.)?"
        r"instagram\.com/"
        r"(p|reel|tv)/"
        r"([A-Za-z0-9_-]+)"
        r"(?:/)?(?:\?.*)?$",
        re.IGNORECASE
    )

    match = pattern.match(url)

    if not match:
        return None

    media_type = match.group(1).lower()
    shortcode = match.group(2)

    return {
        "type": media_type,
        "shortcode": shortcode,
        "url": f"https://www.instagram.com/{media_type}/{shortcode}/"
    }


# ============================================================
# Health
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "status": "ok",
        "service": "Instagram Public Media API",
        "version": APP_VERSION,
        "instaloader": False,
        "graphql": False,
        "oembed": True
    })


# ============================================================
# Home
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "success": True,
        "status": "online",
        "service": "Instagram Public Media API",
        "version": APP_VERSION,

        "usage": (
            "/api?url="
            "https://www.instagram.com/reel/SHORTCODE/"
        ),

        "health": "/api/health",

        "supported": [
            "Instagram posts",
            "Instagram reels",
            "Instagram TV"
        ],

        "note": (
            "Public Instagram content only. "
            "Private/restricted content is not supported."
        )
    })


# ============================================================
# Instagram oEmbed
# ============================================================

def fetch_oembed(instagram_url):

    params = {
        "url": instagram_url,
        "omitscript": "true"
    }

    response = http.get(
        INSTAGRAM_OEMBED_URL,
        params=params,
        timeout=TIMEOUT
    )

    content_type = response.headers.get(
        "content-type",
        ""
    ).lower()

    if response.status_code != 200:

        try:
            error_data = response.json()
        except Exception:
            error_data = {
                "message": response.text[:500]
            }

        return None, {
            "status_code": response.status_code,
            "details": error_data
        }

    if "json" not in content_type:

        return None, {
            "status_code": response.status_code,
            "details": {
                "message": "Instagram returned a non-JSON response."
            }
        }

    return response.json(), None


# ============================================================
# Main API
# ============================================================

@app.route("/api", methods=["GET"])
@app.route("/api/index", methods=["GET"])
def api():

    url = request.args.get("url")

    # --------------------------------------------------------
    # Missing URL
    # --------------------------------------------------------

    if not url:

        return jsonify({
            "success": False,
            "error": "Missing 'url' query parameter.",
            "example": (
                "/api?url="
                "https://www.instagram.com/reel/SHORTCODE/"
            )
        }), 400


    # --------------------------------------------------------
    # Parse Instagram URL
    # --------------------------------------------------------

    parsed = parse_instagram_url(url)

    if not parsed:

        return jsonify({
            "success": False,
            "error": "Invalid Instagram URL.",

            "supported": [
                "https://www.instagram.com/p/SHORTCODE/",
                "https://www.instagram.com/reel/SHORTCODE/",
                "https://www.instagram.com/tv/SHORTCODE/"
            ]
        }), 400


    instagram_url = parsed["url"]


    # --------------------------------------------------------
    # Fetch public Instagram oEmbed data
    # --------------------------------------------------------

    try:

        data, error = fetch_oembed(
            instagram_url
        )

    except requests.Timeout:

        return jsonify({
            "success": False,
            "error": "Instagram request timed out."
        }), 504

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "error": "Instagram connection failed.",
            "message": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Unexpected request error.",
            "message": str(e)
        }), 500


    # --------------------------------------------------------
    # Instagram rejected request
    # --------------------------------------------------------

    if error:

        return jsonify({
            "success": False,
            "error": "Instagram oEmbed request failed.",
            "status_code": error["status_code"],
            "details": error["details"],

            "shortcode": parsed["shortcode"],
            "instagram_url": instagram_url
        }), 502


    # --------------------------------------------------------
    # Return clean response
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "type": parsed["type"],

        "shortcode": parsed["shortcode"],

        "instagram_url": instagram_url,

        "author": {
            "name": data.get("author_name"),
            "url": data.get("author_url")
        },

        "title": data.get("title"),

        "thumbnail": {
            "url": data.get("thumbnail_url"),
            "width": data.get("thumbnail_width"),
            "height": data.get("thumbnail_height")
        },

        "embed": {
            "type": data.get("type"),
            "width": data.get("width"),
            "html": data.get("html")
        },

        "provider": {
            "name": data.get("provider_name"),
            "url": data.get("provider_url")
        }

    })


# ============================================================
# Error handlers
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "error": "Endpoint not found."
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({
        "success": False,
        "error": "Method not allowed."
    }), 405


@app.errorhandler(500)
def internal_error(error):

    return jsonify({
        "success": False,
        "error": "Internal server error."
    }), 500


# ============================================================
# Local development
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
  )
