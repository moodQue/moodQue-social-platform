import os
import requests
import urllib.parse
import os
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Blueprint, redirect, request, jsonify
from firebase_admin import firestore
from firebase_admin_init import init_firebase_app

auth_bp = Blueprint("auth", __name__)

# Ensure Firebase is initialized
init_firebase_app()

db = firestore.client()

def get_spotify_access_token(user_id):
    """
    Retrieves stored Spotify access token for the given user_id.
    Returns None if no token found or if expired.
    """
    try:
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            token = user_data.get("spotify_access_token")
            token_expiry = user_data.get("spotify_token_expires_at")

            # Optionally check for expiration (if stored)
            if token and token_expiry:
                import time
                if time.time() < float(token_expiry):
                    return token
                else:
                    print(f"⚠️ Token for user {user_id} is expired.")
                    return None
            return token
        else:
            print(f"❌ No user found with ID: {user_id}")
            return None
    except Exception as e:
        print(f"🔥 Error retrieving token for user {user_id}: {e}")
        return None

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPES = "playlist-modify-public playlist-modify-private"

def init_firebase_app():
    """
    Initializes Firebase Admin SDK.
    Only runs once.
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate("config/firebase_credentials.json")
        firebase_admin.initialize_app(cred)
        
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
    return jsonify({
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "token_type": token_data.get("token_type"),
        "scope": token_data.get("scope"),
    })
