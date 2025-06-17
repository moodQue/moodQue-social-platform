from dotenv import load_dotenv
import os
import requests
import base64
import random

load_dotenv(dotenv_path=".env")

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")

# OFFICIAL SPOTIFY GENRE SEEDS (verified working)
SPOTIFY_VALID_GENRES = [
    "acoustic", "afrobeat", "alt-rock", "alternative", "ambient", "anime", 
    "black-metal", "bluegrass", "blues", "bossanova", "brazil", "breakbeat", 
    "british", "cantopop", "chicago-house", "children", "chill", "classical", 
    "club", "comedy", "country", "dance", "dancehall", "death-metal", 
    "deep-house", "detroit-techno", "disco", "disney", "drum-and-bass", 
    "dub", "dubstep", "edm", "electro", "electronic", "emo", "folk", 
    "forro", "french", "funk", "garage", "german", "gospel", "goth", 
    "grindcore", "groove", "grunge", "guitar", "happy", "hard-rock", 
    "hardcore", "hardstyle", "heavy-metal", "hip-hop", "holidays", 
    "honky-tonk", "house", "idm", "indian", "indie", "indie-pop", 
    "industrial", "iranian", "j-dance", "j-idol", "j-pop", "j-rock", 
    "jazz", "k-pop", "kids", "latin", "latino", "malay", "mandopop", 
    "metal", "metal-misc", "metalcore", "minimal-techno", "movies", 
    "mpb", "new-age", "new-release", "opera", "pagode", "party", 
    "philippines-opm", "piano", "pop", "pop-film", "post-dubstep", 
    "power-pop", "progressive-house", "psych-rock", "punk", "punk-rock", 
    "r-n-b", "rainy-day", "reggae", "reggaeton", "road-trip", "rock", 
    "rock-n-roll", "rockabilly", "romance", "sad", "salsa", "samba", 
    "sertanejo", "show-tunes", "singer-songwriter", "ska", "sleep", 
    "songwriter", "soul", "soundtracks", "spanish", "study", "summer", 
    "swedish", "synth-pop", "tango", "techno", "trance", "trip-hop", 
    "turkish", "work-out", "world-music"
]

# Map your app genres to Spotify genres
GENRE_MAPPING = {
    "hip-hop": "hip-hop",
    "pop": "pop", 
    "rock": "rock",
    "edm": "edm",
    "jazz": "jazz",
    "classical": "classical",
    "country": "country",
    "lo-fi": "chill",
    "indie": "indie",
    "r-n-b": "r-n-b",
    "funk": "funk",
    "soul": "soul", 
    "reggae": "reggae",
    "latin": "latin",
    "blues": "blues",
    "grunge": "grunge",
    "alternative": "alternative",
    "metal": "metal",
    "electronic": "electronic"
}

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
    print("✅ Access token refreshed successfully!")
    return res.json()["access_token"]

def get_current_user_id(headers):
    """Get the current user's ID from Spotify"""
    res = requests.get("https://api.spotify.com/v1/me", headers=headers)
    if res.status_code == 200:
        user_data = res.json()
        user_id = user_data.get("id")
        print(f"✅ Current user: {user_data.get('display_name')} (ID: {user_id})")
        return user_id
    else:
        print(f"❌ Failed to get user info: {res.status_code}")
        return None

def create_playlist(user_id, name, headers, description="MoodQue Auto Playlist"):
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    payload = {"name": name, "description": description, "public": False}
    
    print(f"🎯 Creating playlist for user: {user_id}")
    print(f"📝 Playlist name: {name}")
    
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code != 201:
        print("❌ Playlist creation failed:", res.text)
        print(f"❌ Status code: {res.status_code}")
        return None, None
    data = res.json()
    return data["id"], data["external_urls"]["spotify"]

def add_tracks_to_playlist(playlist_id, uris, headers):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    res = requests.post(url, headers=headers, json={"uris": uris})
    return res.status_code in [200, 201]

def get_enhanced_mood_values(mood):
    """Enhanced mood mapping with more precise audio features"""
    mood_map = {
        "happy": {
            "target_energy": 0.85, "target_valence": 0.9, "target_danceability": 0.8,
            "min_energy": 0.6, "min_valence": 0.7, "target_tempo": 120
        },
        "chill": {
            "target_energy": 0.3, "target_valence": 0.5, "target_danceability": 0.4,
            "max_energy": 0.6, "target_acousticness": 0.6, "target_tempo": 90
        },
        "upbeat": {
            "target_energy": 0.9, "target_valence": 0.8, "target_danceability": 0.9,
            "min_energy": 0.7, "target_tempo": 130
        },
        "focus": {
            "target_energy": 0.4, "target_valence": 0.3, "target_danceability": 0.3,
            "target_instrumentalness": 0.7, "max_speechiness": 0.1, "target_tempo": 100
        },
        "party": {
            "target_energy": 0.95, "target_valence": 0.9, "target_danceability": 0.95,
            "min_energy": 0.8, "min_danceability": 0.8, "target_tempo": 125
        },
        "hype": {
            "target_energy": 0.95, "target_valence": 0.85, "target_danceability": 0.9,
            "min_energy": 0.9, "target_loudness": -5, "target_tempo": 140
        },
        "melancholy": {
            "target_energy": 0.25, "target_valence": 0.2, "target_danceability": 0.3,
            "max_energy": 0.5, "max_valence": 0.4, "target_acousticness": 0.7
        },
        "workout": {
            "target_energy": 0.9, "target_valence": 0.7, "target_danceability": 0.85,
            "min_energy": 0.8, "target_tempo": 130, "target_loudness": -5
        },
        "romantic": {
            "target_energy": 0.4, "target_valence": 0.6, "target_danceability": 0.5,
            "target_acousticness": 0.5, "max_tempo": 100
        },
        "energetic": {
            "target_energy": 0.9, "target_valence": 0.8, "target_danceability": 0.85,
            "min_energy": 0.8, "target_tempo": 125
        }
    }
    return mood_map.get(mood.lower(), {})

def parse_genre_list(genre_input):
    """Parse comma-separated genres and map them to Spotify genres"""
    if not genre_input or genre_input.lower() == "any":
        return ["pop"]  # Default fallback
    
    # Split by commas and clean up
    genres = [g.strip().lower() for g in genre_input.split(',') if g.strip()]
    mapped_genres = []
    
    for genre in genres:
        # Remove any extra spaces or characters
        clean_genre = genre.replace(" ", "-")
        
        # Map to Spotify genre
        if clean_genre in GENRE_MAPPING:
            mapped_genres.append(GENRE_MAPPING[clean_genre])
        elif clean_genre in SPOTIFY_VALID_GENRES:
            mapped_genres.append(clean_genre)
        else:
            # Try to find similar genre
            for valid_genre in SPOTIFY_VALID_GENRES:
                if clean_genre in valid_genre or valid_genre in clean_genre:
                    mapped_genres.append(valid_genre)
                    break
    
    # Remove duplicates and limit to 3 genres for better results
    unique_genres = list(set(mapped_genres))[:3]
    
    if not unique_genres:
        unique_genres = ["pop"]  # Ultimate fallback
    
    print(f"🎵 Mapped genres: {genre_input} → {unique_genres}")
    return unique_genres

def get_artist_ids(artist_names, headers):
    """Get Spotify artist IDs from artist names"""
    artist_ids = []
    
    if not artist_names:
        return artist_ids
    
    # Parse artist names if it's a string
    if isinstance(artist_names, str):
        names_list = [name.strip() for name in artist_names.split(",") if name.strip()]
    else:
        names_list = artist_names
    
    for name in names_list[:3]:  # Limit to 3 artists for better variety
        if not name or not name.strip():
            continue
            
        res = requests.get("https://api.spotify.com/v1/search", params={
            "q": name.strip(),
            "type": "artist", 
            "limit": 1
        }, headers=headers)

        if res.status_code == 200:
            items = res.json().get("artists", {}).get("items", [])
            if items:
                artist_id = items[0]["id"]
                artist_ids.append(artist_id)
                print(f"🎤 Found artist: {name} → {artist_id}")
            else:
                print(f"❌ Artist not found: {name}")
        else:
            print(f"❌ Search failed for artist: {name}")
    
    return artist_ids

def remove_duplicates_and_filter(tracks, headers):
    """Remove duplicate tracks and filter for quality"""
    if not tracks:
        return []
    
    # Get track details for filtering
    track_ids = [uri.split(":")[-1] for uri in tracks]
    unique_tracks = []
    seen_artists = set()
    seen_track_names = set()
    
    batch_size = 50
    for i in range(0, len(track_ids), batch_size):
        batch_ids = track_ids[i:i + batch_size]
        
        res = requests.get("https://api.spotify.com/v1/tracks", 
                          headers=headers, 
                          params={"ids": ",".join(batch_ids)})
        
        if res.status_code == 200:
            batch_tracks = res.json().get("tracks", [])
            
            for j, track in enumerate(batch_tracks):
                if not track:
                    continue
                
                track_name = track.get("name", "").lower()
                artist_name = track.get("artists", [{}])[0].get("name", "").lower()
                original_uri = tracks[i + j]
                
                # Skip if we've seen this artist too many times (max 2 per artist)
                artist_count = sum(1 for seen in seen_artists if seen == artist_name)
                if artist_count >= 2:
                    continue
                
                # Skip if we've seen this exact track name
                if track_name in seen_track_names:
                    continue
                
                # Skip if track is too short (less than 60 seconds)
                duration_ms = track.get("duration_ms", 0)
                if duration_ms < 60000:
                    continue
                
                # Add track
                unique_tracks.append(original_uri)
                seen_artists.add(artist_name)
                seen_track_names.add(track_name)
    
    print(f"🔍 Filtered tracks: {len(tracks)} → {len(unique_tracks)} (removed duplicates)")
    return unique_tracks

def get_recommendations_enhanced(headers, limit=25, seed_genres=None, seed_artists=None, 
                               mood_params=None):
    """Get recommendations with better genre handling"""
    rec_url = "https://api.spotify.com/v1/recommendations"
    
    params = {"limit": limit, "market": "US"}
    
    # Add seeds (max 5 total, prioritize genres over artists)
    seeds_used = 0
    
    if seed_genres and seeds_used < 5:
        # Use up to 3 genres
        genres_to_use = seed_genres[:min(3, 5-seeds_used)]
        params["seed_genres"] = ",".join(genres_to_use)
        seeds_used += len(genres_to_use)
        print(f"🎵 Using genre seeds: {genres_to_use}")
    
    if seed_artists and seeds_used < 5:
        # Use remaining slots for artists
        artists_to_use = seed_artists[:5-seeds_used]
        params["seed_artists"] = ",".join(artists_to_use)
        seeds_used += len(artists_to_use)
        print(f"🎤 Using artist seeds: {len(artists_to_use)} artists")
    
    # Add mood parameters for better targeting
    if mood_params:
        # Be more selective with mood parameters
        filtered_params = {}
        for key, value in mood_params.items():
            if key.startswith('target_') or key.startswith('min_') or key.startswith('max_'):
                filtered_params[key] = value
        params.update(filtered_params)
        print(f"😊 Using mood params: {filtered_params}")
    
    print(f"🎯 Recommendations API call with {seeds_used} seeds")
    res = requests.get(rec_url, headers=headers, params=params)
    
    if res.status_code == 200:
        tracks = res.json().get("tracks", [])
        track_uris = [track["uri"] for track in tracks]
        print(f"✅ Recommendations API: Got {len(track_uris)} tracks")
        return track_uris
    else:
        print(f"❌ Recommendations API failed: {res.status_code} - {res.text}")
        return []

def search_spotify_tracks_enhanced(genre_input, headers, limit=20, mood_tags=None, 
                                 search_keywords=None, playlist_type="clean", 
                                 artist_names=None):
    """Enhanced search with better genre and duplicate handling"""
    
    # Parse and map genres
    spotify_genres = parse_genre_list(genre_input)
    
    # Get artist IDs if provided
    artist_ids = get_artist_ids(artist_names, headers) if artist_names else []
    
    # Get mood parameters
    mood_params = get_enhanced_mood_values(mood_tags) if mood_tags else {}
    
    all_tracks = []
    
    # Strategy 1: Use Recommendations API with each genre separately
    for genre in spotify_genres:
        print(f"🔍 Getting recommendations for genre: {genre}")
        tracks = get_recommendations_enhanced(
            headers=headers,
            limit=limit // len(spotify_genres) + 5,  # Get extra to account for filtering
            seed_genres=[genre],
            seed_artists=artist_ids[:2] if artist_ids else [],
            mood_params=mood_params
        )
        all_tracks.extend(tracks)
    
    # Strategy 2: If we don't have enough tracks, try combined genre search
    if len(all_tracks) < limit * 0.7:
        print("🔄 Getting additional tracks with combined genres...")
        additional_tracks = get_recommendations_enhanced(
            headers=headers,
            limit=limit,
            seed_genres=spotify_genres[:2],  # Max 2 genres for combined search
            seed_artists=artist_ids[:1] if artist_ids else [],
            mood_params=mood_params
        )
        all_tracks.extend(additional_tracks)
    
    # Remove duplicates and filter for quality
    filtered_tracks = remove_duplicates_and_filter(all_tracks, headers)
    
    # Filter for explicit content
    final_tracks = filter_explicit_content(filtered_tracks, headers, playlist_type)
    
    print(f"✅ Final track count: {len(final_tracks)}")
    return final_tracks[:limit]

def filter_explicit_content(track_uris, headers, playlist_type):
    """Filter tracks based on explicit content preference"""
    if not track_uris or playlist_type.lower() == "any":
        return track_uris
    
    track_ids = [uri.split(":")[-1] for uri in track_uris]
    filtered_uris = []
    batch_size = 50
    
    for i in range(0, len(track_ids), batch_size):
        batch_ids = track_ids[i:i + batch_size]
        
        res = requests.get("https://api.spotify.com/v1/tracks", 
                          headers=headers, 
                          params={"ids": ",".join(batch_ids)})
        
        if res.status_code == 200:
            tracks = res.json().get("tracks", [])
            
            for j, track in enumerate(tracks):
                if track:
                    is_explicit = track.get("explicit", False)
                    original_uri = track_uris[i + j]
                    
                    if playlist_type.lower() == "clean" and not is_explicit:
                        filtered_uris.append(original_uri)
                    elif playlist_type.lower() == "explicit" and is_explicit:
                        filtered_uris.append(original_uri)
    
    print(f"🔍 Content filter: {len(track_uris)} → {len(filtered_uris)} tracks ({playlist_type})")
    return filtered_uris

def build_smart_playlist_enhanced(event, genre, time, mood_tags, search_keywords, 
                                artist_names=None, user_preferences=None, playlist_type="clean"):
    """Enhanced playlist builder with better filtering and no duplicates"""
    track_limit = max(10, int(time) // 3) if time else 20  # Slightly more tracks for better variety
    access_token = refresh_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Get current user ID
    current_user_id = get_current_user_id(headers)
    if not current_user_id:
        print("❌ Failed to get current user ID")
        return None
    
    print(f"🎵 Building enhanced playlist: {event}")
    print(f"🎯 Genres: {genre}")
    print(f"😊 Mood: {mood_tags}")
    print(f"🔍 Keywords: {search_keywords}")
    print(f"🎤 Artists: {artist_names}")
    print(f"📊 Target tracks: {track_limit}")
    print(f"🎯 Content filter: {playlist_type}")

    track_uris = search_spotify_tracks_enhanced(
        genre_input=genre,
        headers=headers,
        limit=track_limit,
        mood_tags=mood_tags,
        search_keywords=search_keywords,
        playlist_type=playlist_type,
        artist_names=artist_names
    )

    if not track_uris:
        print("❌ No tracks found after enhanced search.")
        return None

    playlist_name = f"{event} - {mood_tags or 'Mixed'} [{playlist_type}]"
    playlist_id, playlist_url = create_playlist(current_user_id, playlist_name, headers)
    if not playlist_id:
        return None
        
    success = add_tracks_to_playlist(playlist_id, track_uris, headers)
    if success:
        print(f"✅ Created enhanced playlist '{playlist_name}' with {len(track_uris)} tracks")
        print(f"🔗 Playlist URL: {playlist_url}")
        return playlist_url
    return None

if __name__ == "__main__":
    # Test the enhanced playlist builder
    print("🧪 Testing enhanced playlist creation...")
    
    result = build_smart_playlist_enhanced(
        event="Tuesday Workday Reset",
        genre="pop,rock,hip-hop,indie,r-n-b",  # Test multi-genre
        time="60",
        mood_tags="Upbeat",
        search_keywords="energy motivation",
        artist_names="Taylor Swift, Kendrick Lamar",
        playlist_type="clean"
    )
    
    if result:
        print(f"🎉 Success! Enhanced playlist created: {result}")
    else:
        print("❌ Failed to create enhanced playlist")