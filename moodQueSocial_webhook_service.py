import os
import json
import logging
import requests
import urllib.parse
import time
import uuid
from moodque_engine import MoodQueEngine
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

def prepare_response_data(row_id, playlist_info, user_id=None, processing_time_start=None, track_count=None):
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
            "track_count": str(track_count) if track_count is not None else "0",  # FIXED: Use actual track count
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
            "track_count": str(playlist_info.get("track_count", track_count or "0")),  # FIXED: Use actual track count
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

@app.route("/callback", methods=["GET"])
def spotify_callback():
    code = request.args.get("code")
    if not code:
        return "Missing authorization code", 400

    # Step 1: Exchange code for token
    token_url = "https://accounts.spotify.com/api/token"
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET")
    }

    try:
        token_resp = requests.post(token_url, data=payload)
        token_resp.raise_for_status()
        token_data = token_resp.json()
    except Exception as e:
        print(f"❌ Failed to exchange token: {e}")
        return "Token exchange failed", 500

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        return "No access token received", 500

    # Step 2: Get user profile
    try:
        profile_resp = requests.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        profile_resp.raise_for_status()
        user_profile = profile_resp.json()
    except Exception as e:
        print(f"❌ Failed to fetch user profile: {e}")
        return "Failed to get profile", 500

    spotify_user_id = user_profile.get("id")
    if not spotify_user_id:
        return "Missing Spotify user ID", 500

    # Step 3: Get rich playback data
    from moodque_utilities import fetch_user_playback_data
    playback_data = fetch_user_playback_data({"Authorization": f"Bearer {access_token}"})

    # Step 4: Save user to Firestore
    user_doc = {
        "spotify_user_id": spotify_user_id,
        "spotify_display_name": user_profile.get("display_name"),
        "spotify_email": user_profile.get("email"),
        "spotify_birth_year": user_profile.get("birthdate", "")[:4],
        "spotify_country": user_profile.get("country"),
        "spotify_product": user_profile.get("product"),
        "spotify_images": user_profile.get("images", []),
        "connected_at": datetime.now().isoformat(),
        "spotify_playback_data": playback_data
    }

    try:
        db.collection("users").document(spotify_user_id).set(user_doc, merge=True)
        print(f"✅ Saved Spotify user: {spotify_user_id}")
    except Exception as e:
        print(f"❌ Failed to save user to Firebase: {e}")
        return "Firestore error", 500

    # Step 5: Save tokens
    from moodque_utilities import save_user_tokens
    try:
        save_user_tokens(spotify_user_id, access_token, refresh_token)
    except Exception as e:
        print(f"⚠️ Failed to save tokens: {e}")

    return redirect("https://moodque.glide.page")  # Or your frontend page


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
# Fixed version of your glide_social endpoint in moodQueSocial_webhook_service.py

@app.route('/glide_social', methods=['POST'])
def glide_social():
    data = request.get_json()
    logger.info(f"📥 Glide social data received: {json.dumps(data, indent=2)}")

    # FIXED: Extract row_id more thoroughly and DO NOT generate fallback
    row_id = None
    
    # Check all possible locations for row_id
    if isinstance(data, dict):
        # Try direct keys first (including Glide's emoji-prefixed format)
        row_id = (data.get("row_id") or 
                 data.get("id") or 
                 data.get("rowID") or
                 data.get("Row ID") or
                 data.get("🔒 row_id") or  # FIXED: Handle Glide's emoji format
                 data.get("🔒row_id"))     # Alternative without space
        
        # If still not found, search through all keys for anything containing 'row_id'
        if not row_id:
            for key, value in data.items():
                if 'row_id' in key.lower():
                    row_id = value
                    logger.info(f"🔍 Found row_id in field: '{key}' = '{value}'")
                    break
        
        # If not found, check in body
        if not row_id and "body" in data:
            body_data = data.get("body", {})
            if isinstance(body_data, dict):
                row_id = (body_data.get("row_id") or 
                         body_data.get("id") or 
                         body_data.get("rowID") or
                         body_data.get("Row ID") or
                         body_data.get("🔒 row_id") or
                         body_data.get("🔒row_id"))
                
                # Search in body for row_id-containing keys
                if not row_id:
                    for key, value in body_data.items():
                        if 'row_id' in key.lower():
                            row_id = value
                            logger.info(f"🔍 Found row_id in body field: '{key}' = '{value}'")
                            break
    
    # CRITICAL: If no row_id found, log the full request and return error
    if not row_id:
        logger.error(f"❌ CRITICAL: No row_id found in request!")
        logger.error(f"📋 Full request data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        logger.error(f"📋 Body keys: {list(data.get('body', {}).keys()) if isinstance(data.get('body'), dict) else 'No body or not dict'}")
        
        # Return error response instead of generating fallback
        error_response = {
            "error": "No row_id provided in request",
            "status": "failed",
            "message": "row_id is required but was not found in the request data"
        }
        return jsonify(error_response), 400
    
    logger.info(f"🔑 Found row_id: {row_id}")
    
    user_id = data.get("user_id") or data.get("userId") or "anonymous"
    
    # FIXED: Handle nested data structure if present
    body_data = data.get("body", {}) if isinstance(data.get("body"), dict) else {}
    
    # Extract parameters from both root level and body level
    genre = data.get("genre") or body_data.get("genre") or "pop"
    artist = data.get("artist") or data.get("favorite_artist") or body_data.get("artist") or body_data.get("favorite_artist")
    mood = data.get("mood") or data.get("mood_tags") or body_data.get("mood") or body_data.get("mood_tags")
    event = data.get("event") or data.get("event_name") or body_data.get("event") or body_data.get("event_name") or "My Playlist"
    
    # FIXED: Safer time duration handling
    try:
        time_duration = int(data.get("time", body_data.get("time", 30)))
    except (ValueError, TypeError):
        time_duration = 30
        
    playlist_type = data.get("playlist_type", body_data.get("playlist_type", "clean"))
    birth_year = data.get("birth_year") or body_data.get("birth_year")
    search_keywords = data.get("search_keywords") or body_data.get("search_keywords")
    
    # FIXED: Get webhook URL properly
    webhook_return_url = (data.get("webhook_return_url") or 
                         body_data.get("webhook_return_url") or 
                         os.environ.get("GLIDE_RETURN_WEBHOOK_URL"))

    # ADDED: Log all extracted parameters for debugging
    logger.info(f"🔍 Extracted parameters:")
    logger.info(f"  row_id: {row_id}")
    logger.info(f"  user_id: {user_id}")
    logger.info(f"  genre: {genre}")
    logger.info(f"  artist: {artist}")
    logger.info(f"  mood: {mood}")
    logger.info(f"  event: {event}")
    logger.info(f"  time: {time_duration}")
    logger.info(f"  playlist_type: {playlist_type}")
    logger.info(f"  birth_year: {birth_year}")

    processing_start = datetime.now()
    track_count = 0

    try:
        # CRITICAL: Pass the exact row_id from Glide as request_id
        playlist_result = build_smart_playlist_enhanced(
            event_name=event,
            genre=genre,
            time=time_duration,
            mood_tags=mood,
            search_keywords=search_keywords,
            favorite_artist=artist,
            user_id=user_id,
            playlist_type=playlist_type,
            request_id=row_id,  # FIXED: This must be the exact row_id from Glide
            birth_year=birth_year
        )
        
        if playlist_result:
            logger.info(f"✅ Playlist created: {playlist_result}")
            try:
                # Get actual track count from Spotify
                from moodque_auth import get_spotify_access_token
                token = get_spotify_access_token()
                headers = {"Authorization": f"Bearer {token}"}
                playlist_id = playlist_result.split('/')[-1]
                playlist_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
                response = requests.get(playlist_url, headers=headers)
                if response.status_code == 200:
                    playlist_data = response.json()
                    track_count = playlist_data.get("tracks", {}).get("total", 0)
                    logger.info(f"📊 Actual track count from Spotify: {track_count}")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch track count: {e}")
        else:
            logger.error(f"❌ Playlist creation returned None")
        
    except Exception as e:
        logger.error(f"❌ Playlist creation failed: {e}")
        import traceback
        traceback.print_exc()
        playlist_result = None

    # CRITICAL: Use the exact row_id from Glide in response
    response_data = prepare_response_data(
        row_id=row_id,  # This should be the exact row_id from Glide
        playlist_info=playlist_result,
        user_id=user_id,
        processing_time_start=processing_start,
        track_count=track_count
    )

    # Post response back to Glide webhook if available
    if webhook_return_url:
        try:
            logger.info(f"📤 Sending playlist result to Glide return webhook: {webhook_return_url}")
            logger.info(f"🔑 Response data row_id: {response_data.get('row_id')}")
            post_response = post_data_back_to_glide(webhook_return_url, response_data)
            if post_response and post_response.status_code == 200:
                logger.info("✅ Successfully posted to Glide webhook")
            else:
                logger.warning(f"⚠️ Glide webhook returned status: {post_response.status_code if post_response else 'no response'}")
        except Exception as e:
            logger.error(f"❌ Failed to send to Glide webhook: {e}")

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
    
    # Add this endpoint to your moodQueSocial_webhook_service.py file
# Place it with your other route definitions

@app.route('/health_detailed', methods=['GET'])
def health_detailed():
    """Detailed health check for all system components"""
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # Check Firebase
        try:
            test_doc = db.collection("health_check").document("test")
            test_doc.set({"timestamp": datetime.now().isoformat()})
            health_status["components"]["firebase"] = "healthy"
        except Exception as e:
            health_status["components"]["firebase"] = f"unhealthy: {str(e)}"
            health_status["overall_status"] = "degraded"
        
        # Check Spotify API
        try:
            from moodque_auth import get_spotify_access_token
            token = get_spotify_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            res = requests.get("https://api.spotify.com/v1/me", headers=headers, timeout=5)
            if res.status_code in [200, 401]:  # 401 is expected for app tokens
                health_status["components"]["spotify_api"] = "healthy"
            else:
                health_status["components"]["spotify_api"] = f"unhealthy: HTTP {res.status_code}"
                health_status["overall_status"] = "degraded"
        except Exception as e:
            health_status["components"]["spotify_api"] = f"unhealthy: {str(e)}"
            health_status["overall_status"] = "degraded"
        
        # Check Last.fm API (if available)
        try:
            lastfm_key = os.environ.get("LASTFM_API_KEY")
            if lastfm_key:
                health_status["components"]["lastfm_api"] = "configured"
            else:
                health_status["components"]["lastfm_api"] = "not_configured"
        except Exception as e:
            health_status["components"]["lastfm_api"] = f"error: {str(e)}"
        
        status_code = 200 if health_status["overall_status"] == "healthy" else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "overall_status": "error",
            "error": str(e)
        }), 500
        
        # Add this debugging endpoint to your moodQueSocial_webhook_service.py

@app.route('/debug_parameters', methods=['POST'])
def debug_parameters():
    """Debug endpoint to test parameter extraction from Glide"""
    try:
        raw_data = request.get_json()
        logger.info(f"🔍 DEBUG: Raw request data received:")
        logger.info(f"   Type: {type(raw_data)}")
        logger.info(f"   Content: {json.dumps(raw_data, indent=2)}")
        
        # Test parameter extraction logic
        data = raw_data
        body_data = data.get("body", {}) if isinstance(data.get("body"), dict) else {}
        
        extracted_params = {
            "raw_data_keys": list(data.keys()) if isinstance(data, dict) else "Not a dict",
            "body_data_keys": list(body_data.keys()) if isinstance(body_data, dict) else "No body or not dict",
            
            # Test all extraction methods
            "row_id": data.get("row_id") or data.get("id") or "NOT_FOUND",
            "user_id": data.get("user_id") or data.get("userId") or "NOT_FOUND",
            "genre": data.get("genre") or body_data.get("genre") or "NOT_FOUND",
            "artist": data.get("artist") or data.get("favorite_artist") or body_data.get("artist") or body_data.get("favorite_artist") or "NOT_FOUND",
            "mood": data.get("mood") or data.get("mood_tags") or body_data.get("mood") or body_data.get("mood_tags") or "NOT_FOUND",
            "event": data.get("event") or data.get("event_name") or body_data.get("event") or body_data.get("event_name") or "NOT_FOUND",
            "time": data.get("time", body_data.get("time", "NOT_FOUND")),
            "playlist_type": data.get("playlist_type", body_data.get("playlist_type", "NOT_FOUND")),
            "birth_year": data.get("birth_year") or body_data.get("birth_year") or "NOT_FOUND",
        }
        
        logger.info(f"🎯 DEBUG: Extracted parameters:")
        for key, value in extracted_params.items():
            logger.info(f"   {key}: {value}")
        
        return jsonify({
            "status": "debug_success",
            "raw_data": raw_data,
            "extracted_parameters": extracted_params,
            "recommendations": {
                "missing_parameters": [k for k, v in extracted_params.items() if v == "NOT_FOUND"],
                "data_structure": "Check if Glide is sending data in 'body' object or root level",
                "next_steps": "Use this info to adjust parameter extraction in glide_social endpoint"
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Debug endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "debug_error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/test_engine_directly', methods=['POST'])
def test_engine_directly():
    """Test the MoodQue engine directly with known good parameters"""
    try:
        # Test with hardcoded parameters
        test_request_data = {
            'event_name': 'Test Playlist',
            'genre': 'pop',
            'time': 30,
            'mood_tags': 'upbeat',
            'search_keywords': None,
            'favorite_artist': 'Taylor Swift',
            'user_id': 'test_user',
            'playlist_type': 'clean',
            'request_id': 'test_001',
            'birth_year': 1995
        }
        
        logger.info(f"🧪 Testing engine with: {test_request_data}")
        
        # Test just the engine initialization
        engine = MoodQueEngine(test_request_data)
        
        return jsonify({
            "status": "engine_test_success",
            "request_id": engine.request_id,
            "user_id": engine.user_id,
            "formatted_params": engine._format_parameters(),
            "message": "Engine initialized successfully with test parameters"
        })
        
    except Exception as e:
        logger.error(f"❌ Engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "engine_test_error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
        
# Add this to your moodQueSocial_webhook_service.py file

@app.route('/disconnect_spotify', methods=['POST', 'GET'])
def disconnect_spotify():
    """Disconnect user's Spotify account"""
    try:
        # Get user info from request
        if request.method == 'POST':
            data = request.get_json()
            user_email = data.get('user_email') or data.get('email')
            return_url = data.get('return_url', 'https://moodque.glide.page')
        else:
            # GET request with query parameters
            user_email = request.args.get('user_email') or request.args.get('email')
            return_url = request.args.get('return_url', 'https://moodque.glide.page')
        
        if not user_email:
            return jsonify({"error": "No user email provided"}), 400
        
        # Find and remove user's Spotify connection from Firebase
        users_ref = db.collection("users")
        
        # Search by email
        query = users_ref.where("spotify_email", "==", user_email).limit(1)
        docs = list(query.stream())
        
        if not docs:
            # Try searching by glide_user_email
            query = users_ref.where("glide_user_email", "==", user_email).limit(1) 
            docs = list(query.stream())
        
        if docs:
            # Remove Spotify connection data
            user_doc = docs[0]
            user_doc.reference.update({
                "spotify_access_token": None,
                "spotify_refresh_token": None,
                "spotify_user_id": None,
                "spotify_display_name": None,
                "spotify_email": None,
                "spotify_connected": False,
                "disconnected_at": datetime.now().isoformat()
            })
            
            logger.info(f"✅ Disconnected Spotify for user: {user_email}")
            
            if request.method == 'GET':
                # Redirect back to app with success
                success_url = f"{return_url}?spotify_disconnected=true&status=success"
                return redirect(success_url)
            else:
                # JSON response for POST
                return jsonify({
                    "status": "success",
                    "message": "Spotify account disconnected successfully",
                    "spotify_connected": False,
                    "disconnected_at": datetime.now().isoformat()
                })
        else:
            logger.warning(f"⚠️ No Spotify connection found for user: {user_email}")
            
            if request.method == 'GET':
                error_url = f"{return_url}?spotify_error=not_connected"
                return redirect(error_url)
            else:
                return jsonify({
                    "status": "error", 
                    "message": "No Spotify connection found for this user"
                }), 404
                
    except Exception as e:
        logger.error(f"❌ Error disconnecting Spotify: {e}")
        
        if request.method == 'GET':
            error_url = f"{return_url}?spotify_error=disconnect_failed"
            return redirect(error_url)
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to disconnect Spotify: {str(e)}"
            }), 500

@app.route('/spotify_status', methods=['POST'])
def get_spotify_status():
    """Get current Spotify connection status for a user"""
    try:
        data = request.get_json()
        user_email = data.get('user_email') or data.get('email')
        
        if not user_email:
            return jsonify({"spotify_connected": False, "error": "No email provided"}), 400
        
        # Search Firebase for user's Spotify connection
        users_ref = db.collection("users")
        query = users_ref.where("spotify_email", "==", user_email).limit(1)
        docs = list(query.stream())
        
        if not docs:
            # Try searching by glide_user_email
            query = users_ref.where("glide_user_email", "==", user_email).limit(1)
            docs = list(query.stream())
        
        if docs:
            user_data = docs[0].to_dict()
            return jsonify({
                "spotify_connected": bool(user_data.get("spotify_refresh_token")),
                "spotify_user_id": user_data.get("spotify_user_id", ""),
                "spotify_display_name": user_data.get("spotify_display_name", ""),
                "connected_at": user_data.get("connected_at", ""),
                "status": "found"
            })
        else:
            return jsonify({
                "spotify_connected": False,
                "spotify_user_id": "",
                "spotify_display_name": "",
                "connected_at": "",
                "status": "not_found"
            })
            
    except Exception as e:
        logger.error(f"❌ Error checking Spotify status: {e}")
        return jsonify({
            "spotify_connected": False,
            "error": str(e)
        }), 500        