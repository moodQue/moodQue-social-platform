from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "✅ moodQue Social Webhook Service is running!", 200

@app.route("/glide_social", methods=["POST"])
def glide_social():
    try:
        payload = request.get_json()
        data = payload.get("body", {})

        print("🎯 Received Payload from Glide:", data)

        # Extract expected fields
        row_id = data.get("row_id")
        genre = data.get("genre")
        mood_tags = data.get("mood_tags")
        event_name = data.get("event_name")
        playlist_type = data.get("playlist_type")
        favorite_artist = data.get("favorite_artist")
        search_keywords = data.get("search_keywords")
        time = data.get("time")

        print(f"🆔 row_id: {row_id}")
        print(f"🎵 genre: {genre}")
        print(f"🏷️ mood_tags: {mood_tags}")
        print(f"📅 event_name: {event_name}")
        print(f"🧼 playlist_type: {playlist_type}")
        print(f"🎤 favorite_artist: {favorite_artist}")
        print(f"🔍 search_keywords: {search_keywords}")
        print(f"⏱️ time: {time}")

        return jsonify({
            "status": "success",
            "row_id": row_id,
            "genre": genre,
            "mood_tags": mood_tags,
            "event_name": event_name,
            "playlist_type": playlist_type,
            "favorite_artist": favorite_artist,
            "search_keywords": search_keywords,
            "time": time
        }), 200

    except Exception as e:
        print("❌ Error handling /glide_social:", str(e))
        return jsonify({"error": str(e)}), 500

# Optional placeholders for future routes
@app.route("/like_playlist", methods=["POST"])
def like_playlist():
    return jsonify({"message": "like_playlist endpoint is live"}), 200

@app.route("/view_playlist", methods=["POST"])
def view_playlist():
    return jsonify({"message": "view_playlist endpoint is live"}), 200

@app.route("/get_user_profile", methods=["POST"])
def get_user_profile():
    return jsonify({"message": "get_user_profile endpoint is live"}), 200
