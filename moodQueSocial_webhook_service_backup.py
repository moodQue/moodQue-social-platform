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
        # Parse JSON from request
        payload = request.get_json(force=True)
        logger.info(f"📥 Incoming Payload: {payload}")

        # Extract required values
        row_id = payload.get("row_id")
        genre = payload.get("genre")
        mood_tags = payload.get("mood_tags")
        favorite_artist = payload.get("favorite_artist")
        time_range = payload.get("time_range")

        if not all([row_id, genre, mood_tags, favorite_artist]):
            logger.warning("⚠️ Missing one or more required parameters.")
            return jsonify({"error": "Missing required data"}), 400

        # Call playlist builder
        playlist_info = build_smart_playlist_enhanced(
            favorite_artist=favorite_artist,
            genre=genre,
            time=time_range,
            mood_tags=mood_tags,
            search_keywords=None  # Add if needed
        )

        # Safely handle unexpected result types
        if not isinstance(playlist_info, dict):
            logger.warning(f"❌ Playlist creation failed. Raw Response: {playlist_info}")
            return jsonify({"error": "Playlist creation failed"}), 500

        logger.info(f"🎁 Playlist Info Keys: {list(playlist_info.keys())}")
        logger.info(f"✅ Playlist Created: {playlist_info.get('spotify_url')}")

        # Send data back to Glide via webhook
        try:
            send_to_glide_return_webhook(row_id, playlist_info)
        except Exception as e:
            logger.error(f"🚨 Failed to send return webhook to Glide: {e}")

        # Send immediate 200 response back to Glide to complete workflow
        return jsonify({"status": "Playlist built", "playlist_id": playlist_info.get("playlist_id")}), 200

    except Exception as e:
        logger.exception("🔥 Unexpected server error in glide_social()")
        return jsonify({"error": str(e)}), 500

