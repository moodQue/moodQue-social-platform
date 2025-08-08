# Complete moodque_auth.py - Updated with callback route removed to avoid conflicts

import os
import base64
import json
import datetime
import time
import urllib.parse
import requests
from dotenv import load_dotenv
from datetime import datetime

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
SCOPES = (
    "playlist-modify-private "
    "playlist-modify-public "
    "user-read-private "
    "user-read-email "
    "user-top-read "
    "user-library-read "
    "user-read-recently-played"
)

def init_firebase_app():
    """
    Initializes Firebase Admin SDK.
    Only runs once.
    """
    if not firebase_admin._apps:
        try:
            # Check if we're in a Railway environment with JSON in env
            if "FIREBASE_CREDENTIALS_JSON" in os.environ:
                print("🔥 Loading Firebase credentials from FIREBASE_CREDENTIALS_JSON")
                service_account_info = json.loads(os.environ["FIREBASE_CREDENTIALS_JSON"])
                cred = credentials.Certificate(service_account_info)
            elif "FIREBASE_ADMIN_JSON" in os.environ:
                print("🔥 Loading Firebase credentials from FIREBASE_ADMIN_JSON")
                service_account_info = json.loads(os.environ["FIREBASE_ADMIN_JSON"])
                cred = credentials.Certificate(service_account_info)
            else:
                # Fallback to local file if not in Railway
                print("🔥 Loading Firebase credentials from local file")
                cred_path = os.path.join("config", "firebase_credentials.json")
                cred = credentials.Certificate(cred_path)
            
            firebase_admin.initialize_app(cred)
            print("✅ Firebase initialized successfully in moodque_auth")
        except Exception as e:
            print(f"❌ Firebase initialization failed in moodque_auth: {e}")
            raise

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
        "expires_at": (datetime.utcnow() + datetime.timedelta(seconds=token_data["expires_in"])).isoformat()
    }

@auth_bp.route("/login")
def login():
    """Generate Spotify authorization URL with enhanced state handling"""
    
    # Get optional parameters from query string
    user_email = request.args.get('user_email', '')
    return_url = request.args.get('return_url', 'https://moodque.glide.page')
    
    # Create state parameter with user context
    state_params = {}
    if user_email:
        state_params['user_email'] = user_email
    if return_url:
        state_params['return_url'] = return_url
    
    # Encode state as URL parameters
    state = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in state_params.items()])
    
    query_params = {
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "show_dialog": "true",
        "state": state
    }
    
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(query_params)
    print(f"🔗 Generated Spotify auth URL: {auth_url}")
    
    return redirect(auth_url)

# REMOVED: The callback route is now handled in moodQueSocial_webhook_service.py 
# to avoid conflicts and provide better error handling

@auth_bp.route("/test_auth_flow")
def test_auth_flow():
    """Test endpoint to check auth flow configuration"""
    return jsonify({
        "status": "auth_flow_test",
        "client_id_present": bool(SPOTIFY_CLIENT_ID),
        "client_secret_present": bool(SPOTIFY_CLIENT_SECRET),
        "refresh_token_present": bool(SPOTIFY_REFRESH_TOKEN),
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scopes": SCOPES.split(),
        "callback_note": "Callback is handled in main webhook service"
    })

@auth_bp.route("/generate_auth_url")
def generate_auth_url():
    """Generate auth URL without redirecting - useful for testing"""
    
    user_email = request.args.get('user_email', 'test@example.com')
    return_url = request.args.get('return_url', 'https://moodque.glide.page')
    
    state_params = {
        'user_email': user_email,
        'return_url': return_url,
        'test': 'true'
    }
    
    state = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in state_params.items()])
    
    query_params = {
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "show_dialog": "true",
        "state": state
    }
    
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(query_params)
    
    return jsonify({
        "status": "success",
        "auth_url": auth_url,
        "state_params": state_params,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "instructions": "Use this URL to test the OAuth flow"
    })