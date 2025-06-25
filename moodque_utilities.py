import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")


def refresh_access_token():
    url = "https://accounts.spotify.com/api/token"
    client_creds = f"{client_id}:{client_secret}"
    client_creds_b64 = base64.b64encode(client_creds.encode()).decode()

    headers = {
        "Authorization": f"Basic {client_creds_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    res = requests.post(url, headers=headers, data=payload)
    if res.status_code != 200:
        print("❌ Error refreshing token:", res.json())
        exit()
    return res.json()["access_token"]


def get_spotify_user_id(headers):
    res = requests.get("https://api.spotify.com/v1/me", headers=headers)
    return res.json().get("id")


def create_new_playlist(user_id, headers, name, description=""):
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    data = {
        "name": name,
        "description": description,
        "public": False
    }
    res = requests.post(url, headers=headers, json=data)
    if res.status_code == 201:
        return res.json()["id"]
    else:
        raise Exception(f"Failed to create playlist: {res.json()}")



def add_tracks_to_playlist(headers, playlist_id, track_uris):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    
    # Ensure track_uris is a list of strings
    if isinstance(track_uris, list):
        track_uris = [t["uri"] if isinstance(t, dict) else t for t in track_uris]

    payload = {"uris": track_uris}
    res = requests.post(url, headers=headers, json=payload)

    if res.status_code != 201:
        print(f"❌ Error adding tracks: {res.status_code} {res.text}")
    else:
        print(f"✅ Successfully added {len(track_uris)} tracks to playlist")


def parse_genre_list(raw_genres):
    return [g.strip().lower() for g in raw_genres.split(",") if g.strip()]


def sanitize_genre(genre):
    genre = genre.lower().strip()
    mapping = {
        "hip hop": "hip-hop",
        "r&b": "r-n-b",
        "electro": "electronic",
        "alt": "alternative"
    }
    return mapping.get(genre, genre)


def get_artist_ids(artist_name, headers):
    url = f"https://api.spotify.com/v1/search"
    params = {"q": artist_name, "type": "artist", "limit": 1}
    res = requests.get(url, headers=headers, params=params)
    items = res.json().get("artists", {}).get("items", [])
    return [items[0]["id"]] if items else []


def get_enhanced_mood_values(mood_tags):
    values = {}
    tags = [tag.strip().lower() for tag in mood_tags.split(",")]
    if "happy" in tags:
        values["valence"] = 0.9
    if "chill" in tags:
        values["energy"] = 0.3
    if "party" in tags:
        values["energy"] = 0.95
        values["danceability"] = 0.95
    return values


def get_recommendations_enhanced(headers, limit, seed_genres, seed_artists, mood_params):
    url = "https://api.spotify.com/v1/recommendations"
    params = {
        "limit": limit,
        "seed_genres": ",".join(seed_genres[:2]),
    }
    if seed_artists:
        params["seed_artists"] = ",".join(seed_artists[:2])
    params.update(mood_params)
    res = requests.get(url, headers=headers, params=params)
    return [{"uri": t["uri"]} for t in res.json().get("tracks", [])]


def search_spotify_tracks_fallback(seed_genre, headers, limit, mood_tags, search_keywords, playlist_type):
    query = f"{search_keywords or seed_genre}"
    url = "https://api.spotify.com/v1/search"
    params = {"q": query, "type": "track", "limit": limit}
    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        return [{"uri": t["uri"]} for t in data.get("tracks", {}).get("items", []) if isinstance(t, dict)]
    except Exception as e:
        print(f"❌ Fallback search error: {e}")
        return []



def search_spotify_track(artist, title, headers):
    query = f"track:{title} artist:{artist}"
    url = "https://api.spotify.com/v1/search"
    params = {"q": query, "type": "track", "limit": 1}
    res = requests.get(url, headers=headers, params=params)
    tracks = res.json().get("tracks", {}).get("items", [])
    return tracks[0]["uri"] if tracks else None


def remove_duplicates_and_filter(track_list, headers):
    seen = set()
    result = []
    for item in track_list:
        uri = item["uri"]
        if uri not in seen:
            seen.add(uri)
            result.append(item)
    return result


def filter_explicit_content(tracks, headers, playlist_type):
    if playlist_type == "explicit":
        return tracks
    filtered = []
    for t in tracks:
        track_id = t["uri"].split(":")[-1]
        res = requests.get(f"https://api.spotify.com/v1/tracks/{track_id}", headers=headers)
        if res.status_code == 200 and not res.json().get("explicit"):
            filtered.append(t)
    return filtered
