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
    try:
        res = requests.get("https://api.spotify.com/v1/me", headers=headers)
        if res.status_code == 200:
            data = res.json()
            return data.get("id")
        else:
            print(f"❌ Failed to get user ID: {res.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting user ID: {e}")
        return None


def create_new_playlist(headers, user_id, name, description=""):
    """
    Fixed parameter order: headers, user_id, name, description
    This matches how it's called in moodque_engine.py
    """
    try:
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
            print(f"❌ Failed to create playlist: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"❌ Exception creating playlist: {e}")
        return None


def add_tracks_to_playlist(headers, playlist_id, track_uris):
    """
    Add tracks to playlist with better error handling
    """
    try:
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        
        # Ensure track_uris is a list of strings
        if isinstance(track_uris, list):
            clean_uris = []
            for t in track_uris:
                if isinstance(t, dict) and "uri" in t:
                    clean_uris.append(t["uri"])
                elif isinstance(t, str) and "spotify:track:" in t:
                    clean_uris.append(t)
        else:
            clean_uris = []

        if not clean_uris:
            print("❌ No valid track URIs to add")
            return False

        payload = {"uris": clean_uris}
        res = requests.post(url, headers=headers, json=payload)

        if res.status_code == 201:
            print(f"✅ Successfully added {len(clean_uris)} tracks to playlist")
            return True
        else:
            print(f"❌ Error adding tracks: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"❌ Exception adding tracks: {e}")
        return False


def parse_genre_list(raw_genres):
    try:
        if not raw_genres:
            return ["pop"]
        return [g.strip().lower() for g in str(raw_genres).split(",") if g.strip()]
    except Exception as e:
        print(f"❌ Error parsing genres: {e}")
        return ["pop"]


def sanitize_genre(genre):
    try:
        if not genre:
            return "pop"
        genre = str(genre).lower().strip()
        mapping = {
            "hip hop": "hip-hop",
            "r&b": "r-n-b",
            "electro": "electronic",
            "alt": "alternative"
        }
        return mapping.get(genre, genre)
    except Exception as e:
        print(f"❌ Error sanitizing genre: {e}")
        return "pop"


def get_artist_ids(artist_name, headers):
    try:
        if not artist_name or not headers:
            return []
        
        url = f"https://api.spotify.com/v1/search"
        params = {"q": str(artist_name), "type": "artist", "limit": 1}
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                artists = data.get("artists", {})
                if isinstance(artists, dict):
                    items = artists.get("items", [])
                    return [items[0]["id"]] if items else []
        return []
    except Exception as e:
        print(f"❌ Error getting artist IDs: {e}")
        return []


def get_enhanced_mood_values(mood_tags):
    try:
        values = {}
        if not mood_tags:
            return values
        
        tags = [tag.strip().lower() for tag in str(mood_tags).split(",")]
        if "happy" in tags:
            values["valence"] = 0.9
        if "chill" in tags:
            values["energy"] = 0.3
        if "party" in tags:
            values["energy"] = 0.95
            values["danceability"] = 0.95
        return values
    except Exception as e:
        print(f"❌ Error getting mood values: {e}")
        return {}


def get_recommendations_enhanced(headers, limit, seed_genres, seed_artists, mood_params):
    try:
        url = "https://api.spotify.com/v1/recommendations"
        params = {
            "limit": min(limit or 20, 20),
        }
        
        if seed_genres and isinstance(seed_genres, list):
            params["seed_genres"] = ",".join(seed_genres[:2])
        
        if seed_artists and isinstance(seed_artists, list):
            params["seed_artists"] = ",".join(seed_artists[:2])
        
        if mood_params and isinstance(mood_params, dict):
            params.update(mood_params)
        
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks = data.get("tracks", [])
                return [t["uri"] for t in tracks if isinstance(t, dict) and "uri" in t]
        return []
    except Exception as e:
        print(f"❌ Error in recommendations: {e}")
        return []


def search_spotify_tracks_fallback(seed_genre, headers, limit, mood_tags, search_keywords, playlist_type):
    try:
        query = f"{search_keywords or seed_genre or 'pop'}"
        url = "https://api.spotify.com/v1/search"
        params = {"q": query, "type": "track", "limit": limit or 20}
        
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks_data = data.get("tracks", {})
                if isinstance(tracks_data, dict):
                    tracks = tracks_data.get("items", [])
                    return [t["uri"] for t in tracks if isinstance(t, dict) and "uri" in t]
        return []
    except Exception as e:
        print(f"❌ Fallback search error: {e}")
        return []


def search_spotify_track(artist, title, headers):
    try:
        if not artist or not title or not headers:
            return None
        
        query = f"track:{title} artist:{artist}"
        url = "https://api.spotify.com/v1/search"
        params = {"q": query, "type": "track", "limit": 1}
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks_data = data.get("tracks", {})
                if isinstance(tracks_data, dict):
                    tracks = tracks_data.get("items", [])
                    return tracks[0]["uri"] if tracks else None
        return None
    except Exception as e:
        print(f"❌ Error searching track: {e}")
        return None


def remove_duplicates_and_filter(track_list, headers):
    try:
        if not track_list:
            return []
        
        seen = set()
        result = []
        for item in track_list:
            if isinstance(item, dict) and "uri" in item:
                uri = item["uri"]
            elif isinstance(item, str):
                uri = item
            else:
                continue
                
            if uri not in seen:
                seen.add(uri)
                result.append(uri)
        return result
    except Exception as e:
        print(f"❌ Error removing duplicates: {e}")
        return track_list if isinstance(track_list, list) else []


def filter_explicit_content(tracks, headers, playlist_type):
    try:
        if playlist_type == "explicit" or not tracks:
            return tracks
        
        filtered = []
        for t in tracks:
            try:
                if isinstance(t, dict) and "uri" in t:
                    track_id = t["uri"].split(":")[-1]
                elif isinstance(t, str):
                    track_id = t.split(":")[-1]
                else:
                    continue
                
                res = requests.get(f"https://api.spotify.com/v1/tracks/{track_id}", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict) and not data.get("explicit", False):
                        filtered.append(t)
            except Exception as e:
                print(f"❌ Error checking explicit content: {e}")
                continue
                
        return filtered
    except Exception as e:
        print(f"❌ Error filtering explicit content: {e}")
        return tracks