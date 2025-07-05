from flask import Flask, request, jsonify, Blueprint
from flask import jsonify, request
import os
import uuid
import requests
import json
import time
import logging
from moodque_engine import build_smart_playlist_enhanced
from moodque_utilities import create_new_playlist

glide_social_bp = Blueprint('glide_social', __name__)

pp = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pp.route("/")
def index():
    return "MoodQue Webhook is Running"

# --- Glide Playlist Creation Webhook ---
@glide_social_bp.route('/glide_social', methods=['POST'])
def glide_social():
    try:
        data = request.get_json(force=True)
        print("🔄 Incoming from Glide:", data)

        # Parse incoming data
        row_id = data.get("row_id")
        favorite_artist = data.get("favorite_artist", "")
        genres = data.get("genres", [])
        time_of_day = data.get("time_of_day", "")
        mood_tags = data.get("mood_tags", [])
        event_name = data.get("event_name", "MoodCue Mix")

        # Build the playlist
        result = build_smart_playlist_enhanced(
            favorite_artist=favorite_artist,
            genres=genres,
            time_of_day=time_of_day,
            mood_tags=mood_tags,
            event_name=event_name
        )

        # Prepare response payload to send back to Glide
        payload = {
            "row_id": row_id,
            "playlist_id": result.get("playlist_id", ""),
            "spotify_url": result.get("spotify_url", ""),
            "spotify_code_url": result.get("spotify_code_url", ""),
            "track_count": result.get("track_count", 0),
            "has_spotify_code": bool(result.get("spotify_code_url"))
        }

        print("📤 Sending to Glide Webhook:", payload)

        # POST back to Glide's workflow webhook endpoint
        glide_webhook_url = "https://go.glideapps.com/api/container/plugin/webhook-trigger/WE36jV1c5vSHZWc5A4oC/a170355b-005a-4c5a-ab2a-c65bdf04ad7a"
        response = requests.post(glide_webhook_url, json=payload)

        print(f"✅ Glide Webhook Status: {response.status_code}")
        print(f"📦 Glide Webhook Response: {response.text}")

        return jsonify({"status": "success", "sent_to_glide": response.status_code == 200}), 200

    except Exception as e:
        print("❌ Error in glide_social:", str(e))
        return jsonify({"error": str(e)}), 500


# --- Glide Playlist Creation Webhook End ---

    # --- Social & User Profile Endpoints ---

@pp.route("/like_playlist", methods=["POST"])
def like_playlist():
    data = request.json
    playlist_id = data.get("playlist_id")
    user_id = data.get("user_id")
    return jsonify({"status": "liked", "playlist_id": playlist_id, "user_id": user_id})

@pp.route("/view_playlist", methods=["POST"])
def view_playlist():
    data = request.json
    playlist_id = data.get("playlist_id")
    return jsonify({"status": "viewed", "playlist_id": playlist_id})

@pp.route("/get_user_profile", methods=["POST"])
def get_user_profile():
    data = request.json
    user_email = data.get("email")
    return jsonify({
        "email": user_email,
        "username": "TestUser",
        "preferences": {
            "favorite_genres": ["pop", "hip-hop"],
            "mood_tags": "happy"
        }
    })

@pp.route("/update_user_profile", methods=["POST"])
def update_user_profile():
    data = request.json
    return jsonify({"status": "updated", "data": data})


if __name__ == "__main__":
    pp.run(debug=True)