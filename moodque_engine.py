from dotenv import load_dotenv
import os
import requests
import base64
import random
import uuid
from moodque_utilities import get_spotify_user_id, create_new_playlist

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
    
def get_spotify_user_id(headers):
    res = requests.get("https://api.spotify.com/v1/me", headers=headers)
    if res.status_code == 200:
        return res.json()["id"]
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

def remove_duplicates_and_filter(tracks, headers):
    """Simple duplicate removal"""
    try:
        if not tracks:
            return []
        
        # Ensure tracks is a list of URIs
        track_uris = []
        for track in tracks:
            if isinstance(track, dict) and "uri" in track:
                track_uris.append(track["uri"])
            elif isinstance(track, str):
                track_uris.append(track)
        
        if not track_uris:
            return []
        
        track_ids = [uri.split(":")[-1] for uri in track_uris]
        unique_tracks = []
        seen_artists = set()
        seen_track_names = set()
        
        batch_size = 20
        for i in range(0, min(len(track_ids), 50), batch_size):
            batch_ids = track_ids[i:i + batch_size]
            
            try:
                res = requests.get("https://api.spotify.com/v1/tracks", 
                                  headers=headers, 
                                  params={"ids": ",".join(batch_ids)},
                                  timeout=10)
                
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict):
                        batch_tracks = data.get("tracks", [])
                        
                        for j, track in enumerate(batch_tracks):
                            if not track or len(unique_tracks) >= 25:
                                continue
                            
                            track_name = track.get("name", "").lower()
                            artists = track.get("artists", [])
                            artist_name = artists[0].get("name", "").lower() if artists else ""
                            
                            # Limit to 2 tracks per artist
                            artist_count = sum(1 for seen in seen_artists if seen == artist_name)
                            if artist_count >= 2:
                                continue
                            
                            # Skip exact duplicates
                            if track_name not in seen_track_names:
                                unique_tracks.append(track_uris[i + j])
                                seen_artists.add(artist_name)
                                seen_track_names.add(track_name)
            except Exception as batch_error:
                print(f"⚠️ Batch error: {batch_error}")
                continue
        
        print(f"🔍 Filtered: {len(track_uris)} → {len(unique_tracks)} tracks")
        return unique_tracks
    except Exception as e:
        print(f"❌ Error in filtering: {e}")
        return tracks[:20] if isinstance(tracks, list) else []

def get_recommendations_enhanced(headers, limit=20, seed_genres=None, seed_artists=None, mood_params=None):
    """Fixed recommendations API call"""
    rec_url = "https://api.spotify.com/v1/recommendations"
    
    params = {
        "limit": min(limit, 20),
        "market": "US"
    }
    
    # Add seeds carefully
    seeds_used = 0
    
    if seed_genres and seeds_used < 5:
        genres_to_use = seed_genres[:2]  # Max 2 genres
        params["seed_genres"] = ",".join(genres_to_use)
        seeds_used += len(genres_to_use)
        print(f"🎵 Using genre seeds: {genres_to_use}")
    
    if seed_artists and seeds_used < 4:
        artists_to_use = seed_artists[:1]  # Only 1 artist
        params["seed_artists"] = ",".join(artists_to_use)
        seeds_used += len(artists_to_use)
        print(f"🎤 Using artist seeds: {artists_to_use}")
    
    # Only use basic mood parameters
    if mood_params:
        if "target_energy" in mood_params:
            params["target_energy"] = mood_params["target_energy"]
        if "target_valence" in mood_params:
            params["target_valence"] = mood_params["target_valence"]
        print(f"😊 Using mood params: energy={params.get('target_energy')}, valence={params.get('target_valence')}")
    
    print(f"🎯 API call with {seeds_used} seeds")
    
    try:
        res = requests.get(rec_url, headers=headers, params=params, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                tracks = data.get("tracks", [])
                track_uris = [track["uri"] for track in tracks if isinstance(track, dict) and "uri" in track]
                print(f"✅ Recommendations SUCCESS: Got {len(track_uris)} tracks")
                return track_uris
            else:
                print(f"❌ Invalid recommendations response format")
                return []
        else:
            print(f"❌ Recommendations failed: {res.status_code} - {res.text}")
            return []
    except Exception as e:
        print(f"❌ Exception in recommendations: {e}")
        return []

def get_mood_search_terms(mood):
    """Get search terms for different moods"""
    mood_terms = {
        "happy": ["upbeat", "cheerful", "joyful", "celebration", "positive"],
        "chill": ["chill", "relaxing", "calm", "peaceful", "mellow"],
        "upbeat": ["energetic", "upbeat", "pump up", "high energy", "motivational"],
        "energetic": ["energetic", "pump up", "high energy", "motivational", "intense"],
        "focus": ["focus", "concentration", "study", "instrumental", "ambient"],
        "party": ["party", "dance", "club", "celebration", "fun"],
        "hype": ["hype", "pump up", "energy", "motivation", "intense"],
        "melancholy": ["sad", "emotional", "melancholy", "slow", "reflective"],
        "workout": ["workout", "gym", "fitness", "training", "exercise"],
        "romantic": ["love", "romantic", "intimate", "sweet", "tender"]
    }
    return mood_terms.get(mood.lower(), ["music"])

def search_spotify_tracks_fallback(genre, headers, limit=20, mood_tags=None, 
                                 search_keywords=None, playlist_type="clean"):
    """Fallback search using text-based queries"""
    search_url = "https://api.spotify.com/v1/search"
    
    # Build search queries
    search_queries = []
    
    if genre:
        search_queries.append(f"genre:{genre}")
    
    if mood_tags:
        mood_terms = get_mood_search_terms(mood_tags)
        for term in mood_terms[:2]:
            if genre:
                search_queries.append(f"genre:{genre} {term}")
            else:
                search_queries.append(term)
    
    if search_keywords:
        keywords = search_keywords.split()
        for keyword in keywords[:2]:
            if genre:
                search_queries.append(f"genre:{genre} {keyword}")
            else:
                search_queries.append(keyword)
    
    if not search_queries:
        search_queries = ["popular music", "trending"]
    
    print(f"🔍 Fallback search queries: {search_queries}")
    
    all_tracks = []
    tracks_per_query = max(1, limit // len(search_queries))
    
    for query in search_queries:
        if len(all_tracks) >= limit:
            break
            
        params = {
            "q": query,
            "type": "track",
            "limit": min(tracks_per_query + 10, 50),
            "market": "US"
        }
        
        try:
            res = requests.get(search_url, headers=headers, params=params)
            
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    tracks_data = data.get("tracks", {})
                    if isinstance(tracks_data, dict):
                        tracks = tracks_data.get("items", [])
                        
                        for track in tracks:
                            if len(all_tracks) >= limit:
                                break
                                
                            if not isinstance(track, dict):
                                continue
                                
                            is_explicit = track.get("explicit", False)
                            
                            # Filter by explicit content
                            if playlist_type.lower() == "clean" and is_explicit:
                                continue
                            elif playlist_type.lower() == "explicit" and not is_explicit:
                                continue
                            
                            track_uri = track.get("uri")
                            if track_uri and track_uri not in [t.get("uri") for t in all_tracks]:
                                artists = track.get("artists", [])
                                artist_name = artists[0].get("name", "Unknown") if artists else "Unknown"
                                
                                all_tracks.append({
                                    "uri": track_uri,
                                    "name": track.get("name"),
                                    "artist": artist_name,
                                    "popularity": track.get("popularity", 0),
                                    "explicit": is_explicit
                                })
        except Exception as e:
            print(f"❌ Error in fallback search for query '{query}': {e}")
            continue
    
    # Sort by popularity
    all_tracks.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    track_uris = [track["uri"] for track in all_tracks[:limit]]
    
    print(f"✅ Fallback search: Found {len(track_uris)} tracks")
    return track_uris

def filter_explicit_content(track_uris, headers, playlist_type):
    """Filter tracks based on explicit content preference"""
    if not track_uris or playlist_type.lower() == "any":
        return track_uris
    
    # Ensure track_uris is a list of strings
    if isinstance(track_uris, str):
        track_uris = [track_uris]
    elif not isinstance(track_uris, list):
        return []
    
    track_ids = []
    for uri in track_uris:
        if isinstance(uri, str) and ":" in uri:
            track_ids.append(uri.split(":")[-1])
    
    if not track_ids:
        return []
    
    filtered_uris = []
    batch_size = 50
    
    for i in range(0, len(track_ids), batch_size):
        batch_ids = track_ids[i:i + batch_size]
        
        try:
            res = requests.get("https://api.spotify.com/v1/tracks", 
                              headers=headers, 
                              params={"ids": ",".join(batch_ids)})
            
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    tracks = data.get("tracks", [])
                    
                    for j, track in enumerate(tracks):
                        if track and isinstance(track, dict):
                            is_explicit = track.get("explicit", False)
                            original_uri = track_uris[i + j] if i + j < len(track_uris) else None
                            
                            if original_uri:
                                if playlist_type.lower() == "clean" and not is_explicit:
                                    filtered_uris.append(original_uri)
                                elif playlist_type.lower() == "explicit" and is_explicit:
                                    filtered_uris.append(original_uri)
        except Exception as e:
            print(f"❌ Error filtering explicit content: {e}")
    
    print(f"🔍 Content filter: {len(track_uris)} → {len(filtered_uris)} tracks ({playlist_type})")
    return filtered_uris

# Add this updated function to your moodque_engine.py

def search_spotify_tracks_enhanced(genre, headers, limit=20, mood_tags=None, 
                                 search_keywords=None, playlist_type="clean", 
                                 favorite_artist=None, use_lastfm=False):
    """Enhanced search with improved Last.fm fallback and better error handling"""
    try:
        print(f"🔍 Enhanced search - Genre: {genre}, Mood: {mood_tags}")
        
        # Last.fm Strategy (with improved fallback)
        if use_lastfm and favorite_artist:
            print(f"🎯 Attempting Last.fm + Spotify search for: {favorite_artist}")
            try:
                from lastfm_helpers import get_similar_artists, get_top_tracks, test_lastfm_connection
                from moodque_utilities import search_spotify_track

                # First test if Last.fm is working
                if not test_lastfm_connection():
                    print("⚠️ Last.fm API test failed, skipping Last.fm strategy")
                else:
                    # Try to get similar artists
                    similar_artists = get_similar_artists(favorite_artist, limit=5)
                    artist_list = [favorite_artist] + similar_artists
                    
                    print(f"🎤 Artist list for search: {artist_list}")
                    
                    all_candidates = []
                    for artist in artist_list[:6]:  # Limit to 6 artists
                        tracks = get_top_tracks(artist, limit=3)
                        all_candidates.extend(tracks)
                        if len(all_candidates) >= limit * 2:  # Get more candidates than needed
                            break

                    print(f"🎼 Total track candidates from Last.fm: {len(all_candidates)}")
                    
                    all_tracks = []
                    for title, artist in all_candidates[:limit * 2]:  # Try more than we need
                        uri = search_spotify_track(artist, title, headers)
                        if uri:
                            all_tracks.append(uri)
                        if len(all_tracks) >= limit:
                            break

                    if all_tracks:
                        print(f"✅ Last.fm + Spotify search complete: {len(all_tracks)} tracks")
                        return all_tracks
                    else:
                        print("⚠️ Last.fm search found no Spotify matches, falling back to regular search")
                        
            except ImportError as e:
                print(f"❌ Last.fm helpers not available: {e}")
            except Exception as e:
                print(f"❌ Last.fm search failed: {e}")

        # Regular Spotify Strategy (improved)
        print("🎯 Using regular Spotify search strategy...")
        
        # Parse genres
        if isinstance(genre, str) and ',' in genre:
            spotify_genres = parse_genre_list(genre)
        else:
            spotify_genre = sanitize_genre(genre) if genre else "pop"
            spotify_genres = [spotify_genre]
        
        # Get artist IDs for seed
        artist_ids = []
        if favorite_artist:
            try:
                artist_ids = get_artist_ids(favorite_artist, headers)
                print(f"🎤 Found artist IDs: {len(artist_ids)}")
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
        print("🎯 Trying Spotify Recommendations API...")
        try:
            rec_tracks = get_recommendations_enhanced(
                headers=headers,
                limit=limit,
                seed_genres=spotify_genres,
                seed_artists=artist_ids,
                mood_params=mood_params
            )
            
            if rec_tracks:
                all_tracks.extend(rec_tracks)
                print(f"✅ Got {len(rec_tracks)} tracks from recommendations")
        except Exception as e:
            print(f"⚠️ Recommendations failed: {e}")
        
        # Strategy 2: Search for favorite artist's popular songs if we have one
        if favorite_artist and len(all_tracks) < limit * 0.5:
            print(f"🎯 Searching for popular tracks by {favorite_artist}...")
            try:
                artist_search_tracks = search_artist_popular_tracks(favorite_artist, headers, limit // 2)
                if artist_search_tracks:
                    all_tracks.extend(artist_search_tracks)
                    print(f"✅ Got {len(artist_search_tracks)} tracks from artist search")
            except Exception as e:
                print(f"⚠️ Artist popular tracks search failed: {e}")
        
        # Strategy 3: Fallback to general search if needed
        if len(all_tracks) < limit * 0.7:
            print("🔄 Using general search fallback...")
            try:
                fallback_tracks = search_spotify_tracks_fallback(
                    spotify_genres[0], 
                    headers, 
                    limit - len(all_tracks),
                    mood_tags, 
                    search_keywords, 
                    playlist_type
                )
                if fallback_tracks:
                    all_tracks.extend(fallback_tracks)
                    print(f"✅ Got {len(fallback_tracks)} tracks from fallback")
            except Exception as e:
                print(f"⚠️ Fallback search failed: {e}")
        
        # Deduping and filtering
        if len(all_tracks) > limit:
            try:
                filtered_tracks = remove_duplicates_and_filter(all_tracks, headers)
            except Exception as e:
                print(f"⚠️ Duplicate removal failed: {e}")
                filtered_tracks = all_tracks
        else:
            filtered_tracks = all_tracks
        
        # Filter explicit content
        try:
            final_tracks = filter_explicit_content(filtered_tracks, headers, playlist_type)
        except Exception as e:
            print(f"⚠️ Explicit filter failed: {e}")
            final_tracks = filtered_tracks
        
        result = final_tracks[:limit] if isinstance(final_tracks, list) else []
        print(f"✅ Enhanced search complete: {len(result)} tracks")
        return result
        
    except Exception as e:
        print(f"❌ Error in enhanced search: {e}")
        # Ultimate fallback
        try:
            fallback = search_spotify_tracks_fallback("pop", headers, limit, mood_tags, search_keywords, playlist_type)
            return fallback if isinstance(fallback, list) else []
        except Exception as e:
            print(f"❌ Ultimate fallback failed: {e}")
            return []

def search_artist_popular_tracks(artist_name, headers, limit=10):
    """Search for an artist's popular tracks directly on Spotify"""
    try:
        # First find the artist
        search_url = "https://api.spotify.com/v1/search"
        params = {
            "q": f"artist:{artist_name}",
            "type": "artist",
            "limit": 1
        }
        
        res = requests.get(search_url, headers=headers, params=params)
        if res.status_code != 200:
            return []
        
        data = res.json()
        artists = data.get("artists", {}).get("items", [])
        if not artists:
            return []
        
        artist_id = artists[0]["id"]
        print(f"🎤 Found artist {artist_name} with ID: {artist_id}")
        
        # Get artist's top tracks
        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
        params = {"market": "US"}
        
        res = requests.get(top_tracks_url, headers=headers, params=params)
        if res.status_code != 200:
            return []
        
        data = res.json()
        tracks = data.get("tracks", [])
        
        track_uris = []
        for track in tracks[:limit]:
            if isinstance(track, dict) and "uri" in track:
                track_uris.append(track["uri"])
        
        print(f"🎼 Found {len(track_uris)} popular tracks for {artist_name}")
        return track_uris
        
    except Exception as e:
        print(f"❌ Error searching artist popular tracks: {e}")
        return []