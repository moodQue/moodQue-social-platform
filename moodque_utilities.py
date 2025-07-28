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

def add_tracks_to_playlist(headers, user_id, playlist_id, track_uris):
    """
    Add tracks to playlist - CORRECTED SIGNATURE to match engine expectations
    Note: user_id parameter is kept for compatibility but not used in API call
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

def search_spotify_track(artist, title, headers):
    """Search for a specific track by artist and title"""
    try:
        if not artist or not title or not headers:
            return None
        
        query = f"track:\"{title}\" artist:\"{artist}\""
        url = "https://api.spotify.com/v1/search"
        params = {"q": query, "type": "track", "limit": 1, "market": "US"}
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks_data = data.get("tracks", {})
                if isinstance(tracks_data, dict):
                    tracks = tracks_data.get("items", [])
                    if tracks:
                        return tracks[0]["uri"]
        
        # Fallback: try without quotes
        query_fallback = f"track:{title} artist:{artist}"
        params["q"] = query_fallback
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code == 200:
            data = res.json()
            tracks = data.get("tracks", {}).get("items", [])
            if tracks:
                return tracks[0]["uri"]
        
        return None
    except Exception as e:
        print(f"❌ Error searching track '{artist} - {title}': {e}")
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

# Additional utility functions needed by the new engine

def search_spotify_tracks_enhanced_with_duration(genre, headers, target_duration_minutes=30, 
                                                max_tracks=100, mood_tags=None, 
                                                search_keywords=None, playlist_type="clean", 
                                                favorite_artist=None):
    """
    Enhanced search with duration-based selection
    REMOVED CIRCULAR IMPORT - This function is now just a placeholder
    The new engine handles this logic internally
    """
    print(f"⚠️ search_spotify_tracks_enhanced_with_duration called - this should be handled by the new engine")
    return []

def search_artist_popular_tracks(artist_name, headers, limit=10):
    """Search for an artist's popular tracks directly on Spotify"""
    try:
        print(f"🎤 Searching for popular tracks by: {artist_name}")
        
        # First find the artist
        search_url = "https://api.spotify.com/v1/search"
        params = {
            "q": f"artist:\"{artist_name}\"",
            "type": "artist",
            "limit": 1
        }
        
        res = requests.get(search_url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"❌ Artist search failed: {res.status_code}")
            return []
        
        data = res.json()
        artists = data.get("artists", {}).get("items", [])
        if not artists:
            print(f"❌ Artist not found: {artist_name}")
            return []
        
        artist_id = artists[0]["id"]
        print(f"✅ Found artist {artist_name} with ID: {artist_id}")
        
        # Get artist's top tracks
        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
        params = {"market": "US"}
        
        res = requests.get(top_tracks_url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"❌ Top tracks request failed: {res.status_code}")
            return []
        
        data = res.json()
        tracks = data.get("tracks", [])
        
        track_uris = []
        for track in tracks[:limit]:
            if isinstance(track, dict) and "uri" in track:
                track_uris.append(track["uri"])
        
        print(f"✅ Found {len(track_uris)} popular tracks for {artist_name}")
        return track_uris
        
    except Exception as e:
        print(f"❌ Error searching artist popular tracks: {e}")
        return []

def extract_tracks_from_search(search_response, playlist_type="clean"):
    """Extract track URIs from Spotify search response"""
    tracks = []
    
    try:
        if not isinstance(search_response, dict):
            return tracks
        
        tracks_data = search_response.get("tracks", {})
        if not isinstance(tracks_data, dict):
            return tracks
        
        items = tracks_data.get("items", [])
        if not isinstance(items, list):
            return tracks
        
        for track in items:
            if not isinstance(track, dict):
                continue
            
            # Check explicit content
            is_explicit = track.get("explicit", False)
            if playlist_type.lower() == "clean" and is_explicit:
                continue
            elif playlist_type.lower() == "explicit" and not is_explicit:
                continue
            
            # Get track URI
            track_uri = track.get("uri")
            if track_uri and track_uri.startswith("spotify:track:"):
                tracks.append(track_uri)
        
        return tracks
        
    except Exception as e:
        print(f"❌ Error extracting tracks from search: {e}")
        return tracks
    
def fetch_user_playback_data(headers):
    endpoints = {
        "top_artists": "https://api.spotify.com/v1/me/top/artists?limit=10&time_range=medium_term",
        "top_tracks": "https://api.spotify.com/v1/me/top/tracks?limit=10&time_range=medium_term",
        "recently_played": "https://api.spotify.com/v1/me/player/recently-played?limit=10",
        "saved_tracks": "https://api.spotify.com/v1/me/tracks?limit=10",
        "playlists": "https://api.spotify.com/v1/me/playlists?limit=10"
    }

    data = {}
    for key, url in endpoints.items():
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                data[key] = r.json()
        except Exception as e:
            print(f"❌ Error fetching {key}: {e}")
    return data
    