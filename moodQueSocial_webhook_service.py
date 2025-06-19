from flask import Flask, request, jsonify
import sys
import os
import datetime
import uuid
import json
from urllib.parse import quote
sys.path.append(os.path.join(os.path.dirname(__file__), "python"))

import gspread
from google.oauth2.service_account import Credentials

# Import your enhanced playlist builder functions
from SpotifyPlaylistBuilder import (
    build_smart_playlist_enhanced,
    refresh_access_token
)

# Import the new Spotify code generator
from spotify_code_generator import SpotifyCodeGenerator

app = Flask(__name__)

# Setup Google Sheets API credentials
def get_google_credentials():
    """Get Google credentials from environment variable or file"""
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    
    if creds_json:
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
        SERVICE_ACCOUNT_FILE = "moodQue-automation-437f1e4eaa49.json"
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ])
        else:
            print(f"❌ No Google credentials found.")
            return None

def get_sheets_client():
    """Get authenticated Google Sheets client"""
    creds = get_google_credentials()
    if creds:
        return gspread.authorize(creds)
    else:
        raise Exception("Failed to get Google credentials")

def ensure_social_sheets():
    """Create social feature sheets if they don't exist - Updated with Spotify code columns"""
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
        
        # Ensure Social Playlists sheet exists - UPDATED with Spotify code columns
        try:
            social_sheet = spreadsheet.worksheet("Social Playlists")
            # Check if it has the new columns
            headers = social_sheet.row_values(1)
            if "Spotify Code URL" not in headers:
                print("⚠️ Social Playlists sheet exists but missing Spotify code columns")
                print("   Please run update_sheets.py first!")
        except (gspread.WorksheetNotFound, gspread.exceptions.WorksheetNotFound):
            social_sheet = spreadsheet.add_worksheet(title="Social Playlists", rows="2000", cols="25")
            headers = [
                "Playlist ID", "Creator Email", "Creator Name", "Event Name",
                "Genre", "Mood", "Search Keywords", "Spotify URL", "Created Date", 
                "Likes Count", "Views Count", "Shares Count", "Tags", "Description", 
                "Track Count", "Duration", "Is Public", "Is Trending",
                "Last Liked", "Featured", "Playlist Type", "Spotify Code URL", 
                "Has Code", "Code Generated", "Code Format"
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
        
        try:
            cell = user_sheet.find(user_email)
            row_num = cell.row
            print(f"✅ Found existing user: {user_email} at row {row_num}")
            
            user_sheet.update(f"B{row_num}", user_name)
            user_sheet.update(f"D{row_num}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            if 'current_mood' in updates:
                user_sheet.update(f"C{row_num}", updates['current_mood'])
            if 'total_playlists' in updates:
                if updates['total_playlists'] == '+1':
                    current_val = user_sheet.acell(f"E{row_num}").value
                    new_val = int(current_val or 0) + 1
                    user_sheet.update(f"E{row_num}", new_val)
                else:
                    user_sheet.update(f"E{row_num}", updates['total_playlists'])
            if 'total_likes_received' in updates:
                if updates['total_likes_received'] == '+1':
                    current_val = user_sheet.acell(f"F{row_num}").value
                    new_val = int(current_val or 0) + 1
                    user_sheet.update(f"F{row_num}", new_val)
                else:
                    user_sheet.update(f"F{row_num}", updates['total_likes_received'])
            
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "unable to find" in error_str:
                print(f"👤 Creating new user profile for: {user_email}")
                new_user_row = [
                    user_email, user_name, updates.get('current_mood', ''),
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    updates.get('total_playlists', 0),
                    updates.get('total_likes_received', 0),
                    updates.get('total_likes_given', 0),
                    updates.get('favorite_genre', ''),
                    updates.get('favorite_mood', ''),
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    0, '', updates.get('bio', ''), updates.get('avatar', ''), 'active'
                ]
                user_sheet.append_row(new_user_row)
                print(f"✅ Created new user profile for: {user_email}")
            else:
                print(f"❌ Unexpected error finding user {user_email}: {e}")
                raise e
        
        return True
    except Exception as e:
        print(f"❌ Error updating user profile: {e}")
        return False

def save_social_playlist(playlist_data, playlist_url):
    """Save playlist to social feed - UPDATED with Spotify code generation"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        social_sheet = spreadsheet.worksheet("Social Playlists")
        
        playlist_id = str(uuid.uuid4())[:8]
        
        # Generate Spotify code
        code_gen = SpotifyCodeGenerator()
        code_data = code_gen.generate_spotify_code(playlist_url)
        
        code_url = ""
        has_code = False
        code_generated = ""
        code_format = ""
        
        if code_data:
            code_url = code_data["code_url"]
            has_code = True
            code_generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            code_format = code_data["format"]
            print(f"✅ Generated Spotify code for playlist {playlist_id}")
        else:
            print(f"⚠️ Failed to generate Spotify code for playlist {playlist_id}")
        
        # Get current headers to find column positions
        headers = social_sheet.row_values(1)
        
        # Build the row data - handling both old and new sheet structures
        social_row = [
            playlist_id,                    # A: Playlist ID
            playlist_data.get('user_email', ''),  # B: Creator Email
            playlist_data.get('user_name', ''),   # C: Creator Name
            playlist_data.get('event', ''),       # D: Event Name
            playlist_data.get('genre', ''),       # E: Genre
            playlist_data.get('mood_tags', ''),   # F: Mood
            playlist_data.get('search_keywords', ''),  # G: Search Keywords
            playlist_url,                         # H: Spotify URL
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # I: Created Date
            0,  # J: Likes count
            0,  # K: Views count
            0,  # L: Shares count
            f"{playlist_data.get('fallback_artist', '')}",  # M: Tags
            f"A {playlist_data.get('mood_tags', '')} {playlist_data.get('genre', '')} playlist for {playlist_data.get('event', '')}",  # N: Description
            playlist_data.get('track_count', 15),  # O: Track Count
            playlist_data.get('time', ''),         # P: Duration
            True,  # Q: Is public
            False, # R: Is trending
            '',    # S: Last liked
            False, # T: Featured
            playlist_data.get('playlist_type', 'clean')  # U: Playlist Type
        ]
        
        # Add Spotify code columns if they exist
        if "Spotify Code URL" in headers:
            social_row.extend([
                code_url,      # V: Spotify Code URL
                has_code,      # W: Has Code
                code_generated, # X: Code Generated
                code_format    # Y: Code Format
            ])
        
        social_sheet.append_row(social_row)
        
        # Update user's playlist count
        update_user_profile(
            playlist_data.get('user_email', ''),
            playlist_data.get('user_name', ''),
            {'total_playlists': '+1'}
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
            str(uuid.uuid4())[:12],
            user_email, playlist_id, interaction_type,
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

# Root route
@app.route("/", methods=["GET", "POST"])
def home():
    """Root endpoint to confirm the service is running"""
    return jsonify({
        "status": "MoodQue Social Music Platform with Spotify Codes is running!",
        "version": "2.0 - Spotify Codes Edition",
        "endpoints": {
            "create_playlist": "/glide-webhook",
            "social_feed": "/social/feed",
            "social_feed_with_codes": "/social/feed-with-codes",
            "leaderboard": "/social/leaderboard",
            "like_playlist": "/social/like-playlist",
            "mood_status": "/social/mood-status",
            "generate_spotify_code": "/spotify/generate-code",
            "playlist_with_code": "/spotify/playlist-with-code/<playlist_id>",
            "test": "/test"
        },
        "features": ["Playlist Creation", "Social Feed", "Spotify Codes", "Leaderboards"],
        "timestamp": str(datetime.datetime.now())
    }), 200

@app.route("/glide-webhook", methods=["POST"])
def create_playlist_from_glide():
    """Enhanced playlist creation with social features and Spotify codes"""
    try:
        data = request.get_json()
        
        print("=" * 50)
        print("🔍 DEBUG - Raw form data received:")
        print(json.dumps(data, indent=2))
        print("=" * 50)
        
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        ensure_social_sheets()
        
        # Extract form data
        event = data.get('Event')
        genre = data.get('Genre')
        time = data.get('Time')
        mood_tags = data.get('Mood Tags')
        search_keywords = data.get('Search Keywords', '')
        fallback_artist = data.get('Fallback Artist', '')
        playlist_type = data.get('Playlist Type', 'clean')
        user_email = data.get('User Email', 'anonymous')
        user_name = data.get('User Name', 'Anonymous User')
        
        print(f"🎵 Creating playlist for {user_name} ({user_email}): {event}")
        
        # Update user's current mood
        update_user_profile(user_email, user_name, {'current_mood': mood_tags})
        
        artist_names = fallback_artist
        combined_keywords = search_keywords or fallback_artist or event
        
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
            # Save to social feed (now includes Spotify code generation)
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
            
            # Generate Spotify code for response
            code_gen = SpotifyCodeGenerator()
            code_data = code_gen.generate_spotify_code(playlist_url)
            
            # Log playlist creation
            log_interaction(user_email, playlist_id, "playlist_created", {
                'event': event, 'genre': genre, 'mood': mood_tags
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
            
            # Add Spotify code to response if generated
            if code_data:
                response_data["spotify_code"] = code_data
                response_data["message"] += " 📱 Spotify code generated!"
            
            print(f"✅ Social playlist created with Spotify code: {playlist_id}")
            return jsonify(response_data), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to create playlist. Please try again."
            }), 500
            
    except Exception as e:
        print(f"❌ Error in social playlist creation: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# NEW SPOTIFY CODE ENDPOINTS

@app.route("/spotify/generate-code", methods=["POST"])
def generate_spotify_code_endpoint():
    """Generate Spotify code for any Spotify URL"""
    try:
        data = request.get_json()
        spotify_url = data.get('spotify_url')
        format_type = data.get('format', 'png')
        size = data.get('size', 320)
        
        if not spotify_url:
            return jsonify({"status": "error", "message": "Spotify URL required"}), 400
        
        code_gen = SpotifyCodeGenerator()
        code_data = code_gen.generate_spotify_code(spotify_url, format_type, size)
        
        if code_data:
            return jsonify({
                "status": "success",
                "spotify_code": code_data
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to generate Spotify code"
            }), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/spotify/playlist-with-code/<playlist_id>", methods=["GET"])
def get_playlist_with_code(playlist_id):
    """Get playlist data including Spotify code"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        social_sheet = spreadsheet.worksheet("Social Playlists")
        
        # Find the playlist
        all_records = social_sheet.get_all_records()
        playlist_data = None
        
        for record in all_records:
            if record.get('Playlist ID') == playlist_id:
                playlist_data = record
                break
        
        if not playlist_data:
            return jsonify({"status": "error", "message": "Playlist not found"}), 404
        
        # If no Spotify code exists, generate one
        if not playlist_data.get('Spotify Code URL'):
            spotify_url = playlist_data.get('Spotify URL')
            if spotify_url:
                code_gen = SpotifyCodeGenerator()
                code_data = code_gen.generate_spotify_code(spotify_url)
                if code_data:
                    playlist_data['Spotify Code URL'] = code_data['code_url']
                    playlist_data['Has Code'] = True
                    playlist_data['spotify_code'] = code_data
        
        return jsonify({
            "status": "success",
            "playlist": playlist_data
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/feed-with-codes", methods=["GET"])
def get_social_feed_with_codes():
    """Get social feed with Spotify codes included"""
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        social_sheet = spreadsheet.worksheet("Social Playlists")
        
        # Get all playlists
        all_playlists = social_sheet.get_all_records()
        
        # Sort by creation date (most recent first)
        sorted_playlists = sorted(all_playlists, 
                                key=lambda x: x.get('Created Date', ''), 
                                reverse=True)
        
        # Process playlists and ensure they have Spotify codes
        feed_playlists = []
        code_gen = SpotifyCodeGenerator()
        
        for playlist in sorted_playlists[:20]:  # Top 20
            spotify_url = playlist.get('Spotify URL')
            
            # If playlist doesn't have a code but has a URL, generate one
            if spotify_url and not playlist.get('Spotify Code URL'):
                code_data = code_gen.generate_spotify_code(spotify_url)
                if code_data:
                    playlist['Spotify Code URL'] = code_data['code_url']
                    playlist['Has Code'] = True
                    playlist['spotify_code'] = code_data
            elif playlist.get('Spotify Code URL'):
                playlist['Has Code'] = True
                playlist['spotify_code'] = {
                    'code_url': playlist.get('Spotify Code URL'),
                    'format': playlist.get('Code Format', 'png'),
                    'size': 320
                }
            
            feed_playlists.append(playlist)
        
        return jsonify({
            "status": "success",
            "playlists": feed_playlists,
            "count": len(feed_playlists),
            "has_spotify_codes": True
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/like-playlist", methods=["POST"])
def like_playlist():
    """Like a playlist"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        playlist_id = data.get('playlist_id')
        
        print(f"❤️ Like request: {user_email} likes {playlist_id}")
        
        if not user_email or not playlist_id:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Log the like interaction
        log_interaction(user_email, playlist_id, "playlist_liked")
        
        # Update playlist likes count in Social Playlists sheet
        try:
            client = get_sheets_client()
            spreadsheet = client.open("Playlist App Data")
            social_sheet = spreadsheet.worksheet("Social Playlists")
            
            # Find the playlist and increment likes
            all_records = social_sheet.get_all_records()
            for i, record in enumerate(all_records, start=2):  # Start at row 2 (after header)
                if record.get('Playlist ID') == playlist_id:
                    current_likes = int(record.get('Likes Count', 0))
                    new_likes = current_likes + 1
                    social_sheet.update(f"J{i}", new_likes)  # Update Likes Count column
                    print(f"✅ Updated likes for playlist {playlist_id}: {current_likes} -> {new_likes}")
                    
                    # Also update creator's total likes received
                    creator_email = record.get('Creator Email')
                    if creator_email:
                        update_user_profile(creator_email, '', {'total_likes_received': '+1'})
                    
                    return jsonify({
                        "status": "success",
                        "message": "Playlist liked!",
                        "action": "liked",
                        "new_likes_count": new_likes
                    }), 200
            
            return jsonify({
                "status": "error",
                "message": "Playlist not found"
            }), 404
            
        except Exception as e:
            print(f"❌ Error updating likes count: {e}")
            return jsonify({
                "status": "error",
                "message": "Failed to update likes"
            }), 500
        
    except Exception as e:
        print(f"❌ Error liking playlist: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/social/feed", methods=["GET"])
def get_social_feed():
    """Get recent playlists for social feed (without codes for compatibility)"""
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
    """Test endpoint with social features status and Spotify code test"""
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
        
        # Test Spotify code generation
        try:
            test_url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
            code_gen = SpotifyCodeGenerator()
            test_code = code_gen.generate_spotify_code(test_url)
            spotify_code_status = "✅ Working" if test_code else "❌ Failed"
            test_code_url = test_code["code_url"] if test_code else "None"
        except Exception as e:
            spotify_code_status = f"❌ Error: {str(e)}"
            test_code_url = "Error"
        
        return jsonify({
            "status": "MoodQue Social Server with Spotify Codes is running",
            "version": "2.0 - Spotify Codes Edition",
            "features": {
                "playlist_creation": "/glide-webhook",
                "social_feed": "/social/feed", 
                "social_feed_with_codes": "/social/feed-with-codes",
                "leaderboard": "/social/leaderboard",
                "like_playlist": "/social/like-playlist",
                "mood_status": "/social/mood-status",
                "generate_spotify_code": "/spotify/generate-code",
                "playlist_with_code": "/spotify/playlist-with-code/<id>"
            },
            "connections": {
                "spotify": spotify_status,
                "google_credentials": google_status,
                "google_sheets": sheets_status,
                "spotify_codes": spotify_code_status
            },
            "test_results": {
                "spotify_code_test_url": test_code_url
            },
            "new_features": [
                "✨ Spotify Code Generation",
                "📱 Visual Playlist Sharing",
                "🔗 Enhanced Social Feed",
                "📊 Code Analytics"
            ],
            "timestamp": str(datetime.datetime.now())
        }), 200
    except Exception as e:
        return jsonify({
            "status": "Server running but issues detected",
            "error": str(e)
        }), 200

# Add this endpoint to your moodQueSocial_webhook_service.py file

@app.route("/glide/sync-clean-data", methods=["POST"])
def sync_clean_data_to_glide():
    """
    Receive clean playlist data from Google Sheets and format for Glide
    This replaces the messy data with clean, complete playlists
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        playlists = data.get('playlists', [])
        total_count = data.get('total_count', 0)
        metadata = data.get('metadata', {})
        
        print(f"🧹 Received clean data sync request: {total_count} playlists")
        print(f"📊 Metadata: {metadata}")
        
        # Process the clean data
        processed_playlists = []
        spotify_codes_count = 0
        
        for playlist in playlists:
            # Ensure all required fields are present for Glide
            clean_playlist = {
                # Core playlist info
                'playlist_id': playlist.get('Playlist ID', ''),
                'creator_email': playlist.get('Creator Email', ''),
                'creator_name': playlist.get('Creator Name', ''),
                'event_name': playlist.get('Event Name', ''),
                'genre': playlist.get('Genre', ''),
                'mood': playlist.get('Mood', ''),
                'spotify_url': playlist.get('Spotify URL', ''),
                'created_date': playlist.get('Created Date', ''),
                'description': playlist.get('Description', ''),
                
                # Social features
                'likes_count': int(playlist.get('likes_count_number', 0)),
                'views_count': int(playlist.get('views_count_number', 0)),
                'shares_count': int(playlist.get('shares_count_number', 0)),
                
                # Spotify code info
                'spotify_code_url': playlist.get('Spotify Code URL', ''),
                'has_spotify_code': playlist.get('has_spotify_code_boolean', False),
                'code_generated': playlist.get('Code Generated', ''),
                'code_format': playlist.get('Code Format', 'png'),
                
                # Boolean flags
                'is_public': playlist.get('is_public_boolean', True),
                'is_trending': playlist.get('is_trending_boolean', False),
                'featured': playlist.get('featured_boolean', False),
                
                # Additional fields
                'track_count': int(playlist.get('track_count_number', 0)),
                'duration': playlist.get('Duration', ''),
                'playlist_type': playlist.get('Playlist Type', 'clean'),
                'tags': playlist.get('Tags', ''),
                
                # Computed fields for Glide
                'popularity_score': playlist.get('popularity_score', 0),
                'has_code_text': 'Yes' if playlist.get('has_spotify_code_boolean', False) else 'No',
                'duration_text': f"{playlist.get('Duration', '')} min" if playlist.get('Duration') else '',
                'engagement_score': int(playlist.get('likes_count_number', 0)) + int(playlist.get('views_count_number', 0)) * 0.1,
                
                # Timestamps
                'last_updated': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'sync_timestamp': data.get('timestamp', datetime.datetime.now().isoformat())
            }
            
            if clean_playlist['has_spotify_code']:
                spotify_codes_count += 1
            
            processed_playlists.append(clean_playlist)
        
        # Update Google Sheets with the clean data (write back)
        try:
            client = get_sheets_client()
            spreadsheet = client.open("Playlist App Data")
            
            # Create or update a "Clean Playlists for Glide" sheet
            try:
                glide_sheet = spreadsheet.worksheet("Clean Playlists for Glide")
                # Clear existing data
                glide_sheet.clear()
            except (gspread.WorksheetNotFound, gspread.exceptions.WorksheetNotFound):
                glide_sheet = spreadsheet.add_worksheet(title="Clean Playlists for Glide", rows="2000", cols="30")
            
            # Prepare headers and data for Glide sheet
            if processed_playlists:
                glide_headers = list(processed_playlists[0].keys())
                glide_data = [glide_headers]
                
                for playlist in processed_playlists:
                    row = [playlist.get(header, '') for header in glide_headers]
                    glide_data.append(row)
                
                # Write to sheet
                glide_sheet.update(f"A1:{chr(65 + len(glide_headers) - 1)}{len(glide_data)}", glide_data)
                print(f"✅ Updated 'Clean Playlists for Glide' sheet with {len(processed_playlists)} rows")
        
        except Exception as sheet_error:
            print(f"⚠️ Could not update Glide sheet: {sheet_error}")
            # Continue anyway - the data is still processed
        
        # Log the sync
        log_interaction('system', 'glide_sync', 'clean_data_sync', {
            'total_playlists': total_count,
            'spotify_codes': spotify_codes_count,
            'timestamp': data.get('timestamp')
        })
        
        response_data = {
            "status": "success",
            "message": f"✅ Clean data sync complete! Processed {total_count} playlists",
            "processed_count": len(processed_playlists),
            "spotify_codes_count": spotify_codes_count,
            "glide_ready": True,
            "clean_data_available": True,
            "sheet_name": "Clean Playlists for Glide",
            "metadata": {
                "sync_timestamp": datetime.datetime.now().isoformat(),
                "source": "google_sheets_cleanup",
                "has_spotify_codes": spotify_codes_count > 0
            }
        }
        
        print(f"🎉 Clean data sync successful: {len(processed_playlists)} playlists ready for Glide")
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ Error in clean data sync: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Clean data sync failed: {str(e)}"
        }), 500

@app.route("/glide/get-clean-data", methods=["GET"])
def get_clean_data_for_glide():
    """
    Endpoint for Glide to fetch clean playlist data
    Use this URL as your data source in Glide
    """
    try:
        client = get_sheets_client()
        spreadsheet = client.open("Playlist App Data")
        
        try:
            glide_sheet = spreadsheet.worksheet("Clean Playlists for Glide")
            all_data = glide_sheet.get_all_records()
            
            # Sort by creation date (most recent first)
            sorted_data = sorted(all_data, 
                               key=lambda x: x.get('created_date', ''), 
                               reverse=True)
            
            return jsonify({
                "status": "success",
                "playlists": sorted_data,
                "count": len(sorted_data),
                "last_updated": datetime.datetime.now().isoformat(),
                "has_spotify_codes": True
            }), 200
            
        except (gspread.WorksheetNotFound, gspread.exceptions.WorksheetNotFound):
            return jsonify({
                "status": "error",
                "message": "Clean data not available. Run cleanup first.",
                "playlists": [],
                "count": 0
            }), 404
            
    except Exception as e:
        print(f"❌ Error getting clean data: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
if __name__ == "__main__":
    print("🚀 Starting MoodQue Social Music Platform with Spotify Codes...")
    print("🎵 Version 2.0 - Spotify Codes Edition")
    print("=" * 60)
    print("📱 Endpoints:")
    print("   🏠 Home: /")
    print("   🎵 Create playlist: /glide-webhook")
    print("   📋 Social feed: /social/feed")
    print("   📱 Social feed with codes: /social/feed-with-codes")
    print("   🏆 Leaderboard: /social/leaderboard")
    print("   ❤️ Like playlists: /social/like-playlist")
    print("   😊 Mood status: /social/mood-status")
    print("   🎼 Generate Spotify code: /spotify/generate-code")
    print("   📊 Playlist with code: /spotify/playlist-with-code/<id>")
    print("   🧪 Test endpoint: /test")
    print("=" * 60)
    
    # Check credentials
    try:
        creds = get_google_credentials()
        if creds:
            print("✅ Google credentials loaded successfully")
            ensure_social_sheets()
            print("✅ Social sheets with Spotify code support ready")
        else:
            print("⚠️ Google credentials not found - some features may not work")
    except Exception as e:
        print(f"⚠️ Google credentials error: {e}")
    
    # Test Spotify code generation
    try:
        code_gen = SpotifyCodeGenerator()
        test_result = code_gen.generate_spotify_code("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
        if test_result:
            print("✅ Spotify code generation working")
            print(f"   Sample code URL: {test_result['code_url']}")
        else:
            print("⚠️ Spotify code generation test failed")
    except Exception as e:
        print(f"⚠️ Spotify code test error: {e}")
    
    # Use Railway's PORT environment variable, fallback to 8080 for local development
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)