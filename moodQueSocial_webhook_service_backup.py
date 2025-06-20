
from flask import Flask, request, jsonify
import os
import uuid
import requests
from SpotifyPlaylistBuilder import build_smart_playlist_enhanced, refresh_access_token
from spotify_code_generator import SpotifyCodeGenerator

app = Flask(__name__)

@app.route("/")
def index():
    return "MoodQue Webhook is Running"

# --- Glide Playlist Creation Webhook ---
@app.route("/glide-webhook", methods=["POST"])
def handle_glide_webhook():
    data = request.json

    row_id = data.get("row_id")
    genre = data.get("genre", "")
    mood = data.get("mood", "")
    time = int(data.get("time", 30))
    event = data.get("event", "")
    playlist_type = data.get("playlist_type", "clean")
    user_name = data.get("user_name", "Anonymous")
    search_keywords = data.get("search_keywords", "")
    fallback_artist = data.get("fallback_artist", "")

    playlist = build_smart_playlist_enhanced(
        event, genre, time, mood, search_keywords,
        fallback_artist, playlist_type, user_name, 
    )

    playlist_id = playlist.get("id")
    playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
    spotify_code_url = SpotifyCodeGenerator.generate_code_url(playlist_url)
    track_count = playlist.get("track_count", 0)

    # Get cover image
    access_token = refresh_access_token()
    cover_image = ""
    if access_token:
        headers = {"Authorization": f"Bearer {access_token}"}
        res = requests.get(f"https://api.spotify.com/v1/playlists/{playlist_id}/images", headers=headers)
        if res.ok and res.json():
            cover_image = res.json()[0].get("url", "")

    return jsonify({
        "row_id": row_id,
        "playlist_id": playlist_id,
        "spotify_url": playlist_url,
        "spotify_code_url": spotify_code_url,
        "track_count": track_count,
        "cover_image": cover_image
    })


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
    return jsonify({
    
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
