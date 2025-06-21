import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Will use Railway env vars or local .env/.env.production

def get_access_token():
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not all([refresh_token, client_id, client_secret]):
        raise ValueError("Missing one or more Spotify credentials.")

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        },
        headers={
            "Authorization": f"Basic {requests.auth._basic_auth_str(client_id, client_secret)}"
        }
    )

    if response.ok:
        return response.json()["access_token"]
    else:
        raise Exception(f"Token refresh failed: {response.text}")
