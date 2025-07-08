import logging
from flask import Flask, request, jsonify
from moodque_engine import build_smart_playlist_enhanced  # Adjust path if needed
import requests
import os
from datetime import datetime
import json

# --- Flask App Setup ---
app = Flask(__name__)
logger = logging.getLogger("moodQueSocial_webhook")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Constants ---
# Removed GLIDE_RETURN_WEBHOOK_URL since we're using direct response

# --- Helper Function: Prepare Response Data ---
def prepare_response_data(row_id, playlist_info, user_id=None, processing_time_start=None):
    """Prepare response data for direct return to Glide"""
    
    # Calculate processing time
    processing_duration = None
    if processing_time_start:
        processing_duration = round((datetime.now() - processing_time_start).total_seconds(), 2)

    # Prepare enhanced response data
    if playlist_info and isinstance(playlist_info, str):
        # If playlist_info is just a URL string (successful creation)
        playlist_id = playlist_info.split('/')[-1] if '/' in playlist_info else ""
        response_data = {
            "row_id": row_id,
            "user_id": user_id or "unknown",
            "has_code": "true",
            "playlist_id": playlist_id,
            "spotify_url": playlist_info,
            "track_count": "0",  # Will be updated with actual count later
            "spotify_code_url": f"https://scannables.scdn.co/uri/plain/jpeg/black/white/640/spotify:playlist:{playlist_id}",
            "status": "completed",
            "error_message": "",
            "processing_time_seconds": processing_duration,
            "created_at": datetime.now().isoformat(),
            "play_count": 0,  # Initialize social metrics
            "like_count": 0,
            "share_count": 0
        }
    elif playlist_info and isinstance(playlist_info, dict):
        # If playlist_info is a dictionary with details
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
        # If playlist creation failed
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


# --- Main Playlist Trigger Route ---
@app.route("/glide_social", methods=["POST"])
def glide_social():
    """Handle incoming playlist build requests from Glide with enhanced logging and error handling"""
    request_start_time = datetime.now()
    request_id = f"req_{int(request_start_time.timestamp())}"
    
    try:
        # Log request details
        logger.info(f"🎯 [{request_id}] New playlist request received")
        logger.info(f"🔍 [{request_id}] Request headers: {dict(request.headers)}")
        
        # Parse payload with enhanced error handling
        try:
            payload = request.get_json(force=True)
            logger.info(f"📨 [{request_id}] Raw payload received: {json.dumps(payload, indent=2)}")
        except Exception as parse_error:
            logger.error(f"❌ [{request_id}] Failed to parse JSON payload: {parse_error}")
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        # Handle both payload formats (with or without "body" wrapper)
        if "body" in payload:
            # New format with "body" wrapper
            body = payload.get("body", {})
            logger.info(f"📝 [{request_id}] Using body wrapper format")
        else:
            # Old format without wrapper
            body = payload
            logger.info(f"📝 [{request_id}] Using direct format")

        # Extract required fields with detailed logging
        row_id = body.get("row_id")
        event_name = body.get("event_name", "").strip()
        genre = body.get("genre", "").strip()
        mood_tags = body.get("mood_tags", "").strip()
        favorite_artist = body.get("favorite_artist", "").strip()
        search_keywords = body.get("search_keywords", "").strip()
        time = body.get("time", 30)
        playlist_type = body.get("playlist_type", "clean")
        user_id = body.get("user_id", body.get("creator_email", "unknown"))

        logger.info(f"🎯 [{request_id}] Extracted fields:")
        logger.info(f"   📍 Row ID: {row_id}")
        logger.info(f"   🎪 Event Name: {event_name}")
        logger.info(f"   🎵 Genre: {genre}")
        logger.info(f"   😊 Mood Tags: {mood_tags}")
        logger.info(f"   🌟 Favorite Artist: {favorite_artist}")
        logger.info(f"   🔍 Search Keywords: {search_keywords}")
        logger.info(f"   ⏰ Duration: {time} minutes")
        logger.info(f"   🚫 Content Filter: {playlist_type}")
        logger.info(f"   👤 User ID: {user_id}")

        # Validate required fields
        if not row_id:
            logger.error(f"❌ [{request_id}] Missing row_id - this is required for return webhook")
            return jsonify({"status": "error", "message": "Missing row_id"}), 400

        missing_fields = []
        if not event_name:
            missing_fields.append("event_name")
        if not genre:
            missing_fields.append("genre")
        if not mood_tags:
            missing_fields.append("mood_tags")
        if not favorite_artist:
            missing_fields.append("favorite_artist")

        if missing_fields:
            logger.warning(f"⚠️ [{request_id}] Missing required fields: {missing_fields}")
            
            # Prepare failed response with detailed error
            error_message = f"Missing required fields: {', '.join(missing_fields)}"
            response_data = prepare_response_data(row_id, None, user_id, request_start_time)
            response_data["error_message"] = error_message
            
            return jsonify(response_data), 400

        # Build the playlist with enhanced logging
        logger.info(f"🎵 [{request_id}] Starting playlist build...")
        playlist_build_start = datetime.now()
        
        try:
            playlist_result = build_smart_playlist_enhanced(
                event_name=event_name,           # playlist name
                genre=genre,                     # genre
                time=time,                       # duration in minutes
                mood_tags=mood_tags,             # mood
                search_keywords=search_keywords, # keywords
                playlist_type=playlist_type,     # clean/explicit
                favorite_artist=favorite_artist, # artist
                request_id=request_id           # for logging
            )
            
            playlist_build_duration = (datetime.now() - playlist_build_start).total_seconds()
            logger.info(f"🎵 [{request_id}] Playlist build completed in {playlist_build_duration:.2f}s")
            logger.info(f"🎵 [{request_id}] Playlist result: {playlist_result}")
            
            # Return successful response with playlist data
            if playlist_result:
                response_data = prepare_response_data(row_id, playlist_result, user_id, request_start_time)
                
                # Log success metrics
                total_duration = (datetime.now() - request_start_time).total_seconds()
                logger.info(f"📊 [{request_id}] Total request duration: {total_duration:.2f}s")
                logger.info(f"✅ [{request_id}] Returning successful response to Glide")
                
                return jsonify(response_data), 200
            else:
                logger.warning(f"⚠️ [{request_id}] Playlist creation returned no data")
                response_data = prepare_response_data(row_id, None, user_id, request_start_time)
                response_data["error_message"] = "Playlist creation failed - no data returned"
                
                return jsonify(response_data), 500

        except Exception as playlist_error:
            logger.error(f"❌ [{request_id}] Playlist build failed: {playlist_error}", exc_info=True)
            
            # Return failure response with error details
            response_data = prepare_response_data(row_id, None, user_id, request_start_time)
            response_data["error_message"] = f"Playlist build failed: {str(playlist_error)}"
            
            return jsonify(response_data), 500

    except Exception as e:
        logger.error(f"❌ [{request_id}] Critical exception in glide_social: {e}", exc_info=True)
        
        # Return error response even for critical failures
        try:
            error_response = {
                "row_id": request.get_json().get("body", {}).get("row_id", "unknown") if request.get_json() else "unknown",
                "status": "failed",
                "error_message": "Internal server error",
                "has_code": "false",
                "playlist_id": "",
                "spotify_url": "",
                "created_at": datetime.now().isoformat()
            }
            return jsonify(error_response), 500
        except:
            # Absolute fallback
            return jsonify({
                "status": "failed",
                "error_message": "Critical server error",
                "has_code": "false"
            }), 500


# --- Social Metrics Tracking Routes ---
@app.route("/track_play", methods=["POST"])
def track_play():
    """Track playlist play events for social metrics"""
    try:
        data = request.get_json()
        playlist_id = data.get("playlist_id")
        user_id = data.get("user_id")
        
        logger.info(f"🎧 Play tracked - Playlist: {playlist_id}, User: {user_id}")
        
        # Here you can add logic to update play counts in your database
        # For now, we'll just log it
        
        return jsonify({"status": "play_tracked"}), 200
        
    except Exception as e:
        logger.error(f"❌ Error tracking play: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/track_like", methods=["POST"])
def track_like():
    """Track playlist like events for social metrics"""
    try:
        data = request.get_json()
        playlist_id = data.get("playlist_id")
        user_id = data.get("user_id")
        action = data.get("action", "like")  # like or unlike
        
        logger.info(f"❤️ Like tracked - Playlist: {playlist_id}, User: {user_id}, Action: {action}")
        
        # Here you can add logic to update like counts in your database
        
        return jsonify({"status": "like_tracked", "action": action}), 200
        
    except Exception as e:
        logger.error(f"❌ Error tracking like: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- Health Check Route ---
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint with enhanced diagnostics"""
    try:
        return jsonify({
            "status": "healthy", 
            "service": "moodQueSocial_webhook",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0",
            "features": ["playlist_creation", "social_metrics", "enhanced_logging"]
        }), 200
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# --- Test Route ---
@app.route("/test", methods=["GET", "POST"])
def test_endpoint():
    """Test endpoint to verify webhook is working"""
    if request.method == "POST":
        data = request.get_json()
        logger.info(f"🧪 Test POST data: {json.dumps(data, indent=2)}")
        return jsonify({
            "status": "test_success", 
            "received": data,
            "timestamp": datetime.now().isoformat()
        }), 200
    else:
        return jsonify({
            "status": "test_success", 
            "method": "GET",
            "timestamp": datetime.now().isoformat(),
            "message": "Webhook service is running"
        }), 200


if __name__ == "__main__":
    # For local testing
    logger.info("🚀 Starting moodQueSocial webhook service...")
    app.run(debug=True, host="0.0.0.0", port=5000)