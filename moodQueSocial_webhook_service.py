import os
import json
import logging
import requests
import urllib.parse
import time
import uuid
import base64
from moodque_engine import MoodQueEngine
from moodque_auth import auth_bp
from flask import Flask, request, redirect, jsonify
from datetime import datetime
from firebase_admin import firestore
from ml_reengagement_system import MLReengagementEngine

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

# Helper function to prepare response data for playlist creation
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
            "track_count": str(track_count) if track_count is not None else "0",
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
            "track_count": str(playlist_info.get("track_count", track_count or "0")),
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

# --- FIXED SPOTIFY OAUTH CALLBACK ---
# Updated Spotify OAuth callback in moodQueSocial_webhook_service.py
# Replace the existing callback function with this updated version

@app.route("/callback", methods=["GET"])
def spotify_callback():
    """Spotify OAuth callback that gracefully handles 403 errors and queues users for manual approval"""
    
    # Extract parameters
    code = request.args.get("code")
    error = request.args.get("error")
    state = request.args.get("state", "")
    
    print(f"🔐 Spotify callback received:")
    print(f"   Code: {'Present' if code else 'Missing'}")
    print(f"   Error: {error}")
    print(f"   State: {state}")
    
    # Parse state parameters
    state_params = {}
    if state:
        try:
            for param in state.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    state_params[key] = urllib.parse.unquote(value)
        except Exception as e:
            print(f"⚠️ Error parsing state: {e}")
    
    glide_user_email = state_params.get("user_email", "")
    glide_row_id = state_params.get("row_id", "")
    return_url = state_params.get("return_url", "https://moodque.glide.page")
    
    # Initialize webhook data
    connection_timestamp = datetime.now().isoformat()
    webhook_data = {
        "jsonBody": {
            "row_id": glide_row_id or "unknown",
            "status": "failed",
            "user_id": "unknown",
            "has_code": "false",
            "created_at": connection_timestamp,
            "like_count": 0,
            "play_count": 0,
            "playlist_id": "",
            "shared_count": 0,
            "spotify_url": "",
            "spotify_connected": False,
            "spotify_user_id": "",
            "spotify_display_name": "",
            "spotify_connected_at": "",
            "spotify_avatar_url": "",
            "spotify_email": "",
            "spotify_country": "",
            "spotify_product": "",
            "spotify_followers": 0,
            "glide_user_email": glide_user_email,
            "error_message": "",
            "connection_step": "started",
            "pending_approval": False
        }
    }
    
    # Handle OAuth errors
    if error:
        print(f"❌ Spotify OAuth error: {error}")
        webhook_data["jsonBody"]["error_message"] = f"OAuth error: {error}"
        webhook_data["jsonBody"]["connection_step"] = "oauth_error"
        send_webhook_to_glide(webhook_data)
        return redirect(f"{return_url}?spotify_error=oauth_denied")
    
    if not code:
        print("❌ Missing authorization code")
        webhook_data["jsonBody"]["error_message"] = "Missing authorization code"
        webhook_data["jsonBody"]["connection_step"] = "no_code"
        send_webhook_to_glide(webhook_data)
        return redirect(f"{return_url}?spotify_error=no_code")
    
    # We have a code - user completed OAuth flow
    webhook_data["jsonBody"]["has_code"] = "true"
    webhook_data["jsonBody"]["connection_step"] = "token_exchange"
    
    # Token exchange setup
    token_url = "https://accounts.spotify.com/api/token"
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if not all([redirect_uri, client_id, client_secret]):
        print("❌ Missing Spotify credentials")
        webhook_data["jsonBody"]["error_message"] = "Missing Spotify configuration"
        webhook_data["jsonBody"]["connection_step"] = "config_error"
        send_webhook_to_glide(webhook_data)
        return redirect(f"{return_url}?spotify_error=config_error")
    
    # Exchange code for tokens
    auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    token_headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    try:
        print("🔄 Exchanging code for tokens...")
        token_resp = requests.post(token_url, headers=token_headers, data=token_payload, timeout=10)
        
        if token_resp.status_code != 200:
            print(f"❌ Token exchange failed: {token_resp.status_code}")
            webhook_data["jsonBody"]["error_message"] = f"Token exchange failed: {token_resp.status_code}"
            webhook_data["jsonBody"]["connection_step"] = "token_failed"
            send_webhook_to_glide(webhook_data)
            return redirect(f"{return_url}?spotify_error=token_failed")
        
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        token_scope = token_data.get("scope", "")
        
        print("✅ Token exchange successful")
        print(f"   Token scope: {token_scope}")
        
    except Exception as e:
        print(f"❌ Token exchange exception: {e}")
        webhook_data["jsonBody"]["error_message"] = f"Token exchange error: {str(e)}"
        webhook_data["jsonBody"]["connection_step"] = "token_exception"
        send_webhook_to_glide(webhook_data)
        return redirect(f"{return_url}?spotify_error=token_failed")
    
    # Try to get user profile
    user_profile = {}
    spotify_user_id = "unknown"
    profile_success = False
    
    try:
        print("👤 Fetching user profile...")
        profile_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        profile_resp = requests.get(
            "https://api.spotify.com/v1/me",
            headers=profile_headers,
            timeout=10
        )
        
        print(f"   Profile response status: {profile_resp.status_code}")
        
        if profile_resp.status_code == 200:
            # SUCCESS - User is already approved
            user_profile = profile_resp.json()
            profile_success = True
            spotify_user_id = user_profile.get("id", "unknown")
            
            print("✅ User profile fetched - user is approved!")
            
            webhook_data["jsonBody"].update({
                "status": "connected",
                "user_id": spotify_user_id,
                "spotify_connected": True,
                "spotify_user_id": spotify_user_id,
                "spotify_display_name": user_profile.get("display_name", ""),
                "spotify_email": user_profile.get("email", ""),
                "spotify_country": user_profile.get("country", ""),
                "spotify_product": user_profile.get("product", ""),
                "spotify_followers": user_profile.get("followers", {}).get("total", 0),
                "spotify_avatar_url": user_profile.get("images", [{}])[0].get("url", "") if user_profile.get("images") else "",
                "spotify_url": f"https://open.spotify.com/user/{spotify_user_id}",
                "spotify_connected_at": connection_timestamp,
                "connection_step": "profile_success",
                "pending_approval": False
            })
            
        elif profile_resp.status_code == 403:
            # USER NEEDS APPROVAL - Handle gracefully
            print("🔄 403 Forbidden - User needs to be added to Developer Dashboard")
            print(f"   Response: {profile_resp.text}")
            
            # Store pending user information for manual approval
            pending_user_data = {
                "glide_user_email": glide_user_email,
                "glide_row_id": glide_row_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": str(int(time.time()) + expires_in),
                "token_scope": token_scope,
                "requested_at": connection_timestamp,
                "status": "pending_spotify_approval",
                "oauth_completed": True,
                "profile_accessible": False
            }
            
            # Save pending user to Firebase for tracking
            try:
                pending_doc_id = f"pending_{int(time.time())}_{glide_user_email.replace('@', '_').replace('.', '_')}"
                db.collection("pending_users").document(pending_doc_id).set(pending_user_data)
                print(f"✅ Stored pending user data: {pending_doc_id}")
            except Exception as e:
                print(f"⚠️ Failed to store pending user data: {e}")
            
            # Update webhook for pending approval
            webhook_data["jsonBody"].update({
                "status": "pending_approval", 
                "user_id": f"pending_{glide_user_email}",
                "spotify_connected": False,
                "spotify_user_id": "",
                "spotify_display_name": "",
                "spotify_email": glide_user_email,  # Use the email we have
                "error_message": "User needs to be added to Spotify Developer Dashboard",
                "connection_step": "pending_approval",
                "pending_approval": True,
                "oauth_completed": True,
                "instructions": "Admin: Add this user's email to your Spotify app's User Management section"
            })
            
        else:
            # OTHER ERROR
            print(f"❌ Unexpected profile fetch error: {profile_resp.status_code}")
            webhook_data["jsonBody"].update({
                "error_message": f"Profile fetch failed: {profile_resp.status_code}",
                "connection_step": "profile_error"
            })
            
    except Exception as e:
        print(f"❌ Profile fetch exception: {e}")
        webhook_data["jsonBody"].update({
            "error_message": f"Profile fetch error: {str(e)}",
            "connection_step": "profile_exception"
        })
    
    # Save successful user data to Firebase
    if profile_success:
        try:
            user_doc = {
                "spotify_user_id": spotify_user_id,
                "spotify_display_name": user_profile.get("display_name", ""),
                "spotify_email": user_profile.get("email", ""),
                "spotify_access_token": access_token,
                "spotify_refresh_token": refresh_token,
                "spotify_token_expires_at": str(int(time.time()) + expires_in),
                "spotify_token_scope": token_scope,
                "spotify_connected": True,
                "spotify_country": user_profile.get("country", ""),
                "spotify_product": user_profile.get("product", ""),
                "spotify_followers": user_profile.get("followers", {}).get("total", 0),
                "spotify_images": user_profile.get("images", []),
                "spotify_avatar_url": user_profile.get("images", [{}])[0].get("url", "") if user_profile.get("images") else "",
                "glide_user_email": glide_user_email,
                "glide_row_id": glide_row_id,
                "connected_at": connection_timestamp,
                "last_token_refresh": connection_timestamp,
                "connection_method": "oauth_callback",
                "connection_source": "moodque_app"
            }
            
            db.collection("users").document(spotify_user_id).set(user_doc, merge=True)
            print(f"✅ User data saved: {spotify_user_id}")
            
        except Exception as e:
            print(f"❌ Firebase save failed: {e}")
            webhook_data["jsonBody"]["error_message"] += f" | Firebase error: {str(e)}"
    
    # ALWAYS send webhook data to Glide
    send_webhook_to_glide(webhook_data)
    
    # Determine redirect based on outcome
    if profile_success:
        # Full success
        success_params = {
            "spotify_connected": "true",
            "spotify_user": spotify_user_id,
            "connection_status": "success"
        }
        success_url = f"{return_url}?" + "&".join([
            f"{k}={urllib.parse.quote(str(v))}" for k, v in success_params.items()
        ])
        print(f"✅ Full Spotify connection successful!")
        return redirect(success_url)
    
    elif webhook_data["jsonBody"]["pending_approval"]:
        # Pending approval
        pending_params = {
            "spotify_connected": "pending",
            "connection_status": "pending_approval",
            "message": "Your Spotify connection is pending approval. You'll be notified once it's activated.",
            "user_email": glide_user_email
        }
        pending_url = f"{return_url}?" + "&".join([
            f"{k}={urllib.parse.quote(str(v))}" for k, v in pending_params.items()
        ])
        print(f"🔄 Spotify connection pending approval")
        return redirect(pending_url)
    
    else:
        # Error
        error_params = {
            "spotify_connected": "false",
            "connection_status": "failed",
            "error": "connection_failed"
        }
        error_url = f"{return_url}?" + "&".join([
            f"{k}={urllib.parse.quote(str(v))}" for k, v in error_params.items()
        ])
        print(f"❌ Spotify connection failed")
        return redirect(error_url)


def send_webhook_to_glide(webhook_data):
    """Helper function to send webhook data to Glide"""
    try:
        glide_webhook_url = os.environ.get("GLIDE_RETURN_WEBHOOK_URL")
        if not glide_webhook_url:
            print("⚠️ No GLIDE_RETURN_WEBHOOK_URL configured")
            return False
        
        print("📤 Sending webhook data to Glide...")
        print(f"📋 Webhook status: {webhook_data['jsonBody']['status']}")
        print(f"📋 Connection step: {webhook_data['jsonBody']['connection_step']}")
        
        webhook_response = requests.post(
            glide_webhook_url, 
            json=webhook_data, 
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"📡 Webhook response: {webhook_response.status_code}")
        if webhook_response.status_code != 200:
            print(f"📡 Response body: {webhook_response.text}")
        
        return webhook_response.status_code == 200
        
    except Exception as e:
        print(f"❌ Webhook failed: {e}")
        return False
# Also add this helper endpoint to check connection status
@app.route('/spotify_connection_status', methods=['POST'])
def spotify_connection_status():
    """Check if a user has successfully connected their Spotify account"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        spotify_user_id = data.get('spotify_user_id')  # Alternative lookup
        
        if not user_email and not spotify_user_id:
            return jsonify({
                "spotify_connected": False,
                "error": "No user identifier provided"
            }), 400
        
        # Search by email first, then by Spotify user ID
        user_data = None
        
        if user_email:
            # Search by Glide email
            users_ref = db.collection("users").where("glide_user_email", "==", user_email).limit(1)
            docs = list(users_ref.stream())
            
            if not docs:
                # Also try searching by Spotify email
                users_ref = db.collection("users").where("spotify_email", "==", user_email).limit(1)
                docs = list(users_ref.stream())
            
            if docs:
                user_data = docs[0].to_dict()
        
        elif spotify_user_id:
            # Direct lookup by Spotify user ID
            doc_ref = db.collection("users").document(spotify_user_id)
            doc = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
        
        if user_data:
            return jsonify({
                "spotify_connected": bool(user_data.get("spotify_refresh_token")),
                "spotify_user_id": user_data.get("spotify_user_id", ""),
                "spotify_display_name": user_data.get("spotify_display_name", ""),
                "spotify_email": user_data.get("spotify_email", ""),
                "connected_at": user_data.get("connected_at", ""),
                "last_token_refresh": user_data.get("last_token_refresh", ""),
                "status": "found"
            })
        else:
            return jsonify({
                "spotify_connected": False,
                "spotify_user_id": "",
                "spotify_display_name": "",
                "spotify_email": "",
                "connected_at": "",
                "status": "not_found"
            })
            
    except Exception as e:
        logger.error(f"❌ Error checking Spotify connection status: {e}")
        return jsonify({
            "spotify_connected": False,
            "error": str(e)
        }), 500

# --- Glide Social Endpoint (Build and Return) ---
@app.route('/glide_social', methods=['POST'])
def glide_social():
    data = request.get_json()
    logger.info(f"📥 Glide social data received: {json.dumps(data, indent=2)}")

    # Extract row_id more thoroughly and DO NOT generate fallback
    row_id = None
    
    # Check all possible locations for row_id
    if isinstance(data, dict):
        # Try direct keys first (including Glide's emoji-prefixed format)
        row_id = (data.get("row_id") or 
                 data.get("id") or 
                 data.get("rowID") or
                 data.get("Row ID") or
                 data.get("🔒 row_id") or
                 data.get("🔒row_id"))
        
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
    
    # Handle nested data structure if present
    body_data = data.get("body", {}) if isinstance(data.get("body"), dict) else {}
    
    # Extract parameters from both root level and body level
    genre = data.get("genre") or body_data.get("genre") or "pop"
    artist = data.get("artist") or data.get("favorite_artist") or body_data.get("artist") or body_data.get("favorite_artist")
    mood = data.get("mood") or data.get("mood_tags") or body_data.get("mood") or body_data.get("mood_tags")
    event = data.get("event") or data.get("event_name") or body_data.get("event") or body_data.get("event_name") or "My Playlist"
    
    # Safer time duration handling
    try:
        time_duration = int(data.get("time", body_data.get("time", 30)))
    except (ValueError, TypeError):
        time_duration = 30
        
    playlist_type = data.get("playlist_type", body_data.get("playlist_type", "clean"))
    birth_year = data.get("birth_year") or body_data.get("birth_year")
    search_keywords = data.get("search_keywords") or body_data.get("search_keywords")
    
    # Get webhook URL properly
    webhook_return_url = (data.get("webhook_return_url") or 
                         body_data.get("webhook_return_url") or 
                         os.environ.get("GLIDE_RETURN_WEBHOOK_URL"))

    # Log all extracted parameters for debugging
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
        # Pass the exact row_id from Glide as request_id
        playlist_result = build_smart_playlist_enhanced(
            event_name=event,
            genre=genre,
            time=time_duration,
            mood_tags=mood,
            search_keywords=search_keywords,
            favorite_artist=artist,
            user_id=user_id,
            playlist_type=playlist_type,
            request_id=row_id,
            birth_year=birth_year,
            streaming_service="spotify"
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

    # Use the exact row_id from Glide in response
    response_data = prepare_response_data(
        row_id=row_id,
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

# --- Test Endpoints ---
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

# --- Firebase Test Endpoints ---
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

# ML analysis endpoints
@app.route('/trigger_ml_analysis', methods=['POST'])
def trigger_ml_analysis():
    """Manually trigger ML analysis for testing"""
    try:
        logger.info("🤖 Manual ML analysis triggered")
        ml_engine = MLReengagementEngine()
        result = ml_engine.run_weekly_analysis()
        
        return jsonify({
            "status": "success",
            "analysis_result": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ ML analysis failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/user_recommendations/<user_id>', methods=['GET'])
def get_user_recommendations(user_id):
    """Get pending recommendations for a user"""
    try:
        recommendations_ref = db.collection("weekly_recommendations") \
            .where("user_id", "==", user_id) \
            .where("status", "==", "pending") \
            .order_by("created_at", direction=firestore.Query.DESCENDING) \
            .limit(5)
        
        recommendations = []
        for doc in recommendations_ref.stream():
            rec_data = doc.to_dict()
            rec_data["id"] = doc.id
            recommendations.append(rec_data)
        
        return jsonify({
            "status": "success",
            "recommendations": recommendations,
            "count": len(recommendations)
        })
        
    except Exception as e:
        logger.error(f"❌ Get recommendations failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/mark_recommendation_read/<recommendation_id>', methods=['POST'])
def mark_recommendation_read(recommendation_id):
    """Mark a recommendation as read"""
    try:
        db.collection("weekly_recommendations").document(recommendation_id).update({
            "status": "read",
            "read_at": datetime.now().isoformat()
        })
        
        return jsonify({
            "status": "success",
            "message": "Recommendation marked as read"
        })
        
    except Exception as e:
        logger.error(f"❌ Mark recommendation read failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/ml_stats', methods=['GET'])
def get_ml_stats():
    """Get ML system statistics"""
    try:
        # Get cache stats
        cache_ref = db.collection("track_cache")
        total_cached = len(list(cache_ref.stream()))
        
        # Get recent analysis
        analysis_ref = db.collection("ml_analysis").order_by("analysis_date", direction=firestore.Query.DESCENDING).limit(1)
        latest_analysis = None
        for doc in analysis_ref.stream():
            latest_analysis = doc.to_dict()
            break
        
        # Get pending notifications
        pending_notifications = len(list(
            db.collection("weekly_recommendations")
            .where("status", "==", "pending")
            .stream()
        ))
        
        return jsonify({
            "status": "success",
            "stats": {
                "total_cached_tracks": total_cached,
                "latest_analysis_date": latest_analysis.get("analysis_date") if latest_analysis else None,
                "pending_notifications": pending_notifications,
                "ml_system_active": True
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Get ML stats failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# --- NEW DEBUG ENDPOINTS FOR SPOTIFY OAUTH ---
@app.route('/debug_spotify_config', methods=['GET'])
def debug_spotify_config():
    """Debug Spotify configuration"""
    config = {
        "client_id": os.getenv("SPOTIFY_CLIENT_ID")[:10] + "..." if os.getenv("SPOTIFY_CLIENT_ID") else "MISSING",
        "client_secret": "PRESENT" if os.getenv("SPOTIFY_CLIENT_SECRET") else "MISSING",
        "refresh_token": "PRESENT" if os.getenv("SPOTIFY_REFRESH_TOKEN") else "MISSING",
        "redirect_uri": os.getenv("SPOTIFY_REDIRECT_URI"),
        "environment": "RAILWAY" if os.getenv("RAILWAY_ENVIRONMENT") else "LOCAL"
    }
    
    return jsonify({
        "status": "debug",
        "config": config,
        "missing_vars": [k for k, v in config.items() if v in ["MISSING", None]]
    })

@app.route('/test_spotify_auth', methods=['GET'])
def test_spotify_auth():
    """Generate Spotify authorization URL for testing"""
    try:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        if not client_id or not redirect_uri:
            return jsonify({
                "error": "Missing SPOTIFY_CLIENT_ID or SPOTIFY_REDIRECT_URI"
            }), 500
        
        # Test scopes
        scopes = [
            "playlist-modify-private",
            "playlist-modify-public", 
            "user-read-private",
            "user-read-email",
            "user-top-read",
            "user-library-read",
            "user-read-recently-played"
        ]
        
        # Create state with test data
        state_params = {
            "user_email": "test@example.com",
            "return_url": "https://moodque.glide.page",
            "test": "true"
        }
        
        state = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in state_params.items()])
        
        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "scope": " ".join(scopes),
            "redirect_uri": redirect_uri,
            "state": state,
            "show_dialog": "true"  # Force consent screen for testing
        }
        
        auth_url = "https://accounts.spotify.com/authorize?" + "&".join([
            f"{k}={urllib.parse.quote(str(v))}" for k, v in auth_params.items()
        ])
        
        return jsonify({
            "status": "success",
            "auth_url": auth_url,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "instructions": "Click the auth_url to test Spotify OAuth flow"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/test_callback_simulation', methods=['POST'])
def test_callback_simulation():
    """Simulate callback with test data to debug processing"""
    try:
        data = request.get_json() or {}
        
        # Simulate callback data
        test_profile = {
            "id": "test_spotify_user_123",
            "display_name": "Test User",
            "email": "test@spotify.com",
            "country": "US",
            "product": "premium",
            "followers": {"total": 10},
            "images": []
        }
        
        test_token_data = {
            "access_token": "test_access_token_123",
            "refresh_token": "test_refresh_token_123", 
            "expires_in": 3600
        }
        
        # Use the same logic as real callback
        spotify_user_id = test_profile["id"]
        connection_timestamp = datetime.now().isoformat()
        glide_user_email = data.get("user_email", "test@example.com")
        
        user_doc = {
            "spotify_user_id": spotify_user_id,
            "spotify_display_name": test_profile["display_name"],
            "spotify_email": test_profile["email"],
            "spotify_access_token": test_token_data["access_token"],
            "spotify_refresh_token": test_token_data["refresh_token"],
            "spotify_token_expires_at": str(int(time.time()) + test_token_data["expires_in"]),
            "spotify_connected": True,
            "glide_user_email": glide_user_email,
            "connected_at": connection_timestamp,
            "connection_method": "test_simulation"
        }
        
        # Save to Firebase
        db.collection("users").document(spotify_user_id).set(user_doc, merge=True)
        
        return jsonify({
            "status": "success",
            "message": "Test connection simulation successful",
            "user_doc": user_doc,
            "spotify_user_id": spotify_user_id
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/list_connected_users', methods=['GET'])
def list_connected_users():
    """List all users who have connected Spotify"""
    try:
        users_ref = db.collection("users").where("spotify_connected", "==", True).limit(10)
        connected_users = []
        
        for doc in users_ref.stream():
            user_data = doc.to_dict()
            connected_users.append({
                "doc_id": doc.id,
                "spotify_user_id": user_data.get("spotify_user_id"),
                "spotify_display_name": user_data.get("spotify_display_name"),
                "glide_user_email": user_data.get("glide_user_email"),
                "connected_at": user_data.get("connected_at"),
                "has_refresh_token": bool(user_data.get("spotify_refresh_token"))
            })
        
        return jsonify({
            "status": "success",
            "connected_users_count": len(connected_users),
            "connected_users": connected_users
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/cleanup_test_users', methods=['POST'])
def cleanup_test_users():
    """Clean up test users from database"""
    try:
        # Find test users
        users_ref = db.collection("users")
        
        # Look for test users by various criteria
        test_criteria = [
            ("connection_method", "==", "test_simulation"),
            ("glide_user_email", "==", "test@example.com"),
            ("spotify_user_id", "==", "test_spotify_user_123")
        ]
        
        deleted_count = 0
        
        for field, op, value in test_criteria:
            query = users_ref.where(field, op, value)
            for doc in query.stream():
                doc.reference.delete()
                deleted_count += 1
                print(f"🗑️ Deleted test user: {doc.id}")
        
        return jsonify({
            "status": "success",
            "message": f"Cleaned up {deleted_count} test users"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

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

@app.route('/spotify_connect', methods=['POST', 'GET'])
def spotify_connect():
    """
    Endpoint for Glide to initiate Spotify OAuth with proper state parameters
    FIXED: Ensures row_id and user_email are properly passed through the OAuth flow
    """
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            user_email = data.get('user_email') or data.get('email', '')
            row_id = data.get('row_id') or data.get('id', '') or data.get('🔒 row_id', '')  # Check multiple row_id formats
            return_url = data.get('return_url', 'https://moodque.glide.page')
        else:
            # GET request with query parameters
            user_email = request.args.get('user_email') or request.args.get('email', '')
            row_id = request.args.get('row_id') or request.args.get('id', '') or request.args.get('🔒 row_id', '')
            return_url = request.args.get('return_url', 'https://moodque.glide.page')
        
        # Debug logging to see what we received
        print(f"🔗 Spotify connect request received:")
        print(f"   Method: {request.method}")
        print(f"   User email: '{user_email}'")
        print(f"   Row ID: '{row_id}'")
        print(f"   Return URL: '{return_url}'")
        
        if request.method == 'POST':
            print(f"   POST data keys: {list(data.keys()) if data else 'No data'}")
            print(f"   POST data: {json.dumps(data, indent=2) if data else 'No data'}")
        else:
            print(f"   GET args: {dict(request.args)}")
        
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        if not client_id or not redirect_uri:
            print("❌ Missing Spotify OAuth configuration")
            print(f"   SPOTIFY_CLIENT_ID: {'Present' if client_id else 'Missing'}")
            print(f"   SPOTIFY_REDIRECT_URI: {redirect_uri}")
            return jsonify({
                "error": "Missing Spotify configuration",
                "status": "error"
            }), 500
        
        # CRITICAL: Always include state parameters even if empty
        # This ensures we can track the request even without user info
        state_params = {
            'return_url': return_url,
            'timestamp': str(int(time.time()))  # Add timestamp for uniqueness
        }
        
        # Add user info if available
        if user_email:
            state_params['user_email'] = user_email
            print(f"✅ Added user_email to state: {user_email}")
        else:
            print("⚠️ No user_email provided - will be 'unknown' in callback")
        
        if row_id:
            state_params['row_id'] = row_id
            print(f"✅ Added row_id to state: {row_id}")
        else:
            print("⚠️ No row_id provided - will be 'unknown' in callback")
        
        # Encode state as URL parameters
        state = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in state_params.items()])
        print(f"🔗 Encoded state: {state}")
        
        # Spotify OAuth scopes
        scopes = [
            "user-read-private",      # Required for /me endpoint
            "user-read-email",        # Required for email access
            "playlist-modify-private", # For creating private playlists
            "playlist-modify-public",  # For creating public playlists
            "user-top-read",          # For top artists/tracks
            "user-library-read",      # For saved tracks
            "user-read-recently-played"  # For recent playback
        ]
        
        # Build OAuth URL with proper parameter encoding
        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "scope": " ".join(scopes),  # Space-separated scopes
            "redirect_uri": redirect_uri,
            "show_dialog": "true",  # Force consent screen
            "state": state  # Always include state
        }
        
        # Properly encode all parameters
        auth_url = "https://accounts.spotify.com/authorize?" + "&".join([
            f"{k}={urllib.parse.quote(str(v))}" for k, v in auth_params.items()
        ])
        
        print(f"🔗 Generated Spotify OAuth URL:")
        print(f"   Scopes: {', '.join(scopes)}")
        print(f"   Redirect URI: {redirect_uri}")
        print(f"   State parameters: {state_params}")
        print(f"   Full OAuth URL: {auth_url}")
        
        if request.method == 'POST':
            return jsonify({
                "status": "success",
                "auth_url": auth_url,
                "user_email": user_email,
                "row_id": row_id,
                "state_params": state_params,
                "scopes": scopes,
                "message": "Redirect user to auth_url to connect Spotify",
                "debug_info": {
                    "received_data": data,
                    "state_encoded": state
                }
            })
        else:
            return redirect(auth_url)
            
    except Exception as e:
        logger.error(f"❌ Error in spotify_connect: {e}")
        import traceback
        traceback.print_exc()
        
        if request.method == 'POST':
            return jsonify({
                "status": "error",
                "error": str(e),
                "debug_info": {
                    "request_method": request.method,
                    "request_data": request.get_json() if request.method == 'POST' else dict(request.args)
                }
            }), 500
        else:
            error_url = f"{return_url}?spotify_error=connection_failed"
            return redirect(error_url)
     
@app.route('/admin/pending_users', methods=['GET'])
def get_pending_users():
    """Get all users pending Spotify Developer Dashboard approval"""
    try:
        pending_users = []
        docs = db.collection("pending_users").stream()
        
        for doc in docs:
            user_data = doc.to_dict()
            user_data["doc_id"] = doc.id
            
            # Calculate how long they've been pending
            requested_at = user_data.get("requested_at", "")
            if requested_at:
                try:
                    from datetime import datetime
                    req_time = datetime.fromisoformat(requested_at.replace('Z', '+00:00'))
                    now = datetime.now()
                    pending_hours = (now - req_time).total_seconds() / 3600
                    user_data["pending_hours"] = round(pending_hours, 1)
                except:
                    user_data["pending_hours"] = "unknown"
            
            pending_users.append(user_data)
        
        # Sort by most recent first
        pending_users.sort(key=lambda x: x.get("requested_at", ""), reverse=True)
        
        return jsonify({
            "status": "success",
            "pending_users_count": len(pending_users),
            "pending_users": pending_users,
            "instructions": {
                "step1": "Go to https://developer.spotify.com/dashboard",
                "step2": "Select your moodQue app",
                "step3": "Go to User Management",
                "step4": "Add each email from the list below",
                "step5": "Use /admin/approve_user/{email} to mark as approved"
            }
        })
        
    except Exception as e:
        print(f"❌ Error getting pending users: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/admin/approve_user/<user_email>', methods=['POST'])
def approve_pending_user(user_email):
    """Mark a user as approved and attempt to complete their Spotify connection"""
    try:
        print(f"🔄 Approving user: {user_email}")
        
        # Find the pending user
        pending_docs = db.collection("pending_users").where("glide_user_email", "==", user_email).stream()
        pending_user = None
        pending_doc_id = None
        
        for doc in pending_docs:
            pending_user = doc.to_dict()
            pending_doc_id = doc.id
            break
        
        if not pending_user:
            return jsonify({
                "status": "error",
                "message": f"No pending user found for email: {user_email}"
            }), 404
        
        # Try to fetch their profile now that they should be approved
        access_token = pending_user.get("access_token")
        if not access_token:
            return jsonify({
                "status": "error", 
                "message": "No access token stored for this user"
            }), 400
        
        print(f"🔄 Testing profile access for {user_email}")
        profile_resp = requests.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        
        if profile_resp.status_code == 200:
            # SUCCESS! User is now approved
            user_profile = profile_resp.json()
            spotify_user_id = user_profile.get("id")
            
            print(f"✅ Profile access successful for {spotify_user_id}")
            
            # Create full user record
            connection_timestamp = datetime.now().isoformat()
            user_doc = {
                "spotify_user_id": spotify_user_id,
                "spotify_display_name": user_profile.get("display_name", ""),
                "spotify_email": user_profile.get("email", ""),
                "spotify_access_token": access_token,
                "spotify_refresh_token": pending_user.get("refresh_token", ""),
                "spotify_token_expires_at": pending_user.get("token_expires_at", ""),
                "spotify_token_scope": pending_user.get("token_scope", ""),
                "spotify_connected": True,
                "spotify_country": user_profile.get("country", ""),
                "spotify_product": user_profile.get("product", ""),
                "spotify_followers": user_profile.get("followers", {}).get("total", 0),
                "spotify_images": user_profile.get("images", []),
                "spotify_avatar_url": user_profile.get("images", [{}])[0].get("url", "") if user_profile.get("images") else "",
                "glide_user_email": pending_user.get("glide_user_email", ""),
                "glide_row_id": pending_user.get("glide_row_id", ""),
                "connected_at": connection_timestamp,
                "approved_at": connection_timestamp,
                "last_token_refresh": pending_user.get("requested_at", connection_timestamp),
                "connection_method": "oauth_callback_approved",
                "connection_source": "moodque_app"
            }
            
            # Save to users collection
            db.collection("users").document(spotify_user_id).set(user_doc, merge=True)
            
            # Send updated webhook to Glide
            webhook_data = {
                "jsonBody": {
                    "row_id": pending_user.get("glide_row_id", spotify_user_id),
                    "status": "connected",
                    "user_id": spotify_user_id,
                    "has_code": "true",
                    "created_at": connection_timestamp,
                    "like_count": 0,
                    "play_count": 0,
                    "playlist_id": "",
                    "shared_count": 0,
                    "spotify_url": f"https://open.spotify.com/user/{spotify_user_id}",
                    "spotify_connected": True,
                    "spotify_user_id": spotify_user_id,
                    "spotify_display_name": user_profile.get("display_name", ""),
                    "spotify_connected_at": connection_timestamp,
                    "spotify_avatar_url": user_profile.get("images", [{}])[0].get("url", "") if user_profile.get("images") else "",
                    "spotify_email": user_profile.get("email", ""),
                    "spotify_country": user_profile.get("country", ""),
                    "spotify_product": user_profile.get("product", ""),
                    "spotify_followers": user_profile.get("followers", {}).get("total", 0),
                    "glide_user_email": pending_user.get("glide_user_email", ""),
                    "pending_approval": False,
                    "approved_by_admin": True
                }
            }
            
            webhook_sent = send_webhook_to_glide(webhook_data)
            
            # Remove from pending users
            db.collection("pending_users").document(pending_doc_id).delete()
            
            return jsonify({
                "status": "success",
                "message": f"User {user_email} successfully approved and connected",
                "spotify_user_id": spotify_user_id,
                "spotify_display_name": user_profile.get("display_name", ""),
                "webhook_sent": webhook_sent
            })
            
        else:
            # Still not approved
            return jsonify({
                "status": "pending",
                "message": f"User {user_email} still needs to be added to Spotify Developer Dashboard",
                "spotify_response_code": profile_resp.status_code,
                "instructions": "Add this user to your Spotify app's User Management section, then try again"
            })
            
    except Exception as e:
        print(f"❌ Error approving user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/admin/retry_all_pending', methods=['POST'])
def retry_all_pending_users():
    """Retry approval for all pending users (useful after adding multiple users to Spotify Dashboard)"""
    try:
        pending_docs = list(db.collection("pending_users").stream())
        
        results = {
            "total_pending": len(pending_docs),
            "approved": [],
            "still_pending": [],
            "errors": []
        }
        
        for doc in pending_docs:
            pending_user = doc.to_dict()
            user_email = pending_user.get("glide_user_email", "unknown")
            
            try:
                # Test profile access
                access_token = pending_user.get("access_token")
                if not access_token:
                    results["errors"].append({"email": user_email, "error": "No access token"})
                    continue
                
                profile_resp = requests.get(
                    "https://api.spotify.com/v1/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5
                )
                
                if profile_resp.status_code == 200:
                    # User is now approved - process them
                    user_profile = profile_resp.json()
                    spotify_user_id = user_profile.get("id")
                    
                    # Create user record (similar to approve_pending_user)
                    connection_timestamp = datetime.now().isoformat()
                    user_doc = {
                        "spotify_user_id": spotify_user_id,
                        "spotify_display_name": user_profile.get("display_name", ""),
                        "spotify_email": user_profile.get("email", ""),
                        "spotify_access_token": access_token,
                        "spotify_refresh_token": pending_user.get("refresh_token", ""),
                        "spotify_connected": True,
                        "glide_user_email": user_email,
                        "connected_at": connection_timestamp,
                        "approved_at": connection_timestamp,
                        "connection_method": "batch_approved"
                    }
                    
                    db.collection("users").document(spotify_user_id).set(user_doc, merge=True)
                    db.collection("pending_users").document(doc.id).delete()
                    
                    results["approved"].append({
                        "email": user_email,
                        "spotify_user_id": spotify_user_id,
                        "display_name": user_profile.get("display_name", "")
                    })
                    
                else:
                    results["still_pending"].append({"email": user_email, "status_code": profile_resp.status_code})
                    
            except Exception as e:
                results["errors"].append({"email": user_email, "error": str(e)})
        
        return jsonify({
            "status": "success",
            "results": results,
            "message": f"Processed {len(pending_docs)} pending users. {len(results['approved'])} approved, {len(results['still_pending'])} still pending."
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Get overall stats for admin dashboard"""
    try:
        # Count connected users
        connected_users = list(db.collection("users").where("spotify_connected", "==", True).stream())
        
        # Count pending users
        pending_users = list(db.collection("pending_users").stream())
        
        # Recent activity
        recent_interactions = list(db.collection("interactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream())
        
        return jsonify({
            "status": "success",
            "stats": {
                "connected_users": len(connected_users),
                "pending_users": len(pending_users),
                "total_users": len(connected_users) + len(pending_users),
                "recent_interactions": len(recent_interactions)
            },
            "spotify_dev_mode_limit": 25,
            "users_remaining_in_dev_mode": max(0, 25 - len(connected_users))
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500   
        
# Add this test endpoint to help debug the flow

@app.route('/test_spotify_flow', methods=['POST', 'GET'])
def test_spotify_flow():
    """
    Test endpoint to simulate the proper Glide -> Spotify flow with row_id
    Use this to test before connecting from Glide
    """
    try:
        if request.method == 'GET':
            # Return a test form
            test_form = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Test Spotify Connection Flow</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .form-group { margin: 15px 0; }
                    label { display: block; margin-bottom: 5px; font-weight: bold; }
                    input { padding: 8px; width: 300px; border: 1px solid #ccc; }
                    button { padding: 10px 20px; background: #1db954; color: white; border: none; cursor: pointer; }
                    .info { background: #f0f8ff; padding: 15px; margin: 20px 0; border-left: 4px solid #1db954; }
                </style>
            </head>
            <body>
                <h1>🎵 Test MoodQue Spotify Connection</h1>
                
                <div class="info">
                    <h3>Instructions:</h3>
                    <p>1. Fill out the form below with test data</p>
                    <p>2. Click "Test Spotify Connection"</p>
                    <p>3. Complete the Spotify OAuth flow</p>
                    <p>4. Check your webhook data for the correct row_id</p>
                </div>
                
                <form method="POST">
                    <div class="form-group">
                        <label>Row ID (from Glide):</label>
                        <input type="text" name="row_id" value="test_row_123" placeholder="Enter row ID from Glide">
                    </div>
                    
                    <div class="form-group">
                        <label>User Email:</label>
                        <input type="email" name="user_email" value="test@example.com" placeholder="Enter user email">
                    </div>
                    
                    <div class="form-group">
                        <label>Return URL:</label>
                        <input type="text" name="return_url" value="https://moodque.glide.page" placeholder="Where to redirect after connection">
                    </div>
                    
                    <button type="submit">🎵 Test Spotify Connection</button>
                </form>
                
                <div class="info">
                    <h3>What This Tests:</h3>
                    <p>• Row ID passing through OAuth state</p>
                    <p>• User email preservation</p>
                    <p>• Webhook data structure</p>
                    <p>• Pending approval flow (if user not in Spotify dev dashboard)</p>
                </div>
            </body>
            </html>
            """
            return test_form
        
        else:
            # POST request - simulate Glide calling /spotify_connect
            form_data = request.form
            
            test_data = {
                "row_id": form_data.get("row_id", "test_row_123"),
                "user_email": form_data.get("user_email", "test@example.com"), 
                "return_url": form_data.get("return_url", "https://moodque.glide.page")
            }
            
            print(f"🧪 Test Spotify flow initiated:")
            print(f"   Row ID: {test_data['row_id']}")
            print(f"   User Email: {test_data['user_email']}")
            print(f"   Return URL: {test_data['return_url']}")
            
            # Call the spotify_connect endpoint with test data
            with app.test_client() as client:
                response = client.post('/spotify_connect', 
                                     json=test_data, 
                                     content_type='application/json')
                
                if response.status_code == 200:
                    response_data = response.get_json()
                    auth_url = response_data.get('auth_url')
                    
                    if auth_url:
                        print(f"✅ Test OAuth URL generated successfully")
                        return redirect(auth_url)
                    else:
                        return jsonify({
                            "status": "error",
                            "message": "No auth URL generated",
                            "response": response_data
                        }), 500
                else:
                    return jsonify({
                        "status": "error",
                        "message": f"spotify_connect failed with status {response.status_code}",
                        "response": response.get_data(as_text=True)
                    }), 500
        
    except Exception as e:
        print(f"❌ Test flow error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/debug_state_parsing', methods=['GET'])
def debug_state_parsing():
    """Debug endpoint to test state parameter parsing"""
    
    # Test various state formats
    test_states = [
        "return_url=https%3A//moodque.glide.page",
        "user_email=test@example.com&row_id=test123&return_url=https%3A//moodque.glide.page",
        "user_email=jinneric@gmail.com&row_id=abc123&return_url=https%253A%252F%252Fmoodque.glide.page"
    ]
    
    results = []
    
    for state in test_states:
        print(f"🔍 Testing state: {state}")
        
        # Parse state parameters
        state_params = {}
        if state:
            try:
                for param in state.split("&"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        state_params[key] = urllib.parse.unquote(value)
            except Exception as e:
                print(f"❌ Error parsing state: {e}")
        
        results.append({
            "input_state": state,
            "parsed_params": state_params,
            "row_id": state_params.get("row_id", "NOT_FOUND"),
            "user_email": state_params.get("user_email", "NOT_FOUND"),
            "return_url": state_params.get("return_url", "NOT_FOUND")
        })
        
        print(f"   Parsed: {state_params}")
    
    return jsonify({
        "status": "success",
        "test_results": results,
        "message": "This shows how different state formats are parsed"
    })    
    
# Add this endpoint to your moodQueSocial_webhook_service.py

@app.route('/spotify_connect_and_redirect', methods=['POST'])
def spotify_connect_and_redirect():
    """
    Single endpoint for Glide to call that generates OAuth URL with proper state
    This ensures row_id and user_email are properly passed through the flow
    """
    try:
        data = request.get_json() or {}
        user_email = data.get('user_email', '')
        row_id = data.get('row_id', '')
        return_url = data.get('return_url', 'https://moodque.glide.page')
        
        print(f"🔗 Direct Spotify connect request:")
        print(f"   Row ID: '{row_id}'")
        print(f"   User Email: '{user_email}'")
        print(f"   Return URL: '{return_url}'")
        print(f"   Full request data: {json.dumps(data, indent=2)}")
        
        # Validate we have required data
        if not row_id:
            print("⚠️ Warning: No row_id provided")
        if not user_email:
            print("⚠️ Warning: No user_email provided")
        
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        if not client_id or not redirect_uri:
            print("❌ Missing Spotify configuration")
            return jsonify({
                "status": "error",
                "error": "Missing Spotify configuration"
            }), 500
        
        # Create state parameters with all data
        state_params = {
            'return_url': return_url,
            'timestamp': str(int(time.time()))
        }
        
        # Add user data to state
        if user_email:
            state_params['user_email'] = user_email
        if row_id:
            state_params['row_id'] = row_id
        
        # Encode state
        state = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in state_params.items()])
        
        print(f"🔗 State parameters: {state_params}")
        print(f"🔗 Encoded state: {state}")
        
        # Spotify OAuth scopes
        scopes = [
            "user-read-private",
            "user-read-email", 
            "playlist-modify-private",
            "playlist-modify-public",
            "user-top-read",
            "user-library-read",
            "user-read-recently-played"
        ]
        
        # Build OAuth URL
        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "scope": " ".join(scopes),
            "redirect_uri": redirect_uri,
            "show_dialog": "true",
            "state": state
        }
        
        auth_url = "https://accounts.spotify.com/authorize?" + "&".join([
            f"{k}={urllib.parse.quote(str(v))}" for k, v in auth_params.items()
        ])
        
        print(f"🔗 Generated OAuth URL: {auth_url}")
        
        # Return response that Glide can use to redirect
        return jsonify({
            "status": "success",
            "action": "redirect",
            "url": auth_url,
            "auth_url": auth_url,  # Alternative field name
            "redirect_url": auth_url,  # Another alternative
            "message": "Redirecting to Spotify authentication...",
            "debug_info": {
                "row_id_received": row_id,
                "user_email_received": user_email,
                "state_params": state_params
            }
        })
        
    except Exception as e:
        print(f"❌ Error in spotify_connect_and_redirect: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "status": "error",
            "error": str(e),
            "debug_info": {
                "request_data": data if 'data' in locals() else "N/A"
            }
        }), 500

# Also add a simple test endpoint to verify Glide can reach your service
@app.route('/test_glide_connection', methods=['POST'])
def test_glide_connection():
    """Simple endpoint to test Glide -> Backend connectivity"""
    try:
        data = request.get_json() or {}
        
        print(f"🧪 Test connection from Glide:")
        print(f"   Headers: {dict(request.headers)}")
        print(f"   Data: {json.dumps(data, indent=2)}")
        
        return jsonify({
            "status": "success",
            "message": "Connection successful!",
            "received_data": data,
            "timestamp": datetime.now().isoformat(),
            "backend_status": "operational"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500             

if __name__ == '__main__':
    app.run(debug=True)