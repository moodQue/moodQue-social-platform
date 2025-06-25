import os
import requests
from dotenv import load_dotenv

load_dotenv()  # <-- Make sure this is called at the top level

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
print(f"🔑 Last.fm API Key loaded: {LASTFM_API_KEY is not None}")



def get_similar_artists(artist_name, limit=5):
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    res = requests.get("https://ws.audioscrobbler.com/2.0/", params=params)
    print("📡 RAW Last.fm response:", res.status_code, res.text)
    try:
        data = res.json()
        artists = data.get("similarartists", {}).get("artist", [])
        return [a["name"] for a in artists if "name" in a]
    except Exception as e:
        print(f"⚠️ Error parsing similar artists: {e}")
        return []




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
