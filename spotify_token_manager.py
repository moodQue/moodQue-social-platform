# spotify_token_manager.py

import datetime
import requests
from google.cloud import firestore
from google.oauth2 import service_account
import os

# Initialize Firebase credentials
from firebase_admin_init import init_firebase_app
init_firebase_app()
db = firestore.Client()

# Constants from env
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

def save_user_tokens(user_id, access_token, refresh_token, expires_in):
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at.isoformat(),
        "connected": True
    }
    db.collection("users").document(user_id).collection("spotify_tokens").document("latest").set(token_data)


def get_user_tokens(user_id):
    doc = db.collection("users").document(user_id).collection("spotify_tokens").document("latest").get()
    return doc.to_dict() if doc.exists else None


def is_token_expired(expires_at_str):
    expires_at = datetime.datetime.fromisoformat(expires_at_str)
    return datetime.datetime.utcnow() > expires_at


def refresh_access_token(user_id):
    tokens = get_user_tokens(user_id)
    if not tokens:
        raise Exception("No Spotify tokens found for user")

    if not is_token_expired(tokens["expires_at"]):
        return tokens["access_token"]  # still valid

    refresh_token = tokens["refresh_token"]

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        raise Exception("Failed to refresh Spotify access token")

    new_data = response.json()
    new_access_token = new_data["access_token"]
    expires_in = new_data.get("expires_in", 3600)

    # update Firestore
    save_user_tokens(user_id, new_access_token, refresh_token, expires_in)
    return new_access_token
