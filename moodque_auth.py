# Add this import at the top of moodque_auth.py

import os
import base64
import json
import datetime
import time
import urllib.parse
import requests
from dotenv import load_dotenv
from datetime import datetime  # ADD THIS LINE - was missing!

load_dotenv()

from flask import Blueprint, request, jsonify, redirect
import firebase_admin
from firebase_admin import credentials, firestore

# Rest of your existing moodque_auth.py code remains the same...

auth_bp = Blueprint("auth", __name__)

# Constants
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://example.com/callback")
SCOPES = (
    "playlist-modify-private "
    "playlist-modify-public "
    "user-read-private "
    "user-read-email "
    "user-top-read"
)

#update scopes moodque auth
def init_firebase_app():
    """
    Initializes Firebase Admin SDK.
    Only runs once.
    """
    if not firebase_admin._apps:
        # Check if we're in a Railway environment with JSON in env
        if "FIREBASE_CREDENTIALS_JSON" in os.environ:
            service_account_info = json.loads(os.environ["FIREBASE_CREDENTIALS_JSON"])
            cred = credentials.Certificate(service_account_info)
        else:
            # Fallback to local file if not in Railway
            cred_path = os.path.join("config", "firebase_credentials.json")
            cred = credentials.Certificate(cred_path)
        
        firebase_admin.initialize_app(cred)

# Initialize Firebase before creating the client
init_firebase_app()
db = firestore.client()

def get_spotify_access_token():
    """
    Fetches a new access token using the app's stored refresh token.
    """
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
    """
    Refresh a user's Spotify token using their refresh_token.
    Returns a dict with access_token and expires_at.
    """
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

@auth_bp.route("/login")
def login():
    query_params = {
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "show_dialog": "true"
    }
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(query_params)
    return redirect(auth_url)

# Update your callback function in moodque_auth.py or webhook service

@auth_bp.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state", "")
    
    if not code:
        # Redirect back to Glide with error
        return redirect("https://moodque.glide.page?spotify_error=no_code")

    # Parse state to get user info and return URL
    state_params = {}
    if state:
        for param in state.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                state_params[key] = urllib.parse.unquote(value)
    
    user_id = state_params.get("user_id", "anonymous")
    return_url = state_params.get("return_url", "https://moodque.glide.page")

    # Exchange code for tokens
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("SPOTIFY_REDIRECT_URI"),
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        # Redirect back to Glide with error
        return redirect(f"{return_url}?spotify_error=token_failed")

    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    new_scopes = set(token_data.get("scope", "").split())

    # Get Spotify user profile
    user_profile_resp = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if user_profile_resp.status_code != 200:
        # Redirect back to Glide with error
        return redirect(f"{return_url}?spotify_error=profile_failed")

    spotify_user = user_profile_resp.json()
    spotify_user_id = spotify_user["id"]
    spotify_display_name = spotify_user.get("display_name", spotify_user_id)

    try:
        # Get any existing user data
        user_doc_ref = db.collection("users").document(spotify_user_id)
        existing_data = {}
        existing_doc = user_doc_ref.get()
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()

        # Always update access token and expiry
        existing_data["spotify_access_token"] = access_token
        existing_data["spotify_token_expires_at"] = str(time.time() + token_data.get("expires_in", 3600))

        # Only overwrite refresh token if we got a new one
        if refresh_token:
            existing_data["spotify_refresh_token"] = refresh_token

        # Merge scopes
        existing_scopes = set(existing_data.get("spotify_scopes", "").split())
        merged_scopes = existing_scopes.union(new_scopes)
        existing_data["spotify_scopes"] = " ".join(sorted(merged_scopes))

        # Always store display name and IDs
        existing_data["glide_user_id"] = user_id
        existing_data["spotify_user_id"] = spotify_user_id
        existing_data["spotify_display_name"] = spotify_display_name
        existing_data["connected_at"] = datetime.now().isoformat()

        # Save back to Firestore
        user_doc_ref.set(existing_data, merge=True)
        
        print(f"✅ Spotify connected for Glide user {user_id} -> Spotify user {spotify_user_id}")

        # Redirect back to Glide with success info
        success_params = {
            "spotify_connected": "true",
            "spotify_user": spotify_user_id,
            "spotify_name": spotify_display_name,
            "connection_status": "success"
        }
        
        success_url = f"{return_url}?" + "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in success_params.items()])
        return redirect(success_url)

    except Exception as e:
        print(f"❌ Error saving to Firebase: {e}")
        return redirect(f"{return_url}?spotify_error=database_failed")
