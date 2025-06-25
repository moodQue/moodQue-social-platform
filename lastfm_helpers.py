import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")

def get_similar_artists(artist_name, limit=5):
    """Fetch similar artists from Last.fm"""
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    res = requests.get(url, params=params)
    print("🔎 RAW Last.fm response:", res.status_code, res.text)
    if res.status_code == 200:
        try:
            return [a["name"] for a in res.json().get("similarartists", {}).get("artist", [])]
        except Exception as e:
            print(f"⚠️ Failed to parse similar artists: {e}")
    return []

def get_top_tracks(artist_name, limit=5):
    """Get top tracks for a given artist from Last.fm"""
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.gettoptracks",
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            raw = res.json()
            return [(t["name"], artist_name) for t in raw.get("toptracks", {}).get("track", []) if isinstance(t, dict) and "name" in t]
    except Exception as e:
        print(f"❌ Error fetching top tracks for {artist_name}: {e}")
    return []
