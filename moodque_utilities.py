import os
import base64
import requests
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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

def create_robust_session():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    
    # Define retry strategy
    retry_strategy = Retry(
        total=3,  # Total number of retries
        backoff_factor=1,  # Wait time between retries (1, 2, 4 seconds)
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry
        allowed_methods=["HEAD", "GET", "OPTIONS"]  # Only retry safe methods
    )
    
    # Mount adapter with retry strategy
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def search_spotify_track_robust(artist, title, headers, playlist_type="clean", max_retries=3):
    """
    Enhanced Spotify search with robust error handling and retries
    """
    import re

    def clean_text(text):
        # Remove content inside parentheses or brackets, normalize
        text = re.sub(r"\(.*?\)|\[.*?\]", "", text)
        text = text.replace("feat.", "").replace("featuring", "")
        return text.strip().lower()

    if not artist or not title or not headers:
        print("❌ Missing required parameters for Spotify search")
        return None

    cleaned_title = clean_text(title)
    cleaned_artist = clean_text(artist)

    # Create robust session
    session = create_robust_session()

    base_queries = [
        f'track:"{title}" artist:"{artist}"',
        f'{title} {artist}',
        f'track:{title} artist:{artist}',
        f'{artist} {title}'
    ]

    for attempt in range(max_retries):
        for query_idx, query in enumerate(base_queries):
            try:
                print(f"🔍 Attempt {attempt + 1}/{max_retries}, Query {query_idx + 1}/{len(base_queries)}: '{query[:50]}...'")
                
                params = {
                    "q": query, 
                    "type": "track", 
                    "limit": 10, 
                    "market": "US"
                }
                
                # Use session with shorter timeout
                response = session.get(
                    "https://api.spotify.com/v1/search", 
                    headers=headers, 
                    params=params,
                    timeout=(5, 10)  # (connect timeout, read timeout)
                )

                if response.status_code == 200:
                    data = response.json()
                    tracks = data.get("tracks", {}).get("items", [])
                    
                    for track in tracks:
                        # Check if track matches our search criteria
                        t_name = clean_text(track.get("name", ""))
                        t_artist = clean_text(track.get("artists", [{}])[0].get("name", ""))
                        is_explicit = track.get("explicit", False)
                        
                        # Verify this is the right track
                        if cleaned_title in t_name and cleaned_artist in t_artist:
                            # Apply content filter
                            if playlist_type.lower() == "clean" and is_explicit:
                                print(f"⚠️ Skipping explicit track: '{track.get('name')}' by '{track.get('artists', [{}])[0].get('name')}'")
                                continue
                            elif playlist_type.lower() == "explicit" and not is_explicit:
                                print(f"⚠️ Skipping clean track: '{track.get('name')}' by '{track.get('artists', [{}])[0].get('name')}'")
                                continue
                            
                            # Found a matching track that passes content filter
                            content_type = "explicit" if is_explicit else "clean"
                            print(f"✅ Found {content_type} track: '{track.get('name')}' by '{track.get('artists', [{}])[0].get('name')}'")
                            return track["uri"]
                
                elif response.status_code == 429:
                    # Rate limited - wait longer
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"⏳ Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                    
                elif response.status_code in [401, 403]:
                    print(f"🔐 Authentication error: {response.status_code}")
                    return None  # Don't retry auth errors
                    
                else:
                    print(f"⚠️ Spotify API returned status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout on attempt {attempt + 1} for query '{query[:30]}...'")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                continue
                
            except requests.exceptions.ConnectionError as e:
                print(f"🌐 Connection error on attempt {attempt + 1}: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                continue
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Request exception: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue
                
            except Exception as e:
                print(f"💥 Unexpected error: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

    print(f"❌ Failed to find {playlist_type} match for '{title}' by '{artist}' after {max_retries} attempts")
    return None

# Batch processing function to handle multiple tracks efficiently
def batch_search_spotify_tracks(track_list, headers, playlist_type="clean", batch_size=5):
    """
    Process tracks in batches with delays to avoid overwhelming the API
    """
    found_tracks = []
    failed_tracks = []
    
    print(f"🔄 Processing {len(track_list)} tracks in batches of {batch_size}")
    
    for i in range(0, len(track_list), batch_size):
        batch = track_list[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(track_list) + batch_size - 1) // batch_size
        
        print(f"📦 Processing batch {batch_num}/{total_batches}")
        
        for track_info in batch:
            if isinstance(track_info, dict):
                artist = track_info.get("artist", "")
                track_name = track_info.get("track", "")
            else:
                print(f"⚠️ Skipping invalid track format: {track_info}")
                continue
            
            if not artist or not track_name:
                continue
            
            try:
                track_uri = search_spotify_track_robust(
                    artist, track_name, headers, playlist_type
                )
                
                if track_uri:
                    found_tracks.append({
                        "uri": track_uri,
                        "artist": artist,
                        "track": track_name
                    })
                else:
                    failed_tracks.append({
                        "artist": artist,
                        "track": track_name,
                        "reason": "not_found"
                    })
                    
            except Exception as e:
                print(f"❌ Error processing '{track_name}' by '{artist}': {e}")
                failed_tracks.append({
                    "artist": artist,
                    "track": track_name,
                    "reason": str(e)
                })
        
        # Small delay between batches
        if batch_num < total_batches:
            print("⏳ Brief pause between batches...")
            time.sleep(1)
    
    print(f"✅ Batch processing complete: {len(found_tracks)} found, {len(failed_tracks)} failed")
    return found_tracks, failed_tracks

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
    
def bulk_search_spotify_tracks(track_list, headers):
    """
    Try to find matching Spotify URIs for a list of Last.fm tracks.
    Each track should be a dict with 'artist' and 'track' keys.
    """
    from moodque_utilities import search_spotify_track

    matches = []
    not_found = []

    for track in track_list:
        artist = track.get("artist")
        title = track.get("track")

        if not artist or not title:
            continue

        uri = search_spotify_track(artist, title, headers)

        if uri:
            track["spotify_uri"] = uri
            matches.append(track)
        else:
            not_found.append(track)

    print(f"🔎 Bulk search complete: {len(matches)} found, {len(not_found)} not found")
    return matches

def find_spotify_track_id(track_name, artist_name, access_token):
    query = f"track:{track_name} artist:{artist_name}"
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": query, "type": "track", "limit": 1, "market": "US"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json()
        items = results.get("tracks", {}).get("items", [])
        if items:
            return items[0]["id"]
    return None