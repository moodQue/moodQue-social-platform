from flask import Flask, request, jsonify
import sys
import os
import datetime
import uuid
import json
sys.path.append(os.path.join(os.path.dirname(__file__), "python"))

import gspread
from google.oauth2.service_account import Credentials

# Import your enhanced playlist builder functions
from SpotifyPlaylistBuilder import (
    build_smart_playlist_enhanced,
    refresh_access_token
)

app = Flask(__name__)

# Setup Google Sheets API credentials
def get_google_credentials():
    """Get Google credentials from environment variable or file"""
    # Try to get credentials from environment variable first
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    
    if creds_json:
        # Parse JSON from environment variable
        try:
            creds_dict = json.loads(creds_json)
            return Credentials.from_service_account_info(creds_dict, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ])
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing Google credentials from environment: {e}")
            return None
    else:
        # Fallback to local file for development
        SERVICE_ACCOUNT_FILE = "moodQue-automation-437f1e4eaa49.json"
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ])
        else:
            print(f"❌ No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable or place {SERVICE_ACCOUNT_FILE} in project directory.")
            return None

def get_sheets_client():
    """Get authenticated Google Sheets client"""
    creds = get_google_credentials()
    if creds:
        return gspread.authorize(creds)
    else:
        raise Exception("Failed to get Google credentials")

def ensure_social_sheets():
    """Create social feature sheets if they don't exist"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        
        # Ensure User Profiles sheet exists
        try:
            spreadsheet.worksheet("User Profiles")
        except (gspread.WorksheetNotFound, gspread.exceptions.WorksheetNotFound):
            user_sheet = spreadsheet.add_worksheet(title="User Profiles", rows="1000", cols="15")
            headers = [
                "User Email", "User Name", "Current Mood", "Last Active", 
                "Total Playlists", "Total Likes Received", "Total Likes Given",
                "Favorite Genre", "Favorite Mood", "Profile Created", 
                "Streak Days", "Last Streak Date", "Bio", "Avatar", "Status"
            ]
            user_sheet.append_row(headers)
        
        # Ensure Social Playlists sheet exists
        try:
            spreadsheet.worksheet("Social Playlists")
        except (gspread.WorksheetNotFound, gspread.exceptions.WorksheetNotFound):
            social_sheet = spreadsheet.add_worksheet(title="Social Playlists", rows="2000", cols="20")
            headers = [
                "Playlist ID", "Creator Email", "Creator Name", "Event Name",
                "Genre", "Mood", "Spotify URL", "Created Date", "Likes Count",
                "Views Count", "Shares Count", "Tags", "Description", 
                "Track Count", "Duration", "Is Public", "Is Trending",
                "Last Liked", "Featured", "Playlist Type"
            ]
            social_sheet.append_row(headers)
        
        # Ensure Social Interactions sheet exists
        try:
            spreadsheet.worksheet("Social Interactions")
        except (gspread.WorksheetNotFound, gspread.exceptions.WorksheetNotFound):
            interactions_sheet = spreadsheet.add_worksheet(title="Social Interactions", rows="5000", cols="10")
            headers = [
                "Interaction ID", "User Email", "Playlist ID", "Interaction Type",
                "Timestamp", "Additional Data", "IP Address", "User Agent",
                "Session ID", "Source"
            ]
            interactions_sheet.append_row(headers)
        
        return True
    except Exception as e:
        print(f"❌ Error ensuring social sheets: {e}")
        return False

def update_user_profile(user_email, user_name, updates):
    """Update or create user profile"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        user_sheet = spreadsheet.worksheet("User Profiles")
        
        # Find existing user
        try:
            cell = user_sheet.find(user_email)
            row_num = cell.row
            # Update existing user
            user_sheet.update(f"B{row_num}", user_name)  # Update name
            user_sheet.update(f"D{row_num}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))  # Last active
            
            # Update specific fields
            if 'current_mood' in updates:
                user_sheet.update(f"C{row_num}", updates['current_mood'])
            if 'total_playlists' in updates:
                user_sheet.update(f"E{row_num}", updates['total_playlists'])
            if 'total_likes_received' in updates:
                user_sheet.update(f"F{row_num}", updates['total_likes_received'])
            
        except (gspread.CellNotFound, gspread.exceptions.CellNotFound):
            # Create new user
            new_user_row = [
                user_email, user_name, 
                updates.get('current_mood', ''),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Last active
                updates.get('total_playlists', 0),
                updates.get('total_likes_received', 0),
                updates.get('total_likes_given', 0),
                updates.get('favorite_genre', ''),
                updates.get('favorite_mood', ''),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Profile created
                0,  # Streak days
                '',  # Last streak date
                updates.get('bio', ''),
                updates.get('avatar', ''),
                'active'
            ]
            user_sheet.append_row(new_user_row)
        
        return True
    except Exception as e:
        print(f"❌ Error updating user profile: {e}")
        return False

def save_social_playlist(playlist_data, playlist_url):
    """Save playlist to social feed"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        social_sheet = spreadsheet.worksheet("Social Playlists")
        
        playlist_id = str(uuid.uuid4())[:8]  # Short unique ID
        
        social_row = [
            playlist_id,
            playlist_data.get('user_email', ''),
            playlist_data.get('user_name', ''),
            playlist_data.get('event', ''),
            playlist_data.get('genre', ''),
            playlist_data.get('mood_tags', ''),
            playlist_url,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            0,  # Likes count
            0,  # Views count
            0,  # Shares count
            f"{playlist_data.get('search_keywords', '')}, {playlist_data.get('fallback_artist', '')}",  # Tags
            f"A {playlist_data.get('mood_tags', '')} {playlist_data.get('genre', '')} playlist for {playlist_data.get('event', '')}",  # Description
            playlist_data.get('track_count', 15),
            playlist_data.get('time', ''),
            True,  # Is public
            False,  # Is trending
            '',  # Last liked
            False,  # Featured
            playlist_data.get('playlist_type', 'clean')
        ]
        
        social_sheet.append_row(social_row)
        
        # Update user's playlist count
        update_user_profile(
            playlist_data.get('user_email', ''),
            playlist_data.get('user_name', ''),
            {'total_playlists': '+1'}  # Increment
        )
        
        return playlist_id
    except Exception as e:
        print(f"❌ Error saving social playlist: {e}")
        return None

def log_interaction(user_email, playlist_id, interaction_type, additional_data=None):
    """Log user interactions for analytics"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        interactions_sheet = spreadsheet.worksheet("Social Interactions")
        
        interaction_row = [
            str(uuid.uuid4())[:12],  # Interaction ID
            user_email,
            playlist_id,
            interaction_type,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(additional_data) if additional_data else '',
            request.remote_addr if request else '',
            request.headers.get('User-Agent', '') if request else '',
            request.headers.get('Session-ID', '') if request else '',
            'web_app'
        ]
        
        interactions_sheet.append_row(interaction_row)
        return True
    except Exception as e:
        print(f"❌ Error logging interaction: {e}")
        return False

# Add a simple root route to handle the 404 error
@app.route("/", methods=["GET", "POST"])
def home():
    """Root endpoint to confirm the service is running"""
    return jsonify({
        "status": "MoodQue Social Music Platform is running!",
        "endpoints": {
            "create_playlist": "/glide-webhook",
            "social_feed": "/social/feed",
            "leaderboard": "/social/leaderboard",
            "like_playlist": "/social/like-playlist",
            "mood_status": "/social/mood-status",
            "test": "/test"
        },
        "timestamp": str(datetime.datetime.now())
    }), 200

@app.route("/glide-webhook", methods=["POST"])
def create_playlist_from_glide():
    """Enhanced playlist creation with social features"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # Ensure social sheets exist
        ensure_social_sheets()
        
        # Extract form data
        event = data.get('Event')
        genre = data.get('Genre')
        time = data.get('Time')
        mood_tags = data.get('Mood Tags')
        search_keywords = data.get('Search Keywords', '')
        fallback_artist = data.get('Fallback Artist', '')
        playlist_type = data.get('Playlist Type', 'clean')
        
        # Extract user data
        user_email = data.get('User Email', 'anonymous')
        user_name = data.get('User Name', 'Anonymous User')
        
        # Update user's current mood
        update_user_profile(user_email, user_name, {'current_mood': mood_tags})
        
        artist_names = fallback_artist
        combined_keywords = search_keywords or fallback_artist or event
        
        print(f"🎵 Creating social playlist for {user_name}: {event}")
        
        # Generate the playlist
        playlist_url = build_smart_playlist_enhanced(
            event=event,
            genre=genre or "any",
            time=time,
            mood_tags=mood_tags,
            search_keywords=combined_keywords,
            artist_names=artist_names,
            user_preferences=None,
            playlist_type=playlist_type
        )
        
        if playlist_url:
            # Save to social feed
            playlist_data = {
                'user_email': user_email,
                'user_name': user_name,
                'event': event,
                'genre': genre or "any",
                'mood_tags': mood_tags,
                'search_keywords': search_keywords,
                'fallback_artist': fallback_artist,
                'playlist_type': playlist_type,
                'time': time,
                'track_count': max(5, int(time) // 4) if time else 15
            }
            
            playlist_id = save_social_playlist(playlist_data, playlist_url)
            
            # Log playlist creation
            log_interaction(user_email, playlist_id, "playlist_created", {
                'event': event,
                'genre': genre,
                'mood': mood_tags
            })
            
            response_data = {
                "status": "success",
                "playlist_url": playlist_url,
                "playlist_id": playlist_id,
                "message": f"✅ '{event}' playlist shared to MoodQue community!",
                "social_features": {
                    "can_like": True,
                    "can_share": True,
                    "creator": user_name,
                    "mood": mood_tags,
                    "genre": genre or "Mixed"
                }
            }
            
            print(f"✅ Social playlist created: {playlist_id}")
            return jsonify(response_data), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to create playlist. Please try again."
            }), 500
            
    except Exception as e:
        print(f"❌ Error in social playlist creation: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/like-playlist", methods=["POST"])
def like_playlist():
    """Like a playlist"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        playlist_id = data.get('playlist_id')
        
        if not user_email or not playlist_id:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Log the like interaction
        log_interaction(user_email, playlist_id, "playlist_liked")
        
        # TODO: Update playlist likes count in Social Playlists sheet
        # TODO: Update creator's total likes received
        
        return jsonify({
            "status": "success",
            "message": "Playlist liked!",
            "action": "liked"
        }), 200
        
    except Exception as e:
        print(f"❌ Error liking playlist: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/feed", methods=["GET"])
def get_social_feed():
    """Get recent playlists for social feed"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        social_sheet = spreadsheet.worksheet("Social Playlists")
        
        # Get all playlists (in reverse order for most recent first)
        all_playlists = social_sheet.get_all_records()
        
        # Sort by creation date (most recent first)
        sorted_playlists = sorted(all_playlists, 
                                key=lambda x: x.get('Created Date', ''), 
                                reverse=True)
        
        # Return top 20 for feed
        feed_playlists = sorted_playlists[:20]
        
        return jsonify({
            "status": "success",
            "playlists": feed_playlists,
            "count": len(feed_playlists)
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting social feed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/leaderboard", methods=["GET"])
def get_leaderboard():
    """Get leaderboard data"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        
        # Get user profiles for leaderboard
        user_sheet = spreadsheet.worksheet("User Profiles")
        all_users = user_sheet.get_all_records()
        
        # Sort by total likes received
        top_creators = sorted(all_users, 
                            key=lambda x: int(x.get('Total Likes Received', 0)), 
                            reverse=True)[:10]
        
        # Get trending playlists
        social_sheet = spreadsheet.worksheet("Social Playlists")
        all_playlists = social_sheet.get_all_records()
        
        trending_playlists = sorted(all_playlists,
                                  key=lambda x: int(x.get('Likes Count', 0)),
                                  reverse=True)[:5]
        
        return jsonify({
            "status": "success",
            "leaderboard": {
                "top_creators": top_creators,
                "trending_playlists": trending_playlists
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting leaderboard: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/mood-status", methods=["POST"])
def update_mood_status():
    """Update user's current mood status"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        user_name = data.get('user_name')
        new_mood = data.get('mood')
        
        if not user_email or not new_mood:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Update user profile
        update_user_profile(user_email, user_name, {'current_mood': new_mood})
        
        # Log mood change
        log_interaction(user_email, None, "mood_updated", {'new_mood': new_mood})
        
        return jsonify({
            "status": "success",
            "message": f"Mood updated to {new_mood}",
            "mood": new_mood
        }), 200
        
    except Exception as e:
        print(f"❌ Error updating mood: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/test", methods=["GET"])
def test_endpoint():
    """Test endpoint with social features status"""
    try:
        access_token = refresh_access_token()
        spotify_status = "✅ Connected" if access_token else "❌ Failed"
        
        # Test Google credentials
        try:
            creds = get_google_credentials()
            google_status = "✅ Connected" if creds else "❌ No credentials"
        except Exception as e:
            google_status = f"❌ Error: {str(e)}"
        
        # Test social sheets
        try:
            ensure_social_sheets()
            sheets_status = "✅ Active"
        except Exception as e:
            sheets_status = f"❌ Error: {str(e)}"
        
        return jsonify({
            "status": "MoodQue Social Server is running",
            "features": {
                "playlist_creation": "/glide-webhook",
                "social_feed": "/social/feed", 
                "leaderboard": "/social/leaderboard",
                "like_playlist": "/social/like-playlist",
                "mood_status": "/social/mood-status"
            },
            "connections": {
                "spotify": spotify_status,
                "google_credentials": google_status,
                "google_sheets": sheets_status
            },
            "timestamp": str(datetime.datetime.now())
        }), 200
    except Exception as e:
        return jsonify({
            "status": "Server running but issues detected",
            "error": str(e)
        }), 200

if __name__ == "__main__":
    print("🚀 Starting MoodQue Social Music Platform...")
    print("🏠 Home endpoint: /")
    print("📱 Playlist creation: /glide-webhook")
    print("🎵 Social feed: /social/feed")
    print("🏆 Leaderboard: /social/leaderboard") 
    print("❤️ Like playlists: /social/like-playlist")
    print("😊 Mood status: /social/mood-status")
    print("🧪 Test endpoint: /test")
    
    # Check credentials
    try:
        creds = get_google_credentials()
        if creds:
            print("✅ Google credentials loaded successfully")
            # Ensure social features are set up
            ensure_social_sheets()
        else:
            print("⚠️ Google credentials not found - some features may not work")
    except Exception as e:
        print(f"⚠️ Google credentials error: {e}")
    
    # Use Railway's PORT environment variable, fallback to 8080 for local development
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)