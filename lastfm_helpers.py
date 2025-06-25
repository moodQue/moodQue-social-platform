import os
import requests
from dotenv import load_dotenv

load_dotenv()  # <-- Make sure this is called at the top level

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
print(f"🔑 Last.fm API Key loaded: {LASTFM_API_KEY is not None}")



def get_similar_artists(artist_name, limit=5):
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name,  # Do NOT pre-encode
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    res = requests.get(url, params=params)
    print("🧪 RAW Last.fm response:", res.status_code, res.text)
    if res.status_code == 200:
     artists = [a["name"] for a in res.json().get("similarartists", {}).get("artist", [])]
    if not artists:
        print("⚠️ No similar artists found. Falling back to favorite_artist only.")
        return [artist_name] if artist_name else []
    return artists



def get_top_tracks(artist_name, limit=5):
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.gettoptracks",
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    res = requests.get(url, params=params)
    if res.status_code == 200:
        return [(t["name"], artist_name) for t in res.json().get("toptracks", {}).get("track", [])]
    return []
