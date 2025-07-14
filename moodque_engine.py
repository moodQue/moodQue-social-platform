from dotenv import load_dotenv
from lastfm_recommender import get_recommendations
import os
import requests
import base64
import random
import uuid
import json
from moodque_utilities import search_spotify_track


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

def get_recommendations_enhanced(headers, limit=20, seed_genres=None, seed_artists=None, mood_params=None):
    """Get recommendations using moodQue recommender and build track list"""
    # Handle genre
    if not seed_genres:
        print("⚠️ No genre provided. Defaulting to 'pop'.")
    genre = seed_genres[0] if seed_genres else "pop"

    # Handle birth year
    birth_year = None
    if mood_params:
        birth_year = mood_params.get("birth_year")
    if not birth_year:
        print("⚠️ No birth year provided. Era scoring may be less accurate.")

    # Get recommendations
    tracklist = get_recommendations(seed_artists, genre, birth_year)

    # Optional: Log selected tracks
    for t in tracklist:
        print(f"🎧 Selected: {t['artist']} - {t['track']} (score: {t['score']})")

    return tracklist  # You’ll pass this to the playlist builder

def build_spotify_playlist_from_tracks(headers, user_id, playlist_name, tracklist):
    # Create a playlist
    create_url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    payload = json.dumps({"name": playlist_name, "description": "Made with moodQue", "public": False})
    try:
        res = requests.post(create_url, headers=headers, data=payload)
        if res.status_code == 201:
            playlist_id = res.json().get("id")
            print(f"✅ Created playlist: {playlist_name}")
            
            # Get track URIs from search
            uris = []
            for track in tracklist:
                uri = search_spotify_track(track["artist"], track["track"], headers)
                if uri:
                    uris.append(uri)

            # Add tracks to playlist
            if uris:
                add_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
                add_res = requests.post(add_url, headers=headers, json={"uris": uris})
                if add_res.status_code == 201:
                    print(f"🎶 Added {len(uris)} tracks to playlist!")
                    return playlist_id
                else:
                    print(f"⚠️ Failed to add tracks: {add_res.status_code} {add_res.text}")
            else:
                print("⚠️ No tracks found to add.")
        else:
            print(f"❌ Playlist creation failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"❌ Exception during playlist build: {e}")
    return None

# Map your app genres to Spotify genres
GENRE_MAPPING = {
    "hip-hop": "hip-hop",
    "pop": "pop", 
    "rock": "rock",
    "edm": "edm",
    "jazz": "jazz",
    "classical": "classical",
    "country": "country",
    "lo-fi": "chill",  # lo-fi maps to chill
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

def create_new_playlist(headers, user_id, name, description="MoodQue Auto Playlist"):
    """Create new playlist with correct parameter order"""
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
    """Add tracks to playlist with better error handling"""
    try:
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        
        # Ensure track_uris is a list of strings
        clean_uris = []
        if isinstance(track_uris, list):
            for t in track_uris:
                if isinstance(t, dict) and "uri" in t:
                    clean_uris.append(t["uri"])
                elif isinstance(t, str) and "spotify:track:" in t:
                    clean_uris.append(t)
        
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
        "energetic": {
            "target_energy": 0.9, "target_valence": 0.8, "target_danceability": 0.85,
            "min_energy": 0.8, "target_tempo": 125
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
        }
    }
    return mood_map.get(mood.lower(), {})

def sanitize_genre(genre):
    """Map app genres to valid Spotify genres"""
    if not genre or genre.lower() == "any":
        return None
        
    genre_clean = genre.strip().lower().replace(" ", "-")
    
    # Check if it's directly in our mapping
    if genre_clean in GENRE_MAPPING:
        spotify_genre = GENRE_MAPPING[genre_clean]
        print(f"🎵 Genre mapped: '{genre}' → '{spotify_genre}'")
        return spotify_genre
    
    # Check if it's already a valid Spotify genre
    if genre_clean in SPOTIFY_VALID_GENRES:
        print(f"🎵 Genre valid: '{genre_clean}'")
        return genre_clean
    
    # Fallback: try to find a similar genre
    for valid_genre in SPOTIFY_VALID_GENRES:
        if genre_clean in valid_genre or valid_genre in genre_clean:
            print(f"🎵 Genre fuzzy match: '{genre}' → '{valid_genre}'")
            return valid_genre
    
    print(f"⚠️ Genre '{genre}' not found. Using 'pop' as fallback.")
    return "pop"

def parse_genre_list(genre_input):
    """Parse comma-separated genres and map them to Spotify genres"""
    try:
        if not genre_input or genre_input.lower() == "any":
            return ["pop"]
        
        # Split by commas and clean up
        genres = [g.strip().lower() for g in str(genre_input).split(',') if g.strip()]
        mapped_genres = []
        
        for genre in genres:
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
        
        # Remove duplicates and limit to 2 genres
        unique_genres = list(set(mapped_genres))[:2]
        
        if not unique_genres:
            unique_genres = ["pop"]
        
        print(f"🎵 Mapped genres: {genre_input} → {unique_genres}")
        return unique_genres
    except Exception as e:
        print(f"❌ Error parsing genres: {e}")
        return ["pop"]

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
            
        try:
            res = requests.get("https://api.spotify.com/v1/search", params={
                "q": name.strip(),
                "type": "artist", 
                "limit": 1
            }, headers=headers)

            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    artists = data.get("artists", {})
                    if isinstance(artists, dict):
                        items = artists.get("items", [])
                        if items and isinstance(items, list):
                            artist_id = items[0]["id"]
                            artist_ids.append(artist_id)
                            print(f"🎤 Found artist: {name} → {artist_id}")
                        else:
                            print(f"❌ Artist not found: {name}")
                    else:
                        print(f"❌ Invalid artists response for: {name}")
                else:
                    print(f"❌ Invalid search response for: {name}")
            else:
                print(f"❌ Search failed for artist: {name}")
        except Exception as e:
            print(f"❌ Exception searching for artist {name}: {e}")
    
    return artist_ids

# Replace the search_spotify_tracks_fallback function in your moodque_engine.py with this improved version:

def search_spotify_tracks_fallback(genre, headers, limit=20, mood_tags=None, 
                                 search_keywords=None, playlist_type="clean"):
    """Improved fallback search using multiple search strategies"""
    search_url = "https://api.spotify.com/v1/search"
    all_tracks = []
    
    # Strategy 1: Search by genre
    if genre and genre != "pop":
        print(f"🔍 Fallback strategy 1: Searching by genre '{genre}'")
        try:
            params = {
                "q": f"genre:{genre}",
                "type": "track",
                "limit": min(limit, 50),
                "market": "US"
            }
            
            res = requests.get(search_url, headers=headers, params=params)
            if res.status_code == 200:
                tracks = extract_tracks_from_search(res.json(), playlist_type)
                all_tracks.extend(tracks)
                print(f"✅ Genre search found {len(tracks)} tracks")
        except Exception as e:
            print(f"❌ Genre search failed: {e}")
    
    # Strategy 2: Search by mood/keywords
    if (mood_tags or search_keywords) and len(all_tracks) < limit:
        search_terms = []
        if mood_tags:
            search_terms.append(mood_tags.lower())
        if search_keywords:
            search_terms.append(search_keywords.lower())
        
        query = " ".join(search_terms)
        print(f"🔍 Fallback strategy 2: Searching by mood/keywords '{query}'")
        
        try:
            params = {
                "q": query,
                "type": "track",
                "limit": min(limit, 50),
                "market": "US"
            }
            
            res = requests.get(search_url, headers=headers, params=params)
            if res.status_code == 200:
                tracks = extract_tracks_from_search(res.json(), playlist_type)
                # Avoid duplicates
                new_tracks = [t for t in tracks if t not in all_tracks]
                all_tracks.extend(new_tracks)
                print(f"✅ Mood/keyword search found {len(new_tracks)} new tracks")
        except Exception as e:
            print(f"❌ Mood/keyword search failed: {e}")
    
    # Strategy 3: Popular tracks by year (current hits)
    if len(all_tracks) < limit:
        print(f"🔍 Fallback strategy 3: Searching for popular 2024 tracks")
        try:
            params = {
                "q": "year:2024",
                "type": "track",
                "limit": min(limit, 50),
                "market": "US"
            }
            
            res = requests.get(search_url, headers=headers, params=params)
            if res.status_code == 200:
                tracks = extract_tracks_from_search(res.json(), playlist_type)
                new_tracks = [t for t in tracks if t not in all_tracks]
                all_tracks.extend(new_tracks)
                print(f"✅ 2024 popular search found {len(new_tracks)} new tracks")
        except Exception as e:
            print(f"❌ 2024 popular search failed: {e}")
    
    # Strategy 4: Generic popular music search
    if len(all_tracks) < limit:
        print(f"🔍 Fallback strategy 4: Searching for general popular music")
        try:
            popular_terms = ["pop", "hits", "top", "popular", "trending"]
            
            for term in popular_terms:
                if len(all_tracks) >= limit:
                    break
                    
                params = {
                    "q": term,
                    "type": "track",
                    "limit": 20,
                    "market": "US"
                }
                
                res = requests.get(search_url, headers=headers, params=params)
                if res.status_code == 200:
                    tracks = extract_tracks_from_search(res.json(), playlist_type)
                    new_tracks = [t for t in tracks if t not in all_tracks]
                    all_tracks.extend(new_tracks[:5])  # Limit per term
                    print(f"✅ '{term}' search found {len(new_tracks[:5])} new tracks")
        except Exception as e:
            print(f"❌ Generic popular search failed: {e}")
    
    # Strategy 5: Last resort - search for specific popular artists
    if len(all_tracks) < limit:
        print(f"🔍 Fallback strategy 5: Searching for tracks by popular artists")
        popular_artists = ["Taylor Swift", "Ed Sheeran", "Ariana Grande", "Drake", "Billie Eilish"]
        
        for artist in popular_artists:
            if len(all_tracks) >= limit:
                break
                
            try:
                params = {
                    "q": f"artist:{artist}",
                    "type": "track",
                    "limit": 5,
                    "market": "US"
                }
                
                res = requests.get(search_url, headers=headers, params=params)
                if res.status_code == 200:
                    tracks = extract_tracks_from_search(res.json(), playlist_type)
                    new_tracks = [t for t in tracks if t not in all_tracks]
                    all_tracks.extend(new_tracks[:3])  # Max 3 per artist
                    print(f"✅ {artist} search found {len(new_tracks[:3])} new tracks")
            except Exception as e:
                print(f"❌ {artist} search failed: {e}")
    
    result = all_tracks[:limit]
    print(f"✅ Total fallback search result: {len(result)} tracks")
    return result

def extract_tracks_from_search(search_response, playlist_type="clean"):
    """Extract track URIs from Spotify search response"""
    tracks = []
    
    try:
        if not isinstance(search_response, dict):
            return tracks
        
        tracks_data = search_response.get("tracks", {})
        if not isinstance(tracks_data, dict):
            return tracks
        
        items = tracks_data.get("items", [])
        if not isinstance(items, list):
            return tracks
        
        for track in items:
            if not isinstance(track, dict):
                continue
            
            # Check explicit content
            is_explicit = track.get("explicit", False)
            if playlist_type.lower() == "clean" and is_explicit:
                continue
            elif playlist_type.lower() == "explicit" and not is_explicit:
                continue
            
            # Get track URI
            track_uri = track.get("uri")
            if track_uri and track_uri.startswith("spotify:track:"):
                tracks.append(track_uri)
        
        return tracks
        
    except Exception as e:
        print(f"❌ Error extracting tracks from search: {e}")
        return tracks

# Also add this function to handle the 404 recommendations error:
def get_recommendations_enhanced(headers, limit=20, seed_genres=None, seed_artists=None, mood_params=None):
    """Try to get Spotify recommendations, fallback to Last.fm if Spotify fails"""
    rec_url = "https://api.spotify.com/v1/recommendations"

    # Build Spotify parameters
    params = {
        "limit": min(limit, 20),
        "market": "US"
    }

    total_seeds = 0
    if seed_genres:
        genres_to_use = seed_genres[:2]
        params["seed_genres"] = ",".join(genres_to_use)
        total_seeds += len(genres_to_use)
        print(f"🎵 Using genre seeds: {genres_to_use}")

    if seed_artists:
        artists_to_use = seed_artists[:1]
        params["seed_artists"] = ",".join(artists_to_use)
        total_seeds += len(artists_to_use)
        print(f"🎤 Using artist seeds: {artists_to_use}")

    if mood_params:
        if "target_energy" in mood_params:
            params["target_energy"] = mood_params["target_energy"]
        if "target_valence" in mood_params:
            params["target_valence"] = mood_params["target_valence"]
        print(f"😊 Using mood params: energy={params.get('target_energy')}, valence={params.get('target_valence')}")

    print(f"🎯 API call with {total_seeds} seeds")
    print(f"📝 Full params: {params}")

    try:
        res = requests.get(rec_url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks = data.get("tracks", [])
                uris = [t["uri"] for t in tracks if "uri" in t]
                print(f"✅ Spotify SUCCESS: Got {len(uris)} tracks")
                return uris
            else:
                print("❌ Invalid format from Spotify response.")
        else:
            print(f"❌ Spotify recommendations failed: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Spotify exception: {e}")

    # FALLBACK TO LAST.FM IF SPOTIFY FAILS
    print("⚠️ Falling back to Last.fm recommendations...")
    genre = seed_genres[0] if seed_genres else "pop"
    birth_year = mood_params.get("birth_year") if mood_params else None
    fallback_tracks = get_lastfm_recommendations(seed_artists, genre, birth_year)
    fallback_uris = []

    for t in fallback_tracks:
        uri = search_spotify_track(t["artist"], t["track"], headers)
        if uri:
            fallback_uris.append(uri)

    print(f"✅ Last.fm fallback SUCCESS: Got {len(fallback_uris)} tracks")
    return fallback_uris

# Replace the search_spotify_tracks_enhanced function in moodque_engine.py with this version:

def search_spotify_tracks_enhanced(genre, headers, limit=20, mood_tags=None, 
                                 search_keywords=None, playlist_type="clean", 
                                 favorite_artist=None, use_lastfm=False):
    """Enhanced search with multiple fallback strategies"""
    try:
        print(f"🔍 Enhanced search - Genre: {genre}, Mood: {mood_tags}, Limit: {limit}")
        
        # Parse genres
        if isinstance(genre, str) and ',' in genre:
            spotify_genres = parse_genre_list(genre)
        else:
            spotify_genre = sanitize_genre(genre) if genre else "pop"
            spotify_genres = [spotify_genre] if spotify_genre else ["pop"]
        
        print(f"🎵 Using genres: {spotify_genres}")
        
        # Get artist IDs
        artist_ids = []
        if favorite_artist:
            try:
                artist_ids = get_artist_ids(favorite_artist, headers)
                print(f"🎤 Found {len(artist_ids)} artist IDs")
            except Exception as e:
                print(f"⚠️ Artist lookup failed: {e}")
        
        # Get mood parameters
        mood_params = {}
        if mood_tags:
            try:
                mood_params = get_enhanced_mood_values(mood_tags)
                print(f"😊 Mood parameters: {mood_params}")
            except Exception as e:
                print(f"⚠️ Mood params failed: {e}")
        
        all_tracks = []
        
        # Strategy 1: Try recommendations API
        print("🎯 Strategy 1: Trying Spotify Recommendations API...")
        try:
            rec_tracks = get_recommendations_enhanced(
                headers=headers,
                limit=limit * 2,  # Get more recommendations to have options
                seed_genres=spotify_genres,
                seed_artists=artist_ids,
                mood_params=mood_params
            )
            
            if rec_tracks:
                all_tracks.extend(rec_tracks)
                print(f"✅ Got {len(rec_tracks)} tracks from recommendations")
            else:
                print("⚠️ Recommendations returned no tracks")
        except Exception as e:
            print(f"⚠️ Recommendations failed: {e}")
        
        # Strategy 2: Search for specific artists' popular tracks
        if favorite_artist and len(all_tracks) < limit:
            print(f"🎯 Strategy 2: Searching for popular tracks by {favorite_artist}")
            try:
                artist_tracks = search_artist_popular_tracks(favorite_artist, headers, limit // 2)
                if artist_tracks:
                    # Remove duplicates
                    new_tracks = [t for t in artist_tracks if t not in all_tracks]
                    all_tracks.extend(new_tracks)
                    print(f"✅ Got {len(new_tracks)} tracks from artist search")
            except Exception as e:
                print(f"⚠️ Artist popular tracks search failed: {e}")
        
        # Strategy 3: Use improved fallback search
        if len(all_tracks) < limit:
            print("🎯 Strategy 3: Using improved fallback search...")
            try:
                needed_tracks = limit - len(all_tracks)
                fallback_tracks = search_spotify_tracks_fallback(
                    spotify_genres[0] if spotify_genres else "pop", 
                    headers, 
                    needed_tracks * 2,  # Get more than needed
                    mood_tags, 
                    search_keywords, 
                    playlist_type
                )
                if fallback_tracks:
                    # Remove duplicates
                    new_tracks = [t for t in fallback_tracks if t not in all_tracks]
                    all_tracks.extend(new_tracks)
                    print(f"✅ Got {len(new_tracks)} tracks from fallback")
                else:
                    print("⚠️ Fallback search returned no tracks")
            except Exception as e:
                print(f"⚠️ Fallback search failed: {e}")
        
        # Strategy 4: Emergency fallback - just search for popular music
        if len(all_tracks) < 5:  # If we have very few tracks
            print("🚨 Strategy 4: Emergency fallback - searching for any popular music")
            try:
                emergency_tracks = emergency_track_search(headers, limit, playlist_type)
                if emergency_tracks:
                    new_tracks = [t for t in emergency_tracks if t not in all_tracks]
                    all_tracks.extend(new_tracks)
                    print(f"✅ Got {len(new_tracks)} tracks from emergency search")
            except Exception as e:
                print(f"⚠️ Emergency search failed: {e}")
        
        # Final result
        result = all_tracks[:limit] if all_tracks else []
        print(f"✅ Enhanced search complete: {len(result)} tracks total")
        
        if not result:
            print("❌ No tracks found in any search strategy!")
            
        return result
        
    except Exception as e:
        print(f"❌ Critical error in enhanced search: {e}")
        # Last resort - try emergency search
        try:
            return emergency_track_search(headers, limit, playlist_type)
        except Exception as e2:
            print(f"❌ Emergency search also failed: {e2}")
            return []

def search_artist_popular_tracks(artist_name, headers, limit=10):
    """Search for an artist's popular tracks directly on Spotify"""
    try:
        print(f"🎤 Searching for popular tracks by: {artist_name}")
        
        # First find the artist
        search_url = "https://api.spotify.com/v1/search"
        params = {
            "q": f"artist:\"{artist_name}\"",  # Use quotes for exact match
            "type": "artist",
            "limit": 1
        }
        
        res = requests.get(search_url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"❌ Artist search failed: {res.status_code}")
            return []
        
        data = res.json()
        artists = data.get("artists", {}).get("items", [])
        if not artists:
            print(f"❌ Artist not found: {artist_name}")
            return []
        
        artist_id = artists[0]["id"]
        print(f"✅ Found artist {artist_name} with ID: {artist_id}")
        
        # Get artist's top tracks
        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
        params = {"market": "US"}
        
        res = requests.get(top_tracks_url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"❌ Top tracks request failed: {res.status_code}")
            return []
        
        data = res.json()
        tracks = data.get("tracks", [])
        
        track_uris = []
        for track in tracks[:limit]:
            if isinstance(track, dict) and "uri" in track:
                track_uris.append(track["uri"])
        
        print(f"✅ Found {len(track_uris)} popular tracks for {artist_name}")
        return track_uris
        
    except Exception as e:
        print(f"❌ Error searching artist popular tracks: {e}")
        return []

def emergency_track_search(headers, limit, playlist_type="clean"):
    """Emergency search for when all else fails"""
    try:
        print("🚨 Running emergency track search...")
        
        search_url = "https://api.spotify.com/v1/search"
        
        # Try multiple simple search terms
        search_terms = [
            "top hits",
            "popular songs", 
            "chart toppers",
            "best songs",
            "trending music",
            "hit songs",
            "popular music",
            "top 40"
        ]
        
        all_tracks = []
        
        for term in search_terms:
            if len(all_tracks) >= limit:
                break
                
            try:
                params = {
                    "q": term,
                    "type": "track",
                    "limit": 20,
                    "market": "US"
                }
                
                res = requests.get(search_url, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    tracks = extract_tracks_from_search(data, playlist_type)
                    
                    # Add unique tracks
                    for track in tracks:
                        if track not in all_tracks and len(all_tracks) < limit:
                            all_tracks.append(track)
                    
                    print(f"✅ Emergency term '{term}' found {len(tracks)} tracks")
            except Exception as e:
                print(f"❌ Emergency term '{term}' failed: {e}")
        
        print(f"🚨 Emergency search result: {len(all_tracks)} tracks")
        return all_tracks
        
    except Exception as e:
        print(f"❌ Emergency search completely failed: {e}")
        return []

# build_smart_playlist_enhanced function

def build_smart_playlist_enhanced(event_name, genre, time, mood_tags, search_keywords, 
                                   playlist_type, favorite_artist, request_id=None):
    """
    Build a smart playlist with enhanced features
    
    Args:
        event_name (str): Name of the playlist/event
        genre (str): Music genre
        time (int): Target duration in minutes
        mood_tags (str): Mood tags for the playlist
        search_keywords (str): Additional search keywords
        playlist_type (str): "clean" or "explicit"
        favorite_artist (str): Favorite artist(s)
        request_id (str): Request ID for logging
    
    Returns:
        str: Spotify playlist URL if successful, None if failed
    """
    logger_prefix = f"[{request_id}]" if request_id else ""
    
    print(f"{logger_prefix} 🎧 Building playlist for event: '{event_name}'")
    print(f"{logger_prefix} 🔥 Genre Input: {genre}")
    print(f"{logger_prefix} 🎭 Mood Tag: {mood_tags}")
    print(f"{logger_prefix} 🧠 Search Keywords: {search_keywords}")
    print(f"{logger_prefix} 🌟 Favorite Artist(s): {favorite_artist}")
    print(f"{logger_prefix} ⏰ Target Duration: {time} minutes")
    print(f"{logger_prefix} 🚫 Content Filter: {playlist_type}")

    # Clean up favorite_artist input
    if favorite_artist:
        favorite_artist = favorite_artist.replace("'", "'").strip()

    try:
        # Get fresh access token
        access_token = refresh_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Convert time to target duration in milliseconds (average song is ~3.5 minutes)
        target_duration_minutes = int(time) if time else 30
        estimated_track_count = max(10, int(target_duration_minutes / 3.5))  # Rough estimate
        max_tracks = min(estimated_track_count * 2, 100)  # Get more options, limit to 100
        
        print(f"{logger_prefix} 🎯 Target: {target_duration_minutes} minutes (~{estimated_track_count} tracks)")

        # Get tracks using enhanced search
        track_items = search_spotify_tracks_enhanced_with_duration(
            genre=genre,
            headers=headers,
            target_duration_minutes=target_duration_minutes,
            max_tracks=max_tracks,
            mood_tags=mood_tags,
            search_keywords=search_keywords,
            playlist_type=playlist_type,
            favorite_artist=favorite_artist
        )

        if not track_items:
            print(f"{logger_prefix} ❌ No valid tracks found, cannot create playlist")
            return None

        # Get user ID
        user_id = get_spotify_user_id(headers)
        if not user_id:
            print(f"{logger_prefix} ❌ Could not get user ID")
            return None

        # Create playlist
        playlist_id = create_new_playlist(headers, user_id, event_name, f"MoodQue playlist for {event_name}")
        if not playlist_id:
            print(f"{logger_prefix} ❌ Could not create playlist")
            return None

        # Add tracks to playlist
        success = add_tracks_to_playlist(headers, playlist_id, track_items)
        if not success:
            print(f"{logger_prefix} ❌ Could not add tracks to playlist")
            return None

        # Calculate final duration
        final_duration = calculate_playlist_duration(track_items, headers)
        print(f"{logger_prefix} ✅ Final playlist: {len(track_items)} tracks, {final_duration:.1f} minutes")

        # Return the Spotify URL
        playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
        print(f"{logger_prefix} ✅ Playlist created successfully: {playlist_url}")
        
        return playlist_url
        
    except Exception as e:
        print(f"{logger_prefix} ❌ Error building playlist: {e}")
        import traceback
        traceback.print_exc()
        return None

def search_spotify_tracks_enhanced_with_duration(genre, headers, target_duration_minutes=30, max_tracks=50, 
                                               mood_tags=None, search_keywords=None, playlist_type="clean", 
                                               favorite_artist=None):
    """Enhanced search that prioritizes quality, manages duration, and mixes artists"""
    try:
        print(f"🔍 Enhanced search with duration - Target: {target_duration_minutes} minutes")
        print(f"🚫 Content filter: {playlist_type}")
        
        # Parse genres
        if isinstance(genre, str) and ',' in genre:
            spotify_genres = parse_genre_list(genre)
        else:
            spotify_genre = sanitize_genre(genre) if genre else "pop"
            spotify_genres = [spotify_genre] if spotify_genre else ["pop"]
        
        print(f"🎵 Using genres: {spotify_genres}")
        
        # Get artist IDs
        artist_ids = []
        favorite_artists = []
        if favorite_artist:
            try:
                # Parse multiple artists
                if isinstance(favorite_artist, str) and ',' in favorite_artist:
                    favorite_artists = [a.strip() for a in favorite_artist.split(',')]
                else:
                    favorite_artists = [favorite_artist]
                
                artist_ids = get_artist_ids(favorite_artist, headers)
                print(f"🎤 Found {len(artist_ids)} artist IDs for {len(favorite_artists)} artists")
            except Exception as e:
                print(f"⚠️ Artist lookup failed: {e}")
        
        # Get mood parameters
        mood_params = {}
        if mood_tags:
            try:
                mood_params = get_enhanced_mood_values(mood_tags)
                print(f"😊 Mood parameters: {mood_params}")
            except Exception as e:
                print(f"⚠️ Mood params failed: {e}")
        
        # Collect tracks from different sources
        artist_tracks = []
        recommendation_tracks = []
        fallback_tracks = []
        
        target_duration_ms = target_duration_minutes * 60 * 1000
        
        # Priority 1: Get tracks from each favorite artist
        if favorite_artists:
            print("🎯 Priority 1: Getting tracks from favorite artists...")
            try:
                for artist in favorite_artists:
                    tracks = search_artist_popular_tracks_with_duration(
                        artist, headers, limit=8  # Get 8 tracks per artist
                    )
                    if tracks:
                        # Filter explicit content immediately
                        clean_tracks = filter_explicit_tracks(tracks, playlist_type)
                        artist_tracks.extend(clean_tracks)
                        print(f"✅ Got {len(clean_tracks)} clean tracks from {artist}")
                
                print(f"✅ Total artist tracks: {len(artist_tracks)}")
            except Exception as e:
                print(f"⚠️ Favorite artist search failed: {e}")
        
        # Priority 2: Get recommendations (limit quantity)
        print("🎯 Priority 2: Getting recommendations...")
        try:
            rec_tracks = get_recommendations_enhanced(
                headers=headers,
                limit=15,  # Limit recommendations
                seed_genres=spotify_genres,
                seed_artists=artist_ids,
                mood_params=mood_params
            )
            
            if rec_tracks:
                # Get duration info and filter explicit
                rec_with_duration = get_tracks_with_duration(rec_tracks, headers)
                clean_rec_tracks = filter_explicit_tracks(rec_with_duration, playlist_type)
                recommendation_tracks.extend(clean_rec_tracks)
                print(f"✅ Got {len(clean_rec_tracks)} clean recommendation tracks")
        except Exception as e:
            print(f"⚠️ Recommendations failed: {e}")
        
        # Priority 3: High-quality fallback (if needed)
        estimated_duration = sum(t['duration_ms'] for t in artist_tracks + recommendation_tracks)
        if estimated_duration < target_duration_ms * 0.8:
            print("🎯 Priority 3: Getting high-quality fallback tracks...")
            try:
                needed_duration = target_duration_ms - estimated_duration
                needed_tracks = max(5, int(needed_duration / (3.5 * 60 * 1000)))
                
                fallback_uris = search_high_quality_tracks(
                    spotify_genres[0], headers, needed_tracks, mood_tags, search_keywords, playlist_type
                )
                
                if fallback_uris:
                    fallback_with_duration = get_tracks_with_duration(fallback_uris, headers)
                    clean_fallback_tracks = filter_explicit_tracks(fallback_with_duration, playlist_type)
                    fallback_tracks.extend(clean_fallback_tracks)
                    print(f"✅ Got {len(clean_fallback_tracks)} clean fallback tracks")
            except Exception as e:
                print(f"⚠️ Fallback search failed: {e}")
        
        # Now intelligently mix the tracks
        mixed_tracks = mix_tracks_intelligently(
            artist_tracks, recommendation_tracks, fallback_tracks, 
            target_duration_ms, favorite_artists
        )
        
        final_uris = [track['uri'] for track in mixed_tracks]
        final_duration = sum(track['duration_ms'] for track in mixed_tracks) / 60000
        
        print(f"✅ Search complete: {len(final_uris)} tracks, {final_duration:.1f} minutes")
        return final_uris
        
    except Exception as e:
        print(f"❌ Critical error in enhanced search: {e}")
        return []

def search_artist_popular_tracks_with_duration(artist_name, headers, limit=10):
    """Search for an artist's popular tracks and include duration info with explicit filtering"""
    try:
        print(f"🎤 Searching for popular tracks by: {artist_name}")
        
        # Find the artist
        search_url = "https://api.spotify.com/v1/search"
        params = {
            "q": f"artist:\"{artist_name}\"",
            "type": "artist",
            "limit": 1
        }
        
        res = requests.get(search_url, headers=headers, params=params)
        if res.status_code != 200:
            return []
        
        data = res.json()
        artists_data = data.get("artists", {}).get("items", [])
        if not artists_data:
            return []
        
        artist_id = artists_data[0]["id"]
        print(f"✅ Found artist {artist_name} with ID: {artist_id}")
        
        # Get artist's top tracks
        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
        params = {"market": "US"}
        
        res = requests.get(top_tracks_url, headers=headers, params=params)
        if res.status_code != 200:
            return []
        
        data = res.json()
        tracks = data.get("tracks", [])
        
        track_data = []
        for track in tracks[:limit]:
            if isinstance(track, dict) and "uri" in track:
                track_info = {
                    'uri': track["uri"],
                    'duration_ms': track.get("duration_ms", 210000),
                    'name': track.get("name", "Unknown"),
                    'artist': artist_name,
                    'explicit': track.get("explicit", False)  # Include explicit flag
                }
                track_data.append(track_info)
        
        print(f"✅ Found {len(track_data)} tracks for {artist_name}")
        return track_data
        
    except Exception as e:
        print(f"❌ Error searching artist popular tracks: {e}")
        return []

def filter_explicit_tracks(tracks, playlist_type):
    """
    Filter tracks based on explicit flag and playlist_type.
    tracks: list of dicts with at least 'explicit' key.
    playlist_type: "clean" or "explicit"
    Returns a filtered list of tracks.
    """
    if not isinstance(tracks, list):
        return []
    if playlist_type.lower() == "clean":
        return [track for track in tracks if not track.get("explicit", False)]
    elif playlist_type.lower() == "explicit":
        return [track for track in tracks if track.get("explicit", False)]
    else:
        return tracks

def get_tracks_with_duration(track_uris, headers):
    """Get track duration information for a list of URIs including explicit info"""
    try:
        track_data = []
        
        # Process in batches of 50 (Spotify API limit)
        batch_size = 50
        for i in range(0, len(track_uris), batch_size):
            batch_uris = track_uris[i:i + batch_size]
            track_ids = [uri.split(":")[-1] for uri in batch_uris if isinstance(uri, str)]
            
            if not track_ids:
                continue
            
            res = requests.get("https://api.spotify.com/v1/tracks", 
                              headers=headers, 
                              params={"ids": ",".join(track_ids)})
            
            if res.status_code == 200:
                data = res.json()
                tracks = data.get("tracks", [])
                
                for j, track in enumerate(tracks):
                    if track and isinstance(track, dict):
                        track_info = {
                            'uri': batch_uris[j] if j < len(batch_uris) else track.get("uri"),
                            'duration_ms': track.get("duration_ms", 210000),
                            'name': track.get("name", "Unknown"),
                            'artist': track.get("artists", [{}])[0].get("name", "Unknown"),
                            'explicit': track.get("explicit", False)  # Include explicit flag
                        }
                        track_data.append(track_info)
        
        return track_data
        
    except Exception as e:
        print(f"❌ Error getting track durations: {e}")
        return []

def search_high_quality_tracks(genre, headers, limit=20, mood_tags=None, 
                              search_keywords=None, playlist_type="clean"):
    """Search for high-quality tracks with better filtering"""
    try:
        search_url = "https://api.spotify.com/v1/search"
        
        # Build high-quality search queries
        queries = []
        
        # Query 1: Year-based search for recent hits
        queries.append(f"year:2023-2024 genre:{genre}")
        queries.append(f"year:2022-2023 genre:{genre}")
        
        # Query 2: Mood-based search
        if mood_tags:
            queries.append(f"{mood_tags} {genre}")
        
        # Query 3: Keyword search
        if search_keywords:
            queries.append(f"{search_keywords} {genre}")
        
        # Query 4: Popular artists in genre
        genre_artists = {
            "pop": ["Dua Lipa", "Olivia Rodrigo", "Harry Styles"],
            "hip-hop": ["Drake", "Kendrick Lamar", "Travis Scott"],
            "indie": ["Arctic Monkeys", "Tame Impala", "The 1975"],
            "rock": ["Imagine Dragons", "OneRepublic", "Maroon 5"]
        }
        
        if genre in genre_artists:
            for artist in genre_artists[genre]:
                queries.append(f"artist:\"{artist}\"")
        
        all_tracks = []
        tracks_per_query = max(2, limit // len(queries))
        
        for query in queries:
            if len(all_tracks) >= limit:
                break
                
            try:
                params = {
                    "q": query,
                    "type": "track",
                    "limit": min(tracks_per_query * 2, 20),
                    "market": "US"
                }
                
                res = requests.get(search_url, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    tracks = extract_tracks_from_search(data, playlist_type)
                    
                    # Filter out low-quality tracks
                    quality_tracks = filter_track_quality(tracks, headers)
                    
                    # Add unique tracks
                    for track in quality_tracks[:tracks_per_query]:
                        if track not in all_tracks and len(all_tracks) < limit:
                            all_tracks.append(track)
                    
                    print(f"✅ Query '{query[:30]}...' found {len(quality_tracks)} quality tracks")
                    
            except Exception as e:
                print(f"❌ Query failed: {e}")
                continue
        
        print(f"✅ High-quality search result: {len(all_tracks)} tracks")
        return all_tracks
        
    except Exception as e:
        print(f"❌ High-quality search failed: {e}")
        return []

def filter_track_quality(track_uris, headers):
    """Filter out low-quality tracks (instrumentals, very short/long tracks, etc.)"""
    try:
        if not track_uris:
            return []
        
        quality_tracks = []
        
        # Get track details
        track_data = get_tracks_with_duration(track_uris, headers)
        
        for track in track_data:
            # Filter criteria
            duration_ms = track['duration_ms']
            name = track['name'].lower()
            artist = track['artist'].lower()
            
            # Skip very short or very long tracks
            if duration_ms < 60000 or duration_ms > 420000:  # 1-7 minutes
                continue
            
            # Skip obvious instrumental/generic tracks
            skip_keywords = [
                'instrumental', 'karaoke', 'meditation', 'sleep', 'study music',
                'background music', 'royalty free', 'no copyright', 'clean pop music',
                'instrumentals for', 'upbeat study'
            ]
            
            if any(keyword in name for keyword in skip_keywords):
                continue
            
            if any(keyword in artist for keyword in skip_keywords):
                continue
            
            quality_tracks.append(track['uri'])
        
        return quality_tracks
        
    except Exception as e:
        print(f"❌ Error filtering track quality: {e}")
        return track_uris  # Return original if filtering fails

def calculate_playlist_duration(track_uris, headers):
    """Calculate total playlist duration in minutes"""
    try:
        track_data = get_tracks_with_duration(track_uris, headers)
        total_ms = sum(track['duration_ms'] for track in track_data)
        return total_ms / 60000  # Convert to minutes
    except Exception as e:
        print(f"❌ Error calculating duration: {e}")
        return 0

def mix_tracks_intelligently(artist_tracks, recommendation_tracks, fallback_tracks, 
                       target_duration_ms, favorite_artists):
    """Mix tracks intelligently to avoid clustering by artist"""
    try:
        print(f"🎭 Mixing tracks intelligently...")
        print(f"📊 Input: {len(artist_tracks)} artist, {len(recommendation_tracks)} recs, {len(fallback_tracks)} fallback")
        
        # Organize artist tracks by artist
        artist_buckets = {}
        for track in artist_tracks:
            artist = track.get('artist', 'Unknown')
            if artist not in artist_buckets:
                artist_buckets[artist] = []
            artist_buckets[artist].append(track)
        
        # Create the mixed playlist
        mixed_playlist = []
        current_duration = 0
        
        # Round-robin through artist buckets first
        max_rounds = max(len(bucket) for bucket in artist_buckets.values()) if artist_buckets else 0
        
        for round_num in range(max_rounds):
            if current_duration >= target_duration_ms:
                break
                
            # Add one track from each artist (if they have tracks left)
            for artist_name in favorite_artists:
                if current_duration >= target_duration_ms:
                    break
                    
                if artist_name in artist_buckets and len(artist_buckets[artist_name]) > round_num:
                    track = artist_buckets[artist_name][round_num]
                    mixed_playlist.append(track)
                    current_duration += track['duration_ms']
                    print(f"🎵 Added: {track['name']} by {track['artist']}")
                    
                    # Add 1-2 non-artist tracks after each artist track
                    non_artist_added = 0
                    
                    # Try recommendations first
                    for rec_track in recommendation_tracks:
                        if (current_duration >= target_duration_ms or 
                            non_artist_added >= 2 or 
                            rec_track in mixed_playlist):
                            break
                        
                        # Make sure it's not from a favorite artist
                        if not any(fav_artist.lower() in rec_track.get('artist', '').lower() 
                                  for fav_artist in favorite_artists):
                            mixed_playlist.append(rec_track)
                            current_duration += rec_track['duration_ms']
                            non_artist_added += 1
                            print(f"🔀 Added rec: {rec_track['name']} by {rec_track['artist']}")
                    
                    # Fill with fallback if needed
                    for fallback_track in fallback_tracks:
                        if (current_duration >= target_duration_ms or 
                            non_artist_added >= 2 or 
                            fallback_track in mixed_playlist):
                            break
                        
                        if not any(fav_artist.lower() in fallback_track.get('artist', '').lower() 
                                  for fav_artist in favorite_artists):
                            mixed_playlist.append(fallback_track)
                            current_duration += fallback_track['duration_ms']
                            non_artist_added += 1
                            print(f"🔄 Added fallback: {fallback_track['name']} by {fallback_track['artist']}")
        
        # Fill remaining time with any unused tracks
        all_remaining = [t for t in recommendation_tracks + fallback_tracks if t not in mixed_playlist]
        for track in all_remaining:
            if current_duration >= target_duration_ms:
                break
            mixed_playlist.append(track)
            current_duration += track['duration_ms']
        
        final_duration = current_duration / 60000
        print(f"🎭 Mixed playlist complete: {len(mixed_playlist)} tracks, {final_duration:.1f} minutes")
        
        return mixed_playlist
        
    except Exception as e:
        print(f"❌ Error mixing tracks: {e}")
        return artist_tracks + recommendation_tracks + fallback_tracks