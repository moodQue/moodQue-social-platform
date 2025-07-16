import os
import json
import logging
import requests
from flask import Flask, request, redirect, jsonify
from datetime import datetime

# Initialize Firebase first
import firebase_admin_init
from firebase_admin_init import db

# Now import other modules
from moodque_engine import build_smart_playlist_enhanced
from tracking import track_interaction
from moodque_utilities import (
    get_spotify_access_token,
    get_user_tokens,
    save_user_tokens,
    record_social_interaction,
    record_ml_feedback,
    post_data_back_to_glide
)

# --- Setup ---
app = Flask(__name__)
logger = logging.getLogger("moodQueSocial_webhook")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Spotify OAuth Callback ---
@app.route('/callback')
def spotify_callback():
    code = request.args.get('code')
    if not code:
        return "Missing code in callback URL", 400

    token_url = "https://accounts.spotify.com/api/token"
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_resp = requests.post(token_url, data=payload, headers=headers)

    if token_resp.status_code != 200:
        return f"Failed to get token: {token_resp.text}", 500

    token_data = token_resp.json()
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    token_type = token_data['token_type']

    # Get the user's Spotify ID
    headers = {"Authorization": f"{token_type} {access_token}"}
    profile_resp = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_profile = profile_resp.json()
    user_id = user_profile['id']

    # Save to Firestore
    save_user_tokens(user_id, access_token, refresh_token)
    logger.info(f"✅ Spotify tokens stored for user: {user_id}")

    return redirect("https://yourapp.glide.page")  # Replace with your actual Glide return page

# --- Helper Function: Prepare Response Data ---
def prepare_response_data(row_id, playlist_info, user_id=None, processing_time_start=None):
    processing_duration = None
    if processing_time_start:
        processing_duration = round((datetime.now() - processing_time_start).total_seconds(), 2)

    if playlist_info and isinstance(playlist_info, str):
        playlist_id = playlist_info.split('/')[-1] if '/' in playlist_info else ""
        response_data = {
            "row_id": row_id,
            "user_id": user_id or "unknown",
            "has_code": "true",
            "playlist_id": playlist_id,
            "spotify_url": playlist_info,
            "track_count": "0",
            "spotify_code_url": f"https://scannables.scdn.co/uri/plain/jpeg/black/white/640/spotify:playlist:{playlist_id}",
            "status": "completed",
            "error_message": "",
            "processing_time_seconds": processing_duration,
            "created_at": datetime.now().isoformat(),
            "play_count": 0,
            "like_count": 0,
            "share_count": 0
        }
    elif playlist_info and isinstance(playlist_info, dict):
        response_data = {
            "row_id": row_id,
            "user_id": user_id or "unknown",
            "has_code": "true",
            "playlist_id": playlist_info.get("playlist_id", ""),
            "spotify_url": playlist_info.get("spotify_url", ""),
            "track_count": str(playlist_info.get("track_count", "0")),
            "spotify_code_url": playlist_info.get("spotify_code_url", ""),
            "status": "completed",
            "error_message": "",
            "processing_time_seconds": processing_duration,
            "created_at": datetime.now().isoformat(),
            "play_count": 0,
            "like_count": 0,
            "share_count": 0
        }
    else:
        response_data = {
            "row_id": row_id,
            "user_id": user_id or "unknown",
            "has_code": "false",
            "playlist_id": "",
            "spotify_url": "",
            "track_count": "0",
            "spotify_code_url": "",
            "status": "failed",
            "error_message": "Playlist creation failed - no data returned",
            "processing_time_seconds": processing_duration,
            "created_at": datetime.now().isoformat(),
            "play_count": 0,
            "like_count": 0,
            "share_count": 0
        }

    logger.info(f"📦 Prepared response data: {json.dumps(response_data, indent=2)}")
    return response_data

# --- Glide Social Endpoint (Build and Return) ---
@app.route('/glide_social', methods=['POST'])
def glide_social():
    data = request.get_json()
    logger.info(f"📥 Glide social data received: {json.dumps(data, indent=2)}")

    row_id = data.get("row_id")
    user_id = data.get("user_id")
    genre = data.get("genre")
    artist = data.get("artist")
    mood = data.get("mood")
    event = data.get("event")
    time_duration = data.get("time", 30)  # Default to 30 minutes
    playlist_type = data.get("playlist_type", "clean")
    webhook_return_url = data.get("webhook_return_url")

    processing_start = datetime.now()

    try:
        # Use the updated function signature
        playlist_url = build_smart_playlist_enhanced(
            event_name=event or "My Playlist",
            genre=genre,
            time=time_duration,
            mood_tags=mood,
            search_keywords=None,
            favorite_artist=artist,
            user_id=user_id,
            playlist_type=playlist_type,
            request_id=row_id
        )
        
        logger.info(f"✅ Playlist created: {playlist_url}")
        
    except Exception as e:
        logger.error(f"❌ Playlist creation failed: {e}")
        import traceback
        traceback.print_exc()
        playlist_url = None

    response_data = prepare_response_data(row_id, playlist_url, user_id=user_id, processing_time_start=processing_start)
    
    # Track interaction
    try:
        track_interaction(
            user_id=user_id or "unknown",
            event_type="built_playlist",
            data={
                "playlist_id": response_data.get("playlist_id", ""),
                "mood_tags": [mood] if mood else [],
                "genres": [genre] if genre else [],
                "event": event or "unknown"
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to track interaction: {e}")

    # Send response back to Glide
    try:
        if webhook_return_url:
            res = post_data_back_to_glide(webhook_return_url, response_data)
            if res and res.status_code == 200:
                logger.info(f"✅ Sent response data back to Glide successfully")
            else:
                logger.warning(f"⚠️ Glide response error: {res.status_code if res else 'No response'}")
    except Exception as e:
        logger.error(f"❌ Failed posting back to Glide: {e}")

    return jsonify(response_data)

# --- Legacy Playlist Builder ---
@app.route('/webhook', methods=['POST'])
def playlist_webhook():
    data = request.get_json()
    logger.info(f"📥 Legacy webhook data received: {json.dumps(data, indent=2)}")
    
    row_id = data.get("row_id")
    user_id = data.get("user_id")
    genre = data.get("genre")
    artist = data.get("artist")
    mood = data.get("mood")
    event = data.get("event")
    time_duration = data.get("time", 30)
    playlist_type = data.get("playlist_type", "clean")

    processing_start = datetime.now()

    try:
        playlist_url = build_smart_playlist_enhanced(
            event_name=event or "My Playlist",
            genre=genre,
            time=time_duration,
            mood_tags=mood,
            search_keywords=None,
            favorite_artist=artist,
            user_id=user_id,
            playlist_type=playlist_type,
            request_id=row_id
        )
        
        logger.info(f"✅ Legacy playlist created: {playlist_url}")
        
    except Exception as e:
        logger.error(f"❌ Legacy playlist build failed: {e}")
        import traceback
        traceback.print_exc()
        playlist_url = None

    response_data = prepare_response_data(row_id, playlist_url, user_id=user_id, processing_time_start=processing_start)
    return jsonify(response_data)

# --- Social Interaction Tracker ---
@app.route("/track", methods=["POST"])
def track_event():
    payload = request.get_json()
    logger.info(f"📊 Tracking event: {json.dumps(payload, indent=2)}")
    
    try:
        track_interaction(
            user_id=payload.get("user_id", "unknown"),
            event_type=payload.get("event_type", "unknown"),
            data=payload.get("data", {})
        )
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Failed to track event: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Machine Learning Feedback Endpoint ---
@app.route('/feedback', methods=['POST'])
def ml_feedback():
    payload = request.get_json()
    logger.info(f"🤖 ML feedback received: {json.dumps(payload, indent=2)}")
    
    try:
        result = record_ml_feedback(payload)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"❌ ML feedback failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Health Check ---
@app.route('/')
def root():
    return "MoodQue Social API is running ✅"

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
    
# Add these test endpoints to your moodQueSocial_webhook_service.py
# Make sure they're properly indented and placed after your existing routes

@app.route('/test_firebase', methods=['GET'])
def test_firebase():
    """Test Firebase connection and data writing"""
    try:
        test_doc = {
            "test_timestamp": datetime.now().isoformat(),
            "message": "Firebase connection test",
            "status": "working"
        }
        
        doc_ref = db.collection("test_connection").add(test_doc)
        
        return jsonify({
            "status": "success",
            "message": "Firebase is working properly",
            "test_doc_id": doc_ref[1].id
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Firebase error: {str(e)}"
        }), 500

@app.route('/health_check', methods=['GET'])
def health_check():
    """Check Firebase collections and recent activity"""
    try:
        results = {}
        
        # Count documents in each collection
        collections = ["users", "interactions", "ml_feedback"]
        for collection_name in collections:
            count = len(list(db.collection(collection_name).limit(10).stream()))
            results[f"{collection_name}_count"] = count
        
        return jsonify({
            "status": "success",
            "firebase_health": "operational",
            "collections": results
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/test_user_tokens/<user_id>', methods=['GET'])
def test_user_tokens(user_id):
    """Test user token storage and retrieval"""
    try:
        from moodque_utilities import get_user_tokens, save_user_tokens
        
        # Test saving tokens
        save_user_tokens(user_id, "test_access_token", "test_refresh_token")
        
        # Test retrieving tokens
        tokens = get_user_tokens(user_id)
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "tokens_saved": True,
            "tokens_retrieved": tokens is not None,
            "token_data": tokens
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500