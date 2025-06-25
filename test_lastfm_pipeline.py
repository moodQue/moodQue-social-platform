import os
from dotenv import load_dotenv
import requests

from lastfm_helpers import get_similar_artists, get_top_tracks
from moodque_engine import build_smart_playlist_enhanced
from moodque_utilities import refresh_access_token
load_dotenv()

def search_spotify_track(artist, title, headers):
    query = f"{artist} {title}"
    params = {
        "q": query,
        "type": "track",
        "limit": 1
    }
    res = requests.get("https://api.spotify.com/v1/search", headers=headers, params=params)
    if res.status_code == 200:
        items = res.json().get("tracks", {}).get("items", [])
        if items:
            return items[0]["uri"]
    return None

# === RUN TEST ===

seed_artist = "Taylor Swift"
print(f"🔍 Getting similar artists to: {seed_artist}")
similar_artists = get_similar_artists(seed_artist)
print("🎯 Similar artists found:", similar_artists)

# Get top tracks for top 3 similar artists
track_candidates = []
for artist in similar_artists[:3]:
    track_candidates += get_top_tracks(artist, limit=2)

print(f"\n🧪 Candidate tracks to search on Spotify: {len(track_candidates)}")

# Refresh token and search Spotify
access_token = refresh_access_token()
headers = {"Authorization": f"Bearer {access_token}"}

track_uris = []
for title, artist in track_candidates:
    uri = search_spotify_track(artist, title, headers)
    if uri:
        print(f"✅ Found: {title} by {artist} → {uri}")
        track_uris.append(uri)
    else:
        print(f"❌ Not found: {title} by {artist}")

print(f"\n✅ Total Spotify URIs found: {len(track_uris)}")
