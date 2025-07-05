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
@app.route('/glide-social', methods=['POST'])
def glide_social():
    try:
        raw_payload = request.get_json(force=True)
        logging.info(f"📥 Raw payload: {raw_payload}")

        # Extract inner body if it's nested
        payload = raw_payload.get("body", raw_payload)
        logging.info(f"📦 Processed payload: {payload}")

        # Extract fields with fallback defaults
        event_name = payload.get("event_name", "").strip()
        genre = payload.get("genre", "").strip()
        mood_tags = payload.get("mood_tags", "").strip()
        favorite_artist = payload.get("favorite_artist", "").strip()
        search_keywords = payload.get("search_keywords", "").strip()
        time = payload.get("time", 30)
        playlist_type = payload.get("playlist_type", "clean")

        # ✅ DEBUG PRINT to verify everything
        logging.info(f"🎯 Building playlist for event: '{event_name}'")
        logging.info(f"🎼 Genre Input: {genre}")
        logging.info(f"🎭 Mood Tag: {mood_tags}")
        logging.info(f"🔍 Search Keywords: {search_keywords}")
        logging.info(f"🎤 Favorite Artist(s): {favorite_artist}")
        logging.info(f"⏱️ Target Duration: {time} minutes")
        logging.info(f"🧼 Content Filter: {playlist_type}")
        
        playlist_info = build_smart_playlist_enhanced(
            event_name=event_name,
            genre=genre,
            time=time,
            mood_tags=mood_tags,
            search_keywords=search_keywords,
            playlist_type=playlist_type,
            favorite_artist=favorite_artist
        )

        if not playlist_info:
            logger.warning("⚠️ Playlist creation failed, no data returned.")
            return jsonify({"error": "Playlist creation failed"}), 500

        updates = {
            "Playlist ID": playlist_info.get("playlist_id", ""),
            "Spotify URL": playlist_info.get("spotify_url", ""),
            "Spotify Code URL": playlist_info.get("spotify_code_url", ""),
        }

        logger.info(f"✅ Playlist created: {updates}")
        return jsonify(updates), 200

    except Exception as e:
        logger.exception("🔥 Exception during playlist creation")
        return jsonify({"error": str(e)}), 500
    # --- Glide Playlist Creation Webhook End ---

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