import os
import base64
import json
import datetime
import time
import urllib.parse
import requests
import urllib.parse
from dotenv import load_dotenv
load_dotenv()

from flask import Blueprint, request, jsonify, redirect
import firebase_admin
from firebase_admin import credentials, firestore

auth_bp = Blueprint("auth", __name__)

# Constants
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://example.com/callback")
SCOPES = "playlist-modify-private playlist-modify-public user-read-private user-read-email"
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

@auth_bp.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No code provided"}), 400

    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        return jsonify({"error": "Token exchange failed", "details": response.text}), 400

    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    # Use the access token to get the Spotify user ID
    user_profile_resp = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if user_profile_resp.status_code != 200:
        return jsonify({"error": "Failed to get user profile", "details": user_profile_resp.text}), 400

    user_profile = user_profile_resp.json()
    user_id = user_profile["id"]

    # Store tokens in Firestore
    db.collection("users").document(user_id).set({
        "spotify_access_token": access_token,
        "spotify_refresh_token": refresh_token,
        "spotify_token_expires_at": str(time.time() + int(expires_in))
    }, merge=True)

    return jsonify({
        "message": f"Spotify linked successfully for user {user_id}",
        "user_id": user_id
    })