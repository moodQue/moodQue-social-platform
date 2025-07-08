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
    """Send playlist results back to Glide return webhook"""
    webhook_url = os.getenv("GLIDE_RETURN_WEBHOOK_URL")
    if not webhook_url:
        logger.error("🚫 No Glide Return Webhook URL configured.")
        return

    # Prepare payload for Glide return webhook
    if playlist_info and isinstance(playlist_info, str):
        # If playlist_info is just a URL string
        payload = {
            "row_id": row_id,
            "has_code": "true",
            "playlist_id": playlist_info.split('/')[-1] if '/' in playlist_info else "",
            "spotify_url": playlist_info,
            "track_count": "0",  # You might want to get actual track count
            "spotify_code_url": playlist_info,
            "status": "completed"
        }
    elif playlist_info and isinstance(playlist_info, dict):
        # If playlist_info is a dictionary with details
        payload = {
            "row_id": row_id,
            "has_code": "true",
            "playlist_id": playlist_info.get("playlist_id", ""),
            "spotify_url": playlist_info.get("spotify_url", ""),
            "track_count": str(playlist_info.get("track_count", "0")),
            "spotify_code_url": playlist_info.get("spotify_code_url", ""),
            "status": "completed"
        }
    else:
        # If playlist creation failed
        payload = {
            "row_id": row_id,
            "has_code": "false",
            "playlist_id": "",
            "spotify_url": "",
            "track_count": "0",
            "spotify_code_url": "",
            "status": "failed"
        }

    logger.info(f"📤 Sending to Glide Return Webhook: {webhook_url}")
    logger.info(f"📦 Return Payload: {payload}")

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        logger.info(f"📬 Glide Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"🧨 Error sending webhook to Glide: {e}")
        return False


# --- Main Playlist Trigger Route ---
@app.route("/glide_social", methods=["POST"])
def glide_social():
    """Handle incoming playlist build requests from Glide"""
    try:
        payload = request.get_json()
        logger.info(f"📨 Raw Payload Received: {payload}")

        # ✅ Glide sends data under a "body" key
        body = payload.get("body", {})

        # Extract required fields
        row_id = body.get("row_id")
        event_name = body.get("event_name", "").strip()
        genre = body.get("genre", "").strip()
        mood_tags = body.get("mood_tags", "").strip()
        favorite_artist = body.get("favorite_artist", "").strip()
        search_keywords = body.get("search_keywords", "").strip()
        time = body.get("time", 30)
        playlist_type = body.get("playlist_type", "clean")

        logger.info(f"🎯 Processed Fields:")
        logger.info(f"   - Row ID: {row_id}")
        logger.info(f"   - Event Name: {event_name}")
        logger.info(f"   - Genre: {genre}")
        logger.info(f"   - Mood Tags: {mood_tags}")
        logger.info(f"   - Favorite Artist: {favorite_artist}")
        logger.info(f"   - Search Keywords: {search_keywords}")
        logger.info(f"   - Time: {time}")
        logger.info(f"   - Playlist Type: {playlist_type}")

        # ✅ Check for required fields
        if not row_id:
            logger.error("❌ Missing row_id - this is required for return webhook")
            return jsonify({"status": "error", "message": "Missing row_id"}), 400

        if not all([event_name, genre, mood_tags, favorite_artist, playlist_type]):
            logger.warning(f"⚠️ Missing required fields:")
            logger.warning(f"   - Event Name: {'✓' if event_name else '✗'}")
            logger.warning(f"   - Genre: {'✓' if genre else '✗'}")
            logger.warning(f"   - Mood Tags: {'✓' if mood_tags else '✗'}")
            logger.warning(f"   - Favorite Artist: {'✓' if favorite_artist else '✗'}")
            logger.warning(f"   - Playlist Type: {'✓' if playlist_type else '✗'}")
            
            # Send failed status back to Glide
            send_to_glide_return_webhook(row_id, None)
            return jsonify({"status": "missing values"}), 400

        # ✅ Build the playlist with correct parameter order
        logger.info("🎵 Starting playlist build...")
        
        try:
            playlist_result = build_smart_playlist_enhanced(
                event_name=event_name,           # playlist name
                genre=genre,                     # genre
                time=time,                       # duration in minutes
                mood_tags=mood_tags,             # mood
                search_keywords=search_keywords, # keywords
                playlist_type=playlist_type,     # clean/explicit
                favorite_artist=favorite_artist, # artist
                request_id=row_id               # for logging
            )
            
            logger.info(f"🎵 Playlist build result: {playlist_result}")
            
            # ✅ Send the return webhook
            if playlist_result:
                success = send_to_glide_return_webhook(row_id, playlist_result)
                if success:
                    logger.info("✅ Successfully sent return webhook to Glide")
                else:
                    logger.error("❌ Failed to send return webhook to Glide")
            else:
                logger.warning("⚠️ Playlist creation returned no data.")
                send_to_glide_return_webhook(row_id, None)

            return jsonify({"status": "success", "playlist_url": playlist_result}), 200

        except Exception as playlist_error:
            logger.error(f"❌ Playlist build failed: {playlist_error}", exc_info=True)
            send_to_glide_return_webhook(row_id, None)
            return jsonify({"status": "error", "message": f"Playlist build failed: {str(playlist_error)}"}), 500

    except Exception as e:
        logger.error(f"❌ Exception in glide_social: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


# --- Health Check Route ---
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "moodQueSocial_webhook"}), 200


# --- Test Route ---
@app.route("/test", methods=["GET", "POST"])
def test_endpoint():
    """Test endpoint to verify webhook is working"""
    if request.method == "POST":
        data = request.get_json()
        logger.info(f"🧪 Test POST data: {data}")
        return jsonify({"status": "test_success", "received": data}), 200
    else:
        return jsonify({"status": "test_success", "method": "GET"}), 200


if __name__ == "__main__":
    # For local testing
    app.run(debug=True, host="0.0.0.0", port=5000)