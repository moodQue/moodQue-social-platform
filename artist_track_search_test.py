import requests
import os
from dotenv import load_dotenv

load_dotenv(".env")  # Make sure your Spotify credentials are in a .env file

SPOTIFY_TOKEN = os.getenv("SPOTIFY_TOKEN")  # Your valid token
HEADERS = {
    "Authorization": f"Bearer {SPOTIFY_TOKEN}"
}


def get_artist_id(artist_name):
    query = f"https://api.spotify.com/v1/search?q={artist_name}&type=artist&limit=1"
    response = requests.get(query, headers=HEADERS)
    data = response.json()

    if data.get("artists", {}).get("items"):
        artist = data["artists"]["items"][0]
        print(f"[ARTIST FOUND] {artist['name']} → {artist['id']}")
        return artist["id"]
    else:
        print(f"[ARTIST NOT FOUND] {artist_name}")
        return None


def search_track_by_artist_id(track_title, artist_id):
    query = f"https://api.spotify.com/v1/search?q=track:{track_title}+artist:{artist_id}&type=track&limit=5"
    response = requests.get(query, headers=HEADERS)
    data = response.json()

    if data.get("tracks", {}).get("items"):
        print(f"\n[TRACK RESULTS for '{track_title}']:\n")
        for track in data["tracks"]["items"]:
            name = track["name"]
            artist = track["artists"][0]["name"]
            uri = track["uri"]
            print(f"🎵 {name} by {artist} — URI: {uri}")
        return data["tracks"]["items"]
    else:
        print(f"[TRACK NOT FOUND] {track_title}")
        return []


if __name__ == "__main__":
    # 🔁 Test inputs
    artist_name = "Pearl Jam"
    track_title = "Even Flow"

    artist_id = get_artist_id(artist_name)
    if artist_id:
        search_track_by_artist_id(track_title, artist_id)
