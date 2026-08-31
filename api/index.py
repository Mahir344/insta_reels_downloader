import re
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


def extract_shortcode(url: str):
    """Pull the shortcode out of a standard Instagram post/reel/tv URL."""
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url)
    return match.group(1) if match else None


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
    return jsonify({"status": "ok"})


# Vercel's Python runtime looks for a WSGI app named `app`
if __name__ == "__main__":
    app.run(debug=True)
  
