import os
import json
import logging
import requests
import urllib.parse
import time
from moodque_auth import auth_bp
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

# Add this function to your moodQueSocial_webhook_service.py file
# Place it before your route definitions

def prepare_response_data(row_id, playlist_info, user_id=None, processing_time_start=None):
    """Helper function to prepare response data for playlist creation"""
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

# --- Setup ---
app = Flask(__name__)
logger = logging.getLogger("moodQueSocial_webhook")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app.register_blueprint(auth_bp)

# --- Spotify OAuth Callback ---
# Replace your entire callback function with this complete version:

# Updated Spotify callback using your existing environment variable

@app.route('/callback')
def spotify_callback():
    """Spotify OAuth callback that sends data to Glide webhook"""
    code = request.args.get('code')
    state = request.args.get('state', '')
    
    if not code:
        return redirect("https://moodque.glide.page?spotify_error=no_code")

    # Parse state to get user info
    state_params = {}
    if state:
        try:
            for param in state.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    state_params[key] = urllib.parse.unquote(value)
        except Exception as e:
            print(f"Error parsing state: {e}")
    
    glide_user_email = state_params.get("user_id", "anonymous")
    return_url = state_params.get("return_url", "https://moodque.glide.page")
    
    print(f"📥 Spotify callback - User: {glide_user_email}")

    # Exchange code for tokens
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
        print(f"❌ Token exchange failed: {token_resp.text}")
        return redirect(f"{return_url}?spotify_error=token_failed")

    token_data = token_resp.json()
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 3600)

    # Get Spotify user profile
    profile_headers = {"Authorization": f"Bearer {access_token}"}
    profile_resp = requests.get("https://api.spotify.com/v1/me", headers=profile_headers)
    
    if profile_resp.status_code != 200:
        print(f"❌ Profile fetch failed: {profile_resp.text}")
        return redirect(f"{return_url}?spotify_error=profile_failed")

    user_profile = profile_resp.json()
    spotify_user_id = user_profile['id']
    spotify_display_name = user_profile.get('display_name', spotify_user_id)
    spotify_email = user_profile.get('email', '')
    
    print(f"✅ Spotify profile: {spotify_display_name} ({spotify_user_id})")

    # Save to Firebase
    try:
        db.collection("users").document(spotify_user_id).set({
            "glide_user_email": glide_user_email,
            "spotify_user_id": spotify_user_id,
            "spotify_access_token": access_token,
            "spotify_refresh_token": refresh_token,
            "spotify_token_expires_at": str(int(time.time()) + expires_in),
            "spotify_display_name": spotify_display_name,
            "spotify_email": spotify_email,
            "connected_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }, merge=True)
        
        print(f"✅ Saved to Firebase: {glide_user_email} -> {spotify_user_id}")
        
    except Exception as e:
        print(f"❌ Firebase save failed: {e}")
        return redirect(f"{return_url}?spotify_error=database_failed")

    # Send data to Glide webhook using existing environment variable
    webhook_data = {
        "type": "spotify_connection",
        "user_email": glide_user_email,
        "spotify_connected": True,
        "spotify_user_id": spotify_user_id,
        "spotify_display_name": spotify_display_name,
        "spotify_email": spotify_email,
        "connected_at": datetime.now().isoformat(),
        "status": "connected",  # Changed from "completed" to "connected"
        "processing_time_seconds": 0,
        "created_at": datetime.now().isoformat()
    }

    # Use your existing environment variable
    glide_webhook_url = os.environ.get("GLIDE_RETURN_WEBHOOK_URL")
    
    if glide_webhook_url:
        try:
            webhook_response = requests.post(glide_webhook_url, json=webhook_data, timeout=10)
            if webhook_response.status_code == 200:
                print(f"✅ Sent Spotify connection data to Glide webhook successfully")
            else:
                print(f"⚠️ Glide webhook response: {webhook_response.status_code}")
        except Exception as e:
            print(f"❌ Failed to send to Glide webhook: {e}")
    else:
        print("⚠️ GLIDE_RETURN_WEBHOOK_URL not configured")

    # Redirect back to Glide app with success parameters
    success_params = {
        "spotify_connected": "true",
        "spotify_user_id": spotify_user_id,
        "spotify_display_name": spotify_display_name,
        "connection_status": "connected"  # Changed to "connected"
    }
    
    param_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in success_params.items()])
    success_url = f"{return_url}?{param_string}"
    
    print(f"🔄 Redirecting to: {success_url}")
    return redirect(success_url)

# Also add a test endpoint that uses the same webhook
@app.route('/test_spotify_webhook', methods=['POST'])
def test_spotify_webhook():
    """Test Spotify webhook integration"""
    test_data = {
        "type": "spotify_connection",
        "user_email": "test@example.com",
        "spotify_connected": True,
        "spotify_user_id": "test_spotify_user",
        "spotify_display_name": "Test User",
        "spotify_email": "test@spotify.com",
        "connected_at": datetime.now().isoformat(),
        "status": "connected",
        "created_at": datetime.now().isoformat()
    }

    glide_webhook_url = os.environ.get("GLIDE_RETURN_WEBHOOK_URL")
    
    if not glide_webhook_url:
        return jsonify({
            "status": "error",
            "error": "GLIDE_RETURN_WEBHOOK_URL not configured"
        }), 500
    
    try:
        response = requests.post(glide_webhook_url, json=test_data, timeout=10)
        return jsonify({
            "status": "success",
            "webhook_response_code": response.status_code,
            "test_data": test_data,
            "webhook_url": glide_webhook_url
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# Keep your existing prepare_response_data function as-is
# (No changes needed to that function)

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
        
@app.route('/track_user_session', methods=['POST'])
def track_user_session():
        """Track user login and update their profile"""
        try:
            data = request.get_json()
            user_email = data.get('user_email')
            action = data.get('action', 'login')  # login, logout, activity
    
            if not user_email:
                return jsonify({"error": "No user email provided"}), 400
    
            # Update or create user profile in Glide
            session_data = {
                "email": user_email,
                "is_signed_in": action == "login",
                "last_active": datetime.now().isoformat(),
            }
    
            # Log to Firebase for tracking
            db.collection("user_sessions").add({
                "user_email": user_email,
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "user_agent": request.headers.get('User-Agent', ''),
                "ip_address": request.remote_addr
            })
    
            return jsonify({
                "status": "success",
                "user_email": user_email,
                "action": action,
                "session_data": session_data
            })
    
        except Exception as e:
            logger.error(f"Error tracking user session: {e}")
            return jsonify({"error": str(e)}), 500

@app.route('/check_spotify_status', methods=['POST'])
def check_spotify_status():
    """Check if user has connected Spotify"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        
        if not user_email:
            return jsonify({"spotify_connected": False})
        
        # Search Firebase for user's Spotify connection
        users_ref = db.collection("users")
        query = users_ref.where("glide_user_email", "==", user_email).limit(1)
        docs = list(query.stream())
        
        if docs:
            user_data = docs[0].to_dict()
            return jsonify({
                "spotify_connected": True,
                "spotify_user_id": user_data.get("spotify_user_id", ""),
                "spotify_display_name": user_data.get("spotify_display_name", ""),
                "connected_at": user_data.get("connected_at", "")
            })
        else:
            return jsonify({
                "spotify_connected": False,
                "spotify_user_id": "",
                "spotify_display_name": "",
                "connected_at": ""
            })
            
    except Exception as e:
        logger.error(f"Error checking Spotify status: {e}")
        return jsonify({"spotify_connected": False})

@app.route('/update_glide_profile', methods=['POST'])
def update_glide_profile():
    """Update user profile in Glide after Spotify connection"""
    try:
        data = request.get_json()
        
        # This endpoint returns data that Glide can use to update the user profile
        return jsonify({
            "status": "success",
            "user_data": {
                "spotify_connected": True,
                "spotify_user_id": data.get("spotify_user_id"),
                "spotify_display_name": data.get("spotify_display_name"),
                "connected_at": data.get("connected_at")
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating Glide profile: {e}")
        return jsonify({"status": "error"})