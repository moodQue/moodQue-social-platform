import random
import requests
from moodque_auth import get_access_token

MOOD_TO_GENRE_MAP = {
    "happy": ["pop", "dance", "indie_pop"],
    "sad": ["acoustic", "piano", "ambient"],
    "angry": ["metal", "hard_rock", "industrial"],
    "chill": ["lofi", "chillhop", "electronic"],
    "romantic": ["rnb", "soul", "jazz"]
}

WILDCARD_ARTISTS = ["Tame Impala", "Grimes", "KAYTRANADA", "Joji", "FKA twigs"]

def weighted_genre_list(genres):
    weighted = []
    for i, genre in enumerate(genres):
        weight = max(1, len(genres) - i)
        weighted.extend([genre] * weight)
    return random.sample(weighted, min(5, len(weighted)))

def build_playlist(data):
    print("📦 Incoming Data:", data)  # NEW LINE

def build_playlist(data):
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    event = data.get("event_name")
    mood = data.get("mood")
    genres = weighted_genre_list(data.get("genre", []))

    if not (event and mood and genres):
        return {"error": "Missing one or more required fields (event_name, mood, genre)."}

    search_keywords = data.get("search_keywords", "")
    favorite_artist = data.get("favorite_artist", "").strip()
    playlist_type = data.get("playlist_type", "clean").lower()
    is_public = bool(data.get("is_public", True))

    # Enrich with artist
    seed_artists = []
    if favorite_artist:
        artist_search = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params={"q": favorite_artist, "type": "artist", "limit": 1}
        )
        artist_data = artist_search.json().get("artists", {}).get("items", [])
        if artist_data:
            seed_artists.append(artist_data[0]["id"])

    rec_params = {
        "limit": 25,
        "seed_genres": ','.join(genres),
        "market": "US"
    }

    if seed_artists:
        rec_params["seed_artists"] = ','.join(seed_artists)

    rec_resp = requests.get("https://api.spotify.com/v1/recommendations", headers=headers, params=rec_params)
    if not rec_resp.ok:
        return {"error": "Failed to get recommendations"}

    track_uris = [t["uri"] for t in rec_resp.json().get("tracks", [])]

    user_resp = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_id = user_resp.json().get("id")

    playlist_data = {
        "name": f"{event} • moodQue",
        "description": f"A moodQue playlist for your {event.lower()} vibe.",
        "public": is_public
    }

    playlist_resp = requests.post(
        f"https://api.spotify.com/v1/users/{user_id}/playlists",
        headers=headers,
        json=playlist_data
    )

    if not playlist_resp.ok:
        return {"error": "Failed to create playlist."}

    playlist_id = playlist_resp.json().get("id")

    track_resp = requests.post(
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
        headers=headers,
        json={"uris": track_uris}
    )

    print("🛑 Playlist creation failed:", playlist_resp.text)

    if not track_resp.ok:
        return {"error": "Failed to add tracks to playlist."}

    return {
        "message": "✅ Playlist created!",
        "url": playlist_resp.json().get("external_urls", {}).get("spotify"),
        "track_count": len(track_uris)
    }
