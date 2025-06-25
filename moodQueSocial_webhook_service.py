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
@app.route("/glide-webhook", methods=["POST"])
def handle_glide_webhook():
    """
    This webhook is called BY Glide when a new playlist needs to be created.
    It returns playlist metadata along with a Raw Webhook string for Glide to parse later.
    """
    data = request.json
    row_id = data.get("row_id")
    
    logger.info(f"🎵 Processing playlist request for row_id: {row_id}")
    logger.info(f"Request data: {data}")

    try:
        playlist_url = build_smart_playlist_enhanced(
            event_name=data.get('event_name', '').strip(),
            genre=data.get('genre', ''),
            mood_tags=data.get('mood_tags', ''),
            time=data.get('time', 30),
            playlist_type=data.get('playlist_type', 'clean'),
            search_keywords=data.get('search_keywords', ''),
            favorite_artist=data.get('favorite_artist', '')
        )

        if not playlist_url:
            logger.error("❌ No playlist created - fallback failed")
            return jsonify({
                "updates": {
                    "Playlist ID": "",
                    "Spotify URL": "",
                    "Spotify Code URL": "",
                    "Has Spotify Code": "No",
                    "Track Count": 0,
                    "Raw Webhook": "{}"
                }
            }), 200

        playlist_id = playlist_url.split("/")[-1] if playlist_url else ""
        spotify_code_url = f"https://scannables.scdn.co/uri/plain/spotify:playlist:{playlist_id}" if playlist_id else ""

        updates = {
            "Playlist ID": playlist_id,
            "Spotify URL": playlist_url,
            "Spotify Code URL": spotify_code_url,
            "Has Spotify Code": "Yes" if spotify_code_url else "No",
            "Track Count": int(data.get('time', 30))
        }

        response_data = { "updates": updates }

        logger.info(f"📡 Returning data to Glide: {response_data}")
        logger.info(f"✅ Playlist created successfully: {playlist_url}")

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"❌ Exception during playlist creation: {str(e)}")
        return jsonify({
            "updates": {
                "Playlist ID": "",
                "Spotify URL": "",
                "Spotify Code URL": "",
                "Has Spotify Code": "No",
                "Track Count": 0,
                "Raw Webhook": "{}"
            }
        }), 200


    
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