import os
from moodque_engine import get_recommendations_enhanced, build_spotify_playlist_from_tracks
from moodque_utilities import refresh_access_token

# STEP 1: Set up Spotify access
headers = {
    "Authorization": f"Bearer {refresh_access_token()}",
    "Content-Type": "application/json"
}

# STEP 2: Simulate inputs
user_id = os.getenv("SPOTIFY_USER_ID")
playlist_name = "🌟 LastFM Test Playlist"
seed_artists = ["Radiohead", "Daft Punk", "The Weeknd"]  # Seed artist names, not Spotify IDs
seed_genres = ["electronic"]
mood_params = {
    "birth_year": 1992
}

# STEP 3: Run recommendation pipeline
tracklist = get_recommendations_enhanced(
    headers=headers,
    seed_genres=seed_genres,
    seed_artists=seed_artists,
    mood_params=mood_params
)

# STEP 4: Create playlist on Spotify
playlist_id = build_spotify_playlist_from_tracks(headers, user_id, playlist_name, tracklist)

print(f"\n✅ Playlist created with ID: {playlist_id}")
