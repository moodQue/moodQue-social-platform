import os
import requests
from dotenv import load_dotenv

load_dotenv('.env')  # Make sure this points to your .env file

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

def get_access_token():
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": SPOTIFY_REFRESH_TOKEN
        },
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
    )
    response.raise_for_status()
    return response.json()["access_token"]

def search_spotify(query, access_token):
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "q": query,
        "type": "track",
        "limit": 1,
        "market": "US"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    results = response.json()
    if results["tracks"]["items"]:
        track = results["tracks"]["items"][0]
        print(f"✅ Found: {track['name']} by {track['artists'][0]['name']}")
    else:
        print("❌ No results found.")

if __name__ == "__main__":
    token = get_access_token()
    search_spotify("Doxy Miles Davis", token)
