from flask import Flask, request, jsonify
import os
import uuid
import requests
import json
import time
import logging
from moodque_engine import build_smart_playlist_enhanced

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    return "MoodQue Webhook is Running"

class GlideWebhookClient:
    def __init__(self):
        # Updated with your actual Glide webhook URL
        self.webhook_url = "https://go.glideapps.com/api/container/plugin/webhook-trigger/WE36jV1c5vSHZWc5A4oC/3e24c78c-fd03-4a86-b2db-05e0f36398b6"
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Railway-Spotify-Service/1.0"
        }
    
    # ... rest of your class remains the same

# Instantiate the webhook client so it can be used in the endpoints
webhook_client = GlideWebhookClient()

class GlideWebhookClient:
    def __init__(self):
        # Updated with your actual Glide webhook URL
        self.webhook_url = "https://go.glideapps.com/api/container/plugin/webhook-trigger/WE36jV1c5vSHZWc5A4oC/3e24c78c-fd03-4a86-b2db-05e0f36398b6"
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Railway-Spotify-Service/1.0"
        }

    def send_playlist_update(self, row_id, playlist_data, max_retries=3):
        """Send playlist data back to Glide webhook"""
        payload = {
            "row_id": row_id,
            "playlist_id": playlist_data.get("playlist_id", ""),
            "spotify_url": playlist_data.get("spotify_url", ""),
            "spotify_code_url": playlist_data.get("spotify_code_url", ""),
            "has_spotify_code": "Yes" if playlist_data.get("spotify_code_url") else "No",
            "track_count": playlist_data.get("track_count", 0)
        }

        logger.info(f"🚀 Sending webhook for row_id: {row_id}")

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 200:
                    logger.info("✅ Webhook sent successfully!")
                    return True
                else:
                    logger.error(f"❌ Webhook failed: {response.status_code}")

            except Exception as e:
                logger.error(f"❌ Webhook error on attempt {attempt + 1}: {str(e)}")

            if attempt < max_retries - 1:
                time.sleep(1)

        return False

# Instantiate the webhook client so it can be used in the endpoints
webhook_client = GlideWebhookClient()
    
# --- Glide Playlist Creation Webhook ---
@app.route("/glide-webhook", methods=["POST"])
def handle_glide_webhook():
    data = request.json
    row_id = data.get("row_id")
    
    logger.info(f"🎵 Processing playlist request for row_id: {row_id}")
    logger.info(f"Request data: {data}")
    
    try:
        # Your existing playlist creation logic
        playlist_url = build_smart_playlist_enhanced(
            event_name=data.get('event_name', '').strip(),
            genre=data.get('genre', ''),
            mood=data.get('mood', ''),
            time=data.get('time', 30),
            playlist_type=data.get('playlist_type', 'clean'),
            search_keywords=data.get('search_keywords', ''),
            favorite_artist=data.get('favorite_artist', '')
        )
        
        if not playlist_url:
            # Send failure notification to Glide
            failure_data = {
                "playlist_id": "",
                "spotify_url": "",
                "spotify_code_url": "",
                "track_count": 0
            }
            webhook_client.send_playlist_update(row_id, failure_data) # type: ignore
            
            return jsonify({
                "row_id": row_id,
                "error": "No playlist created - fallback failed.",
                "spotify_url": None
            }), 400

        # Extract playlist ID from URL
        playlist_id = playlist_url.split("/")[-1] if playlist_url else ""
        
        # Generate Spotify Code URL (if you have this function)
        # spotify_code_url = generate_spotify_code_url(playlist_id)  # Uncomment if you have this
        spotify_code_url = f"https://scannables.scdn.co/uri/plain/spotify:playlist:{playlist_id}" if playlist_id else ""
        
        # Prepare playlist data for Glide
        playlist_data = {
            "playlist_id": playlist_id,
            "spotify_url": playlist_url,
            "spotify_code_url": spotify_code_url,
            "track_count": data.get('time', 30)  # Approximate based on duration
        }
        
        # Send success data back to Glide
        webhook_success = webhook_client.send_playlist_update(row_id, playlist_data) # type: ignore
        
        logger.info(f"✅ Playlist created: {playlist_url}")
        logger.info(f"📡 Glide webhook sent: {'✅' if webhook_success else '❌'}")
        
        return jsonify({
            "row_id": row_id,
            "playlist_id": playlist_id,
            "spotify_url": playlist_url,
            "spotify_code_url": spotify_code_url,
            "track_count": playlist_data["track_count"],
            "message": "✅ Playlist created!",
            "webhook_sent": webhook_success
        })

    except Exception as e:
        logger.error(f"❌ Exception during playlist creation: {str(e)}")
        
        # Send error notification to Glide
        error_data = {
            "playlist_id": "",
            "spotify_url": "",
            "spotify_code_url": "",
            "track_count": 0
        }
        webhook_client.send_playlist_update(row_id, error_data)
        
        return jsonify({
            "row_id": row_id,
            "error": f"Exception during playlist creation: {str(e)}"
        }), 500


# --- Social & User Profile Endpoints ---

@app.route("/like_playlist", methods=["POST"])
def like_playlist():
    data = request.json
    playlist_id = data.get("playlist_id")
    user_id = data.get("user_id")
    return jsonify({"status": "liked", "playlist_id": playlist_id, "user_id": user_id})

@app.route("/view_playlist", methods=["POST"])
def view_playlist():
    data = request.json
    playlist_id = data.get("playlist_id")
    return jsonify({"status": "viewed", "playlist_id": playlist_id})

@app.route("/get_user_profile", methods=["POST"])
def get_user_profile():
    data = request.json
    user_email = data.get("email")
    return jsonify({
        "email": user_email,
        "username": "TestUser",
        "preferences": {
            "favorite_genres": ["pop", "hip-hop"],
            "mood": "happy"
        }
    })

@app.route("/update_user_profile", methods=["POST"])
def update_user_profile():
    data = request.json
    return jsonify({"status": "updated", "data": data})


if __name__ == "__main__":
    app.run(debug=True)
