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
        # Replace with your actual webhook URL from Glide
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
    
# --- Glide Playlist Creation Webhook ---
@app.route("/glide-webhook", methods=["POST"])
def handle_glide_webhook():
    data = request.json
    row_id = data.get("row_id")

    try:
        playlist_url = build_smart_playlist_enhanced(
            event=data.get("event_name"),
            genre=data.get("genre"),
            time=data.get("duration"),
            mood_tags=data.get("mood"),
            search_keywords=data.get("search_keywords"),
            artist_names=data.get("favorite_artist"),
            playlist_type=data.get("playlist_type", "clean")
        )

        if not playlist_url:
            return jsonify({
                "row_id": row_id,
                "error": "No playlist created — fallback failed.",
                "spotify_url": None
            }), 400

        return jsonify({
        "row_id": f"{data.get('user_email', '').strip()}_{data.get('event_name', '').strip().replace(' ', '_')}",
        "playlist_id": playlist_url.split("/")[-1] if playlist_url else "",
        "spotify_url": playlist_url,
        "message": "✅ Playlist created!"
   })



    except Exception as e:
        print(f"❌ Exception during playlist creation: {str(e)}")
        return jsonify({
            "row_id": row_id,
            "error": f"Exception occurred: {str(e)}"
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
