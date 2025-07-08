import logging
from flask import Flask, request, jsonify
from moodque_engine import build_smart_playlist_enhanced  # Adjust path if needed
import requests
import os

# --- Flask App Setup ---
app = Flask(__name__)
logger = logging.getLogger("moodQueSocial_webhook")
logging.basicConfig(level=logging.INFO)

# --- Constants ---
GLIDE_RETURN_WEBHOOK_URL = os.getenv("GLIDE_RETURN_WEBHOOK_URL")  # Set in Railway or .env

# --- Helper Function: Send Result to Glide Webhook ---
def send_to_glide_return_webhook(row_id, playlist_info):
    webhook_url = os.getenv("GLIDE_RETURN_WEBHOOK_URL")
    if not webhook_url:
        logger.error("🚫 No Glide Return Webhook URL configured.")
        return

    payload = {
        "row_id": row_id,
        "has_code": "true",
        "playlist_id": playlist_info.get("playlist_id"),
        "spotify_url": playlist_info.get("spotify_url"),
        "track_count": str(playlist_info.get("track_count", "0")),
        "spotify_code_url": playlist_info.get("spotify_code_url"),
    }

    logger.info(f"📤 Sending to Glide Return Webhook: {webhook_url}")
    logger.info(f"📦 Return Payload: {payload}")

    try:
        response = requests.post(webhook_url, json=payload)
        logger.info(f"📬 Glide Response: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"🧨 Error sending webhook to Glide: {e}")


# --- Main Playlist Trigger Route ---
@app.route("/glide_social", methods=["POST"])
def glide_social():
    try:
        payload = request.get_json()

        # ✅ Glide sends data under a "body" key
        body = payload.get("body", {})

        row_id = body.get("row_id")
        event_name = body.get("event_name", "").strip()
        genre = body.get("genre", "").strip()
        mood_tags = body.get("mood_tags", "").strip()
        favorite_artist = body.get("favorite_artist", "").strip()
        search_keywords = body.get("search_keywords", "").strip()
        time = body.get("time", 30)
        playlist_type = body.get("playlist_type", "clean")

        logger.info(f"🎯 Incoming Payload: {body}")

        # ✅ Check for required fields
        if not all([row_id, genre, mood_tags, favorite_artist, event_name, playlist_type]):
            logger.warning(
                f"⚠️ Missing required fields: row_id={row_id}, genre={genre}, mood_tags={mood_tags}, favorite_artist={favorite_artist}, event_name={event_name}, playlist_type={playlist_type}"
            )
            return jsonify({"status": "missing values"}), 400

        # ✅ Build the playlist
        playlist_info = build_smart_playlist_enhanced(
            favorite_artist,
            event_name,
            genre,
            time,
            mood_tags,
            playlist_type,
            search_keywords
        )

        logger.info(f"✅ Playlist created: {playlist_info}")

        # ✅ Send the return webhook
        if playlist_info:
            playlist_info["row_id"] = row_id
            send_to_glide_return_webhook(playlist_info)
        else:
            logger.warning("⚠️ Playlist creation returned no data.")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"❌ Exception in glide_social: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500