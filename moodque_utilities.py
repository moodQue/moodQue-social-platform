import os
import base64
import requests
import time

# Only load .env if running locally (Railway sets env vars automatically)
if os.getenv("RAILWAY_ENVIRONMENT") is None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available in production

from firebase_admin_init import db

# Example variable usage
client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")

def refresh_access_token():
    """Refresh the system Spotify access token"""
    url = "https://accounts.spotify.com/api/token"
    client_creds = f"{client_id}:{client_secret}"
    client_creds_b64 = base64.b64encode(client_creds.encode()).decode()

    headers = {
        "Authorization": f"Basic {client_creds_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    res = requests.post(url, headers=headers, data=payload)
    if res.status_code != 200:
        print("❌ Error refreshing token:", res.json())
        exit()
    return res.json()["access_token"]

def get_spotify_access_token():
    """
    Fetches a new access token using the app's stored refresh token.
    """
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)

    if response.status_code != 200:
        print("❌ Failed to refresh app access token", response.text)
        raise Exception("Spotify token refresh failed")

    token_info = response.json()
    return token_info["access_token"]

def get_spotify_user_id(headers):
    """Get the current user's Spotify ID"""
    try:
        res = requests.get("https://api.spotify.com/v1/me", headers=headers)
        if res.status_code == 200:
            data = res.json()
            return data.get("id")
        else:
            print(f"❌ Failed to get user ID: {res.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting user ID: {e}")
        return None

def create_new_playlist(headers, user_id, name, description=""):
    """
    Create a new playlist for the user
    """
    try:
        url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
        data = {
            "name": name,
            "description": description,
            "public": False
        }
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 201:
            return res.json()["id"]
        else:
            print(f"❌ Failed to create playlist: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"❌ Exception creating playlist: {e}")
        return None

def add_tracks_to_playlist(headers, playlist_id, track_uris):
    """
    Add tracks to playlist with better error handling
    """
    try:
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        
        # Ensure track_uris is a list of strings
        if isinstance(track_uris, list):
            clean_uris = []
            for t in track_uris:
                if isinstance(t, dict) and "uri" in t:
                    clean_uris.append(t["uri"])
                elif isinstance(t, str) and "spotify:track:" in t:
                    clean_uris.append(t)
        else:
            clean_uris = []

        if not clean_uris:
            print("❌ No valid track URIs to add")
            return False

        payload = {"uris": clean_uris}
        res = requests.post(url, headers=headers, json=payload)

        if res.status_code == 201:
            print(f"✅ Successfully added {len(clean_uris)} tracks to playlist")
            return True
        else:
            print(f"❌ Error adding tracks: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"❌ Exception adding tracks: {e}")
        return False

def calculate_playlist_duration(track_uris, headers):
    """Calculate total playlist duration in minutes"""
    try:
        track_data = get_tracks_with_duration(track_uris, headers)
        total_ms = sum(track['duration_ms'] for track in track_data)
        return total_ms / 60000  # Convert to minutes
    except Exception as e:
        print(f"❌ Error calculating duration: {e}")
        return 0

def get_tracks_with_duration(track_uris, headers):
    """Get track duration information for a list of URIs including explicit info"""
    try:
        track_data = []
        
        # Process in batches of 50 (Spotify API limit)
        batch_size = 50
        for i in range(0, len(track_uris), batch_size):
            batch_uris = track_uris[i:i + batch_size]
            track_ids = [uri.split(":")[-1] for uri in batch_uris if isinstance(uri, str)]
            
            if not track_ids:
                continue
            
            res = requests.get("https://api.spotify.com/v1/tracks", 
                              headers=headers, 
                              params={"ids": ",".join(track_ids)})
            
            if res.status_code == 200:
                data = res.json()
                tracks = data.get("tracks", [])
                
                for j, track in enumerate(tracks):
                    if track and isinstance(track, dict):
                        track_info = {
                            'uri': batch_uris[j] if j < len(batch_uris) else track.get("uri"),
                            'duration_ms': track.get("duration_ms", 210000),
                            'name': track.get("name", "Unknown"),
                            'artist': track.get("artists", [{}])[0].get("name", "Unknown"),
                            'explicit': track.get("explicit", False)
                        }
                        track_data.append(track_info)
        
        return track_data
        
    except Exception as e:
        print(f"❌ Error getting track durations: {e}")
        return []

def search_spotify_tracks_enhanced_with_duration(genre, headers, target_duration_minutes=30, 
                                                max_tracks=100, mood_tags=None, 
                                                search_keywords=None, playlist_type="clean", 
                                                favorite_artist=None):
    """Enhanced search with duration-based selection"""
    try:
        print(f"🔍 Enhanced search - Genre: {genre}, Target: {target_duration_minutes}min")
        
        # Import here to avoid circular imports
        from moodque_engine import search_spotify_tracks_enhanced
        
        track_uris = search_spotify_tracks_enhanced(
            genre=genre,
            headers=headers,
            limit=max_tracks,
            mood_tags=mood_tags,
            search_keywords=search_keywords,
            playlist_type=playlist_type,
            favorite_artist=favorite_artist
        )
        
        if not track_uris:
            print("❌ No tracks found from enhanced search")
            return []
        
        # Get track details with duration
        track_data = get_tracks_with_duration(track_uris, headers)
        
        # Filter by explicit content
        if playlist_type.lower() == "clean":
            track_data = [t for t in track_data if not t.get("explicit", False)]
        elif playlist_type.lower() == "explicit":
            track_data = [t for t in track_data if t.get("explicit", False)]
        
        # Select tracks to match target duration
        selected_tracks = []
        current_duration = 0
        target_duration_ms = target_duration_minutes * 60 * 1000
        
        for track in track_data:
            if current_duration >= target_duration_ms:
                break
            selected_tracks.append(track)
            current_duration += track['duration_ms']
        
        final_duration = current_duration / 60000
        print(f"✅ Selected {len(selected_tracks)} tracks, {final_duration:.1f} minutes")
        
        return selected_tracks
        
    except Exception as e:
        print(f"❌ Error in enhanced search with duration: {e}")
        return []

def search_spotify_track(artist, title, headers):
    """Search for a specific track by artist and title"""
    try:
        if not artist or not title or not headers:
            return None
        
        query = f"track:{title} artist:{artist}"
        url = "https://api.spotify.com/v1/search"
        params = {"q": query, "type": "track", "limit": 1}
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks_data = data.get("tracks", {})
                if isinstance(tracks_data, dict):
                    tracks = tracks_data.get("items", [])
                    return tracks[0]["uri"] if tracks else None
        return None
    except Exception as e:
        print(f"❌ Error searching track: {e}")
        return None

def get_valid_access_token(user_id=None):
    """
    Returns access token for given user_id or falls back to MoodQue account
    """
    try:
        if user_id:
            token = get_spotify_access_token()
            if token:
                return token
        # Fallback if no user_id or token fetch failed
        return refresh_access_token()
    except Exception as e:
        print(f"❌ Error getting access token: {e}")
        return refresh_access_token()

# Firestore helper functions
def get_user_tokens(user_id):
    """Get user tokens from Firestore"""
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"❌ Error getting user tokens: {e}")
        return None

def save_user_tokens(user_id, access_token, refresh_token):
    """Save user tokens to Firestore"""
    try:
        db.collection("users").document(user_id).set({
            "spotify_access_token": access_token,
            "spotify_refresh_token": refresh_token,
            "spotify_token_expires_at": str(int(time.time()) + 3600)
        }, merge=True)
        print(f"✅ Saved tokens for user {user_id}")
    except Exception as e:
        print(f"❌ Error saving user tokens: {e}")

def record_social_interaction(data):
    """Record social interaction in Firestore"""
    try:
        db.collection("social_interactions").add(data)
        print("✅ Social interaction recorded")
    except Exception as e:
        print(f"❌ Error recording social interaction: {e}")

def record_ml_feedback(data):
    """Record ML feedback in Firestore"""
    try:
        db.collection("ml_feedback").add(data)
        print("✅ ML feedback recorded")
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Error recording ML feedback: {e}")
        return {"status": "error", "message": str(e)}

def post_data_back_to_glide(webhook_url, data):
    """Post data back to Glide webhook"""
    try:
        response = requests.post(webhook_url, json=data)
        return response
    except Exception as e:
        print(f"❌ Error posting to Glide: {e}")
        return None