from flask import Flask, request, jsonify
import os
import uuid
import requests
from moodque_engine import build_playlist  # NEW

app = Flask(__name__)

@app.route("/")
def index():
    return "MoodQue Webhook is Running"

# --- Glide Playlist Creation Webhook ---
@app.route("/glide-webhook", methods=["POST"])
def handle_glide_webhook():
    data = request.json

    row_id = data.get("row_id")
    try:
        result = build_playlist(data)

        if not result or "url" not in result:
            return jsonify({
                "row_id": row_id,
                "error": result.get("error", "No playlist created."),
                "spotify_url": None
            }), 400

        return jsonify({
            "row_id": row_id,
            "spotify_url": result["url"],
            "track_count": result.get("track_count", 0),
            "message": result.get("message", "Playlist created.")
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
