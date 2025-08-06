import os
import json
import datetime
import time
import base64
import requests

# Use your existing Firebase initialization instead of creating a new one
from firebase_admin_init import db

# Spotify credential environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://example.com/callback")

def get_spotify_access_token():
    """Get system/app access token for MoodQue"""
    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": SPOTIFY_REFRESH_TOKEN
    }
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)

    if response.status_code != 200:
        print("❌ Failed to refresh app access token", response.text)
        raise Exception("Spotify token refresh failed")

    token_info = response.json()
    return token_info["access_token"]

def refresh_token_with_spotify(refresh_token):
    """Refresh a user's token with Spotify API"""
    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
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
        print("❌ Failed to refresh user token", response.text)
        raise Exception("Spotify user token refresh failed")

    token_data = response.json()
    return {
        "access_token": token_data["access_token"],
        "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(seconds=token_data["expires_in"])).isoformat()
    }

def refresh_access_token(user_id=None):
    """
    Refresh the Spotify access token for a given user using their stored refresh token.
    Checks expiry and only refreshes if needed.
    """
    if not user_id:
        raise ValueError("A user_id must be provided to refresh the access token.")

    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
        raise ValueError(f"User {user_id} not found in Firestore.")

    user_data = user_doc.to_dict()
    refresh_token = user_data.get("spotify_refresh_token")
    if not refresh_token:
        raise ValueError(f"No refresh token found for user {user_id}.")

    # Check if the current token is still valid
    try:
        expires_at = float(user_data.get("spotify_token_expires_at", 0))
    except (ValueError, TypeError):
        expires_at = 0

    if expires_at > time.time():
        return user_data.get("spotify_access_token")

    # Refresh the token with Spotify
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
    }

    r = requests.post(token_url, data=payload)
    r.raise_for_status()
    token_data = r.json()

    # Update Firestore with new token and expiry
    user_data["spotify_access_token"] = token_data["access_token"]
    user_data["spotify_token_expires_at"] = str(time.time() + token_data.get("expires_in", 3600))

    # Only update refresh token if Spotify provided a new one
    if "refresh_token" in token_data and token_data["refresh_token"]:
        user_data["spotify_refresh_token"] = token_data["refresh_token"]

    db.collection("users").document(user_id).set(user_data, merge=True)

    return token_data["access_token"]

def get_user_access_token(user_id):
    """
    Get a valid access token for the user, refreshing if necessary
    """
    return refresh_access_token(user_id)

def is_user_connected(user_id):
    """
    Check if user has valid Spotify connection
    """
    try:
        if not user_id or user_id == 'unknown':
            return False
            
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        user_data = doc.to_dict()
        return bool(user_data.get("spotify_refresh_token"))
        
    except Exception as e:
        print(f"❌ Error checking user connection: {e}")
        return False

def revoke_user_tokens(user_id):
    """
    Revoke and clear user tokens from database
    """
    try:
        db.collection("users").document(user_id).update({
            "spotify_access_token": None,
            "spotify_refresh_token": None,
            "spotify_token_expires_at": None,
            "spotify_token_expiry": None,  # Clear old field name too
            "tokens_revoked_at": datetime.datetime.now().isoformat()
        })
        print(f"✅ Revoked tokens for user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error revoking tokens for user {user_id}: {e}")
        return False

def get_user_spotify_info(user_id):
    """
    Get user's Spotify profile information
    """
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            user_data = doc.to_dict()
            return {
                "spotify_user_id": user_data.get("spotify_user_id"),
                "spotify_display_name": user_data.get("spotify_display_name"),
                "connected_at": user_data.get("connected_at"),
                "is_connected": bool(user_data.get("spotify_refresh_token"))
            }
        return None
    except Exception as e:
        print(f"❌ Error getting user Spotify info: {e}")
        return None
    
def get_user_top_data(user_id, time_range="medium_term", limit=20):
    """
    Fetch a user's top artists, tracks, and genres from Spotify using their stored refresh token.
    Uses existing refresh_access_token() to ensure a valid token.
    Returns a dict with 'artists', 'tracks', and 'genres'.
    """
    token = refresh_access_token(user_id)
    if not token:
        raise ValueError(f"Could not get a valid access token for user {user_id}")

    headers = {"Authorization": f"Bearer {token}"}

    def spotify_get(endpoint, params=None):
        url = f"https://api.spotify.com/v1/{endpoint}"
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()

    # Get top artists
    artists_data = spotify_get("me/top/artists", {"time_range": time_range, "limit": limit})
    artist_names = [artist["name"] for artist in artists_data.get("items", [])]

    genres = {}
    for artist in artists_data.get("items", []):
        for genre in artist.get("genres", []):
            genres[genre] = genres.get(genre, 0) + 1

    # Get top tracks
    tracks_data = spotify_get("me/top/tracks", {"time_range": time_range, "limit": limit})
    track_names = [track["name"] for track in tracks_data.get("items", [])]

    return {
        "artists": artist_names,
        "tracks": track_names,
        "genres": genres
    }
