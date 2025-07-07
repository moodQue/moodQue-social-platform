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
    payload = {
        "row_id": row_id,
        "playlist_id": playlist_info.get("playlist_id", ""),
        "spotify_url": playlist_info.get("spotify_url", ""),
        "spotify_code_url": playlist_info.get("spotify_code_url", ""),
        "has_code": playlist_info.get("has_code", False),
        "track_count": playlist_info.get("track_count", 0),
    }

    try:
        response = requests.post(GLIDE_RETURN_WEBHOOK_URL, json=payload)
        logger.info(f"📤 Sent to Glide Return Webhook → Status: {response.status_code}")
        logger.debug(f"🔁 Glide Response: {response.text}")
        return response.status_code
    except Exception as e:
        logger.exception("❌ Failed to post to Glide Return Webhook")
        return None

# --- Main Playlist Trigger Route ---
@app.route('/glide-social', methods=['POST'])
def glide_social():
    try:
        raw_payload = request.get_json(force=True)
        logger.info(f"📥 Raw Payload: {raw_payload}")

        payload = raw_payload.get("body", raw_payload)
        logger.info(f"📦 Processed Payload: {payload}")

        # Extract fields
        row_id = payload.get("🔒 row_id")  # Your custom Glide column
        event_name = payload.get("event_name", "").strip()
        genre = payload.get("genre", "").strip()
        mood_tags = payload.get("mood_tags", "").strip()
        favorite_artist = payload.get("favorite_artist", "").strip()
        search_keywords = payload.get("search_keywords", "").strip()
        time = payload.get("time", 30)
        playlist_type = payload.get("playlist_type", "clean")
        
        # Build Playlist
        playlist_info = build_smart_playlist_enhanced(
            event_name=event_name,
            genre=genre,
            time=time,
            mood_tags=mood_tags,
            search_keywords=search_keywords,
            playlist_type=playlist_type,
            favorite_artist=favorite_artist
        )
        
        logger.info(f"🎁 Playlist Info Keys: {list(playlist_info.keys())}")
        logger.info(f"🎯 Event: {event_name} | 🎼 Genre: {genre} | 🎭 Mood: {mood_tags} | ⏱️ Time: {time}")
        
        
        if not isinstance(playlist_info, dict) or "spotify_url" not in playlist_info:
            logger.warning(f"⚠️ Playlist creation failed or invalid response: {playlist_info}")
            return jsonify({"error": "Playlist creation failed"}), 500

        logger.info(f"📡 Sending return webhook for row_id={row_id}")
        logger.info(f"📦 Playlist Info Payload: {playlist_info}")

        # Send result to Glide return webhook
        status = send_to_glide_return_webhook(row_id, playlist_info)

        return jsonify({"message": "Playlist created", "status": status}), 200

    except Exception as e:
        logger.exception("🔥 Exception in glide_social")
        return jsonify({"error": str(e)}), 500

# --- Flask App Entry Point ---
if __name__ == '__main__':
    app.run(debug=True)
