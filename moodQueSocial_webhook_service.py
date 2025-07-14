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
        logger.info(f"🎯 [{request_id}] New playlist request received")
        logger.info(f"🔍 [{request_id}] Request headers: {dict(request.headers)}")

        try:
            payload = request.get_json(force=True)
            logger.info(f"📨 [{request_id}] Raw payload received: {json.dumps(payload, indent=2)}")
        except Exception as parse_error:
            logger.error(f"❌ [{request_id}] Failed to parse JSON payload: {parse_error}")
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        body = payload.get("body", {}) if "body" in payload else payload
        logger.info(f"📝 [{request_id}] Using {'body wrapper' if 'body' in payload else 'direct'} format")

        logger.info(f"🔍 [{request_id}] Available keys in body: {list(body.keys())}")
        for key, value in body.items():
            if "row" in key.lower() or "id" in key.lower():
                logger.info(f"🔍 [{request_id}] Potential row_id field: '{key}' = '{value}'")

        # Extract fields
        row_id = body.get("row_id") or body.get("\ud83d\udd12 row_id") or body.get("🔒 row_id")
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

        # Validate
        if not row_id:
            logger.error(f"❌ [{request_id}] Missing row_id")
            return jsonify({"status": "error", "message": "Missing row_id"}), 400

        missing_fields = []
        if not event_name: missing_fields.append("event_name")
        if not genre: missing_fields.append("genre")
        if not mood_tags: missing_fields.append("mood_tags")
        if not favorite_artist: missing_fields.append("favorite_artist")

        if missing_fields:
            error_message = f"Missing required fields: {', '.join(missing_fields)}"
            logger.warning(f"⚠️ [{request_id}] {error_message}")
            response_data = prepare_response_data(row_id, None, user_id, request_start_time)
            response_data["error_message"] = error_message
            return jsonify(response_data), 400

                # Build playlist
        logger.info(f"🎵 [{request_id}] Starting playlist build...")
        playlist_build_start = datetime.now()

        try:
            playlist_result = build_smart_playlist_enhanced(
                event_name=event_name,
                genre=genre,
                time=time,
                mood_tags=mood_tags,
                search_keywords=search_keywords,
                playlist_type=playlist_type,
                favorite_artist=favorite_artist,
                request_id=request_id
            )

            if isinstance(playlist_result, dict):
                track_count = playlist_result.get("track_count", 0)
            else:
                track_count = 0
                logger.warning(f"⚠️ [{request_id}] Playlist result is a string (likely URL); track_count set to 0")

            build_duration = (datetime.now() - playlist_build_start).total_seconds()
            logger.info(f"🎵 [{request_id}] Playlist build completed in {build_duration:.2f}s")
            logger.info(f"🎵 [{request_id}] Playlist result: {playlist_result}")

            if playlist_result:
                response_data = prepare_response_data(row_id, playlist_result, user_id, request_start_time)
                response_data["track_count"] = track_count

                # 🚀 Post to Glide
                try:
                    glide_url = os.environ.get("GLIDE_RETURN_WEBHOOK_URL")
                    if glide_url:
                        post_result = requests.post(glide_url, json=response_data)
                        logger.info(f"📤 [{request_id}] Posted to Glide (Status {post_result.status_code})")
                    else:
                        logger.warning(f"⚠️ [{request_id}] No GLIDE_RETURN_WEBHOOK_URL set")
                except Exception as post_err:
                    logger.error(f"❌ [{request_id}] Glide post failed: {post_err}")

                total_duration = (datetime.now() - request_start_time).total_seconds()
                logger.info(f"📊 [{request_id}] Total request duration: {total_duration:.2f}s")
                return jsonify(response_data), 200

            else:
                logger.warning(f"⚠️ [{request_id}] Playlist creation returned no data")
                response_data = prepare_response_data(row_id, None, user_id, request_start_time)
                response_data["error_message"] = "Playlist creation failed - no data returned"
                return jsonify(response_data), 500

        except Exception as playlist_error:
            logger.error(f"❌ [{request_id}] Playlist build failed: {playlist_error}", exc_info=True)
            response_data = prepare_response_data(row_id, None, user_id, request_start_time)
            response_data["error_message"] = f"Playlist build failed: {str(playlist_error)}"
            return jsonify(response_data), 500
    
    except Exception as critical:
        logger.error(f"❌ [{request_id}] Critical exception: {critical}", exc_info=True)
        try:
            fallback = {
                "row_id": request.get_json().get("body", {}).get("row_id", "unknown"),
                "status": "failed",
                "error_message": "Internal server error",
                "has_code": "false",
                "playlist_id": "",
                "spotify_url": "",
                "created_at": datetime.now().isoformat()
            }
            return jsonify(fallback), 500
        except:
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