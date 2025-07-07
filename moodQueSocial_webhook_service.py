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
    # Parse JSON from request
    payload = request.get_json()
    body = payload.get("body", {})  # get the inner dict safely

    row_id = body.get("row_id")
    event_name = body.get("event_name", "").strip()
    genre = body.get("genre", "").strip()
    mood_tags = body.get("mood_tags", "").strip()
    favorite_artist = body.get("favorite_artist", "").strip()
    search_keywords = body.get("search_keywords", "").strip()
    time = body.get("time", 30)
    playlist_type = body.get("playlist_type", "clean")

    try:
        # Extract required values
        # Use values from body, not payload
        # event_name is not extracted above, so remove it from the check or extract it if needed
        # If event_name is required, uncomment the next line:
        # event_name = body.get("event_name")
        # and add event_name to the all() check below

        if not all([row_id, genre, mood_tags, favorite_artist]):
            logger.warning(f"⚠️ Missing values: row_id={row_id}, genre={genre}, mood_tags={mood_tags}, favorite_artist={favorite_artist}")
            return jsonify({"error": "Missing required fields"}), 400

        # Call playlist builder
        playlist_info = build_smart_playlist_enhanced(
            favorite_artist=favorite_artist,
            genre=genre,
            time=time,
            mood_tags=mood_tags,
            search_keywords=search_keywords  # Add if needed
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

