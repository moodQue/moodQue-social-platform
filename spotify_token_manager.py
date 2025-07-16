import os
import json
import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Load Firebase credentials from escaped JSON string in Railway
def init_firestore():
    firebase_admin_json = os.getenv("FIREBASE_ADMIN_JSON")
    if not firebase_admin_json:
        raise RuntimeError("FIREBASE_ADMIN_JSON not found in environment variables")

    firebase_creds_dict = json.loads(firebase_admin_json)
    cred = credentials.Certificate(firebase_creds_dict)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    return firestore.client()

# Firestore client
db = init_firestore()

# Spotify credential environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://example.com/callback")

import base64
import requests

def get_spotify_access_token():
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
    if user_id:
        try:
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
                access_token = user_data.get("spotify_access_token")
                refresh_token = user_data.get("spotify_refresh_token")
                token_expiry = user_data.get("spotify_token_expiry")

                if access_token and token_expiry:
                    expiry_time = datetime.datetime.fromisoformat(token_expiry)
                    if expiry_time > datetime.datetime.utcnow():
                        return access_token

                new_token_data = refresh_token_with_spotify(refresh_token)
                doc_ref.update({
                    "spotify_access_token": new_token_data["access_token"],
                    "spotify_token_expiry": new_token_data["expires_at"]
                })
                return new_token_data["access_token"]

        except Exception as e:
            print(f"⚠️ Error refreshing user token from Firestore: {e}")

    return get_spotify_access_token()
