from flask import Flask, request, jsonify
from flask import jsonify, request
import os
import uuid
import requests
import json
import time
import logging
from moodque_engine import build_smart_playlist_enhanced
from moodque_utilities import create_new_playlist


app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    return "MoodQue Webhook is Running"

# --- Glide Playlist Creation Webhook ---
@app.route("/glide-social", methods=["POST"])
def handle_glide_webhook():
    try:
        event = request.json
        logger.info(f"📥 Received event: {json.dumps(event)}")

        favorite_artist = event.get("Favorite Artist", "")
        genres = event.get("Genres", "")
        mood_tags = event.get("Mood Tags", "")
        time = event.get("Time", "")
        search_keywords = event.get("Search Keywords", "")
        glide_user_id = event.get("Creator Email", "")
        event_name = event.get("Event Name", "")

        logger.info(f"🎯 Favorite artist: {favorite_artist}, Genres: {genres}, Moods: {mood_tags}, Time: {time}, Keywords: {search_keywords}")

        playlist_info = build_smart_playlist_enhanced(
            event=event_name,
            genre=genres,
            time=time,
            mood_tags=mood_tags,
            search_keywords=search_keywords,
            favorite_artist=favorite_artist,
            glide_user_id=glide_user_id
        )

        if not playlist_info:
            logger.warning("⚠️ Playlist creation failed, no data returned.")
            return jsonify({"error": "Playlist creation failed"}), 500

        updates = {
            "Playlist ID": playlist_info.get("playlist_id", ""),
            "Spotify URL": playlist_info.get("spotify_url", ""),
            "Spotify Code URL": playlist_info.get("spotify_code_url", ""),
            "Has Spotify Code": "Yes" if playlist_info.get("spotify_code_url") else "No",
            "Track Count": playlist_info.get("track_count", 0)
        }

        # Add raw JSON string for use in Glide workflows
        raw_webhook_json = json.dumps(updates)
        updates["Raw Webhook"] = raw_webhook_json

        response_data = { "updates": updates }

        logger.info(f"📡 Returning data to Glide: {json.dumps(response_data)}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"❌ Exception during playlist creation: {e}")
        return jsonify({"error": str(e)}), 500


    
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
            "mood_tags": "happy"
        }
    })

@app.route("/update_user_profile", methods=["POST"])
def update_user_profile():
    data = request.json
    return jsonify({"status": "updated", "data": data})


if __name__ == "__main__":
    app.run(debug=True)