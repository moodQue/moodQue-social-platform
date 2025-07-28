# complete_moodque_engine.py - Full Featured MoodQue Engine

from firebase_admin import firestore

def get_user_id_from_spotify_id(spotify_user_id):
    db = firestore.client()
    users_ref = db.collection("users")
    query = users_ref.where("spotify_user_id", "==", spotify_user_id).limit(1).stream()

    for doc in query:
        return doc.id  # Or use doc.to_dict().get("user_id") if stored inside

    return None

from lastfm_recommender import get_recommendations, get_similar_artists, get_genre_seed_artists
import os
import requests
import base64
import random
import uuid
import json
import traceback
from datetime import datetime
import logging

# Import Firebase initialization
import firebase_admin_init
from firebase_admin_init import db

# Import tracking
from tracking import track_interaction

# Import utilities
from moodque_utilities import (
    get_valid_access_token,
    get_spotify_user_id,
    create_new_playlist,
    add_tracks_to_playlist,
    calculate_playlist_duration,
    search_spotify_track
)

# Load .env only in local dev
if os.environ.get("RAILWAY_ENVIRONMENT") is None:
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=".env")
        logging.info("✅ .env loaded for local development")
    except ImportError:
        logging.warning("⚠️ dotenv not installed – skipping .env load")

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

class MoodQueEngine:
    """Main class for building MoodQue playlists with Spotify integration"""
    
    def __init__(self, request_data):
        """Initialize with clean request data"""
        self.request_data = request_data
        
        # FIXED: Handle user_id properly with fallbacks
        self.user_id = (request_data.get('user_id') or 
                       request_data.get('userId') or 
                       'anonymous')
        
        # CRITICAL: Get request_id but DO NOT generate fallback UUID
        self.request_id = (request_data.get('request_id') or 
                          request_data.get('row_id') or 
                          request_data.get('id') or 
                          request_data.get('rowID'))
        
        # CRITICAL: If no request_id found, raise an error instead of generating UUID
        if not self.request_id:
            error_msg = f"❌ CRITICAL: No request_id found in MoodQueEngine initialization"
            print(error_msg)
            print(f"📋 Available keys: {list(request_data.keys())}")
            raise ValueError("request_id is required but not provided")
        
        print(f"✅ Using provided request_id: {self.request_id}")
        
        self.logger_prefix = f"[{self.request_id}]"
        
        # FIXED: Extract and validate parameters with better fallback handling
        self.event_name = (request_data.get('event_name') or 
                          request_data.get('event') or 
                          "Untitled MoodQue Mix")
        
        self.genre = request_data.get('genre', 'pop')
        
        # FIXED: Handle time parameter conversion safely
        try:
            self.time_minutes = int(request_data.get('time', 30))
        except (ValueError, TypeError):
            self.time_minutes = 30
            
        self.mood_tags = request_data.get('mood_tags') or request_data.get('mood')
        self.search_keywords = request_data.get('search_keywords')
        
        # FIXED: Handle favorite_artist with multiple possible keys
        self.favorite_artist = (request_data.get('favorite_artist') or 
                               request_data.get('artist'))
        
        self.playlist_type = request_data.get('playlist_type', 'clean')
        
        # FIXED: Handle birth_year safely
        self.birth_year = request_data.get('birth_year')
        if self.birth_year:
            try:
                self.birth_year = int(self.birth_year)
            except (ValueError, TypeError):
                self.birth_year = None
        
        # Initialize components
        self.access_token = None
        self.headers = None
        self.spotify_user_id = None
        
        # Results storage
        self.artist_pool = []
        self.track_candidates = []
        self.final_playlist = []
        
        # Audio feature parameters for mood matching
        self.mood_audio_params = self._get_mood_audio_params()
        
        print(f"{self.logger_prefix} 🚀 MoodQue Engine Initialized")
        print(f"{self.logger_prefix} 📋 Parameters: {self._format_parameters()}")

    def _format_parameters(self):
        """Format parameters for logging"""
        return {
            'request_id': self.request_id,
            'user_id': self.user_id,
            'event': self.event_name,
            'genre': self.genre,
            'time': f"{self.time_minutes}min",
            'mood': self.mood_tags,
            'keywords': self.search_keywords,
            'artist': self.favorite_artist,
            'filter': self.playlist_type,
            'birth_year': self.birth_year
        }

    def _get_mood_audio_params(self):
        """Get audio feature parameters based on mood"""
        if not self.mood_tags:
            return {}
        
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
        return mood_map.get(self.mood_tags.lower(), {}) if self.mood_tags else {}

    def authenticate_spotify(self):
        """Handle Spotify authentication with proper fallback"""
        print(f"{self.logger_prefix} 🔐 Authenticating with Spotify...")
        
        # Try user token first
        if self.user_id and self.user_id != 'unknown':
            try:
                from spotify_token_manager import refresh_access_token
                self.access_token = refresh_access_token(self.user_id)
                if self.access_token:
                    print(f"{self.logger_prefix} ✅ User token authenticated for {self.user_id}")
                    self.headers = {"Authorization": f"Bearer {self.access_token}"}
                    self.spotify_user_id = get_spotify_user_id(self.headers)
                    return True
            except Exception as e:
                print(f"{self.logger_prefix} ⚠️ User token failed: {e}")
        
        # Fallback to system token
        try:
            from moodque_auth import get_spotify_access_token
            self.access_token = get_spotify_access_token()
            if self.access_token:
                print(f"{self.logger_prefix} ✅ System token authenticated")
                self.headers = {"Authorization": f"Bearer {self.access_token}"}
                self.spotify_user_id = get_spotify_user_id(self.headers)
                return True
        except Exception as e:
            print(f"{self.logger_prefix} ❌ System token failed: {e}")
        
        return False

    def analyze_era_preferences(self):
        """Analyze user preferences and determine era weights"""
        print(f"{self.logger_prefix} 📊 Analyzing era preferences...")
        
        era_weights = {'2020s': 1.0, '2010s': 0.7, '2000s': 0.5, '1990s': 0.3, '1980s': 0.2}
        
        # Adjust based on birth year
        if self.birth_year:
            try:
                birth_year = int(self.birth_year)
                current_year = datetime.now().year
                age = current_year - birth_year
                
                # People tend to prefer music from their teens/early 20s
                if age >= 15:  # Old enough to have musical preferences
                    formative_decade = f"{((birth_year + 18) // 10) * 10}s"
                    if formative_decade in era_weights:
                        era_weights[formative_decade] = min(1.5, era_weights.get(formative_decade, 0.1) + 0.8)
                        print(f"{self.logger_prefix} 🎯 Boosted {formative_decade} weight for age {age}")
                
            except (ValueError, TypeError):
                print(f"{self.logger_prefix} ⚠️ Invalid birth year: {self.birth_year}")
        
        # Adjust based on mood
        if self.mood_tags:
            mood_lower = self.mood_tags.lower()
            if any(word in mood_lower for word in ['nostalgic', 'throwback', 'classic', 'retro']):
                # Boost older eras
                era_weights['2000s'] = min(1.2, era_weights['2000s'] + 0.4)
                era_weights['1990s'] = min(1.0, era_weights['1990s'] + 0.4)
                print(f"{self.logger_prefix} 🕰️ Boosted retro eras for nostalgic mood")
            elif any(word in mood_lower for word in ['trending', 'current', 'new', 'fresh']):
                # Boost current era
                era_weights['2020s'] = 1.5
                print(f"{self.logger_prefix} 🆕 Boosted current era for fresh mood")
        
        print(f"{self.logger_prefix} ⚖️ Era weights: {era_weights}")
        return era_weights

    def discover_artists_lastfm(self, era_weights):
        """Use Last.fm to discover target artists and similar artists"""
        print(f"{self.logger_prefix} 🎭 Discovering artists via Last.fm...")
        
        target_artists = []
        
        # Add favorite artist if provided
        if self.favorite_artist:
            if isinstance(self.favorite_artist, str):
                artists_list = [a.strip() for a in self.favorite_artist.split(',') if a.strip()]
            else:
                artists_list = [self.favorite_artist] if self.favorite_artist else []
            
            target_artists.extend(artists_list[:3])  # Limit to 3 favorites
            print(f"{self.logger_prefix} ⭐ Added favorite artists: {target_artists}")
        
        # If no favorite artists, get genre-based seeds
        if not target_artists:
            target_artists = get_genre_seed_artists(self.genre, limit=2)
            print(f"{self.logger_prefix} 🎵 Using genre seed artists: {target_artists}")
        
        # Get similar artists for each target artist
        similar_artists = []
        for artist in target_artists:
            try:
                similar = get_similar_artists(artist, limit=5)
                similar_artists.extend(similar)
                print(f"{self.logger_prefix} 🔗 Found {len(similar)} similar to {artist}")
            except Exception as e:
                print(f"{self.logger_prefix} ⚠️ Similar artist search failed for {artist}: {e}")
        
        # Get genre-based artist recommendations
        try:
            genre_artists = get_recommendations(
                seed_artists=target_artists,
                genre=self.genre,
                birth_year=self.birth_year,
                era_weights=era_weights,
                limit=20,
                return_artists_only=True
            )
            print(f"{self.logger_prefix} 🎵 Found {len(genre_artists)} genre-based artists")
            similar_artists.extend([a['artist'] for a in genre_artists])
        except Exception as e:
            print(f"{self.logger_prefix} ⚠️ Genre artist discovery failed: {e}")
        
        # Combine and deduplicate
        self.artist_pool = list(set(target_artists + similar_artists))
        print(f"{self.logger_prefix} 👥 Artist pool: {len(self.artist_pool)} unique artists")
        return self.artist_pool
    
    def select_tracks_with_logic(self, era_weights):
        """Use ML logic and user parameters to select optimal tracks"""
        print(f"{self.logger_prefix} 🧠 Selecting tracks with intelligent logic...")

        seed_artists = self.artist_pool[:3]
        similar_artists = list(set(self.artist_pool) - set(seed_artists))

        try:
            seed_tracks = get_recommendations(
                seed_artists=seed_artists,
                genre=self.genre,
                birth_year=self.birth_year,
                era_weights=era_weights,
                limit=int(self.time_minutes * 3 * 0.65)
            )

            similar_tracks = get_recommendations(
                seed_artists=similar_artists,
                genre=self.genre,
                birth_year=self.birth_year,
                era_weights=era_weights,
                limit=int(self.time_minutes * 3 * 0.35)
            )

            lastfm_tracks = seed_tracks + similar_tracks
            print(f"{self.logger_prefix} 🎼 Last.fm returned {len(lastfm_tracks)} track recommendations (seed={len(seed_tracks)}, similar={len(similar_tracks)})")

        except Exception as e:
            print(f"{self.logger_prefix} ❌ Last.fm track selection failed: {e}")
            lastfm_tracks = []

        # Apply user-specific filtering
            filtered_candidates = self._apply_user_filters(lastfm_tracks)

        # Apply mood-based scoring
            mood_scored_tracks = self._apply_mood_scoring(filtered_candidates)

        # Apply time-based selection
            self.track_candidates = self._select_by_duration(mood_scored_tracks)

            print(f"{self.logger_prefix} ✅ Selected {len(self.track_candidates)} track candidates")

            return self.track_candidates



    def _apply_user_filters(self, tracks):
        """Apply user-specific filters based on preferences"""
        if not tracks:
            return []
        
        filtered = []
        
        for track in tracks:
            # Skip if no required data
            if not track.get('artist') or not track.get('track'):
                continue
            
            # Apply search keyword filtering
            if self.search_keywords:
                keywords_lower = self.search_keywords.lower()
                track_text = f"{track.get('track', '')} {track.get('artist', '')}".lower()
                if keywords_lower not in track_text:
                    continue
            
            filtered.append(track)
        
        print(f"{self.logger_prefix} 🔍 User filters applied: {len(tracks)} → {len(filtered)}")
        return filtered

    def _apply_mood_scoring(self, tracks):
        """Apply mood-based scoring to prioritize tracks"""
        if not tracks or not self.mood_tags:
            return tracks
        
        mood_keywords = {
            'happy': ['happy', 'joy', 'celebration', 'upbeat', 'cheerful', 'bright'],
            'energetic': ['energy', 'power', 'dynamic', 'intense', 'strong', 'vigorous'],
            'chill': ['chill', 'relaxed', 'calm', 'peaceful', 'mellow', 'smooth'],
            'party': ['party', 'dance', 'club', 'celebration', 'fun', 'wild'],
            'romantic': ['love', 'romance', 'heart', 'romantic', 'intimate', 'tender'],
            'workout': ['workout', 'fitness', 'training', 'exercise', 'pump', 'motivate'],
            'focus': ['focus', 'concentrate', 'study', 'work', 'productivity', 'ambient'],
            'melancholy': ['sad', 'melancholy', 'blue', 'emotional', 'reflective', 'somber']
        }
        
        mood_lower = self.mood_tags.lower()
        relevant_keywords = []
        
        for mood, keywords in mood_keywords.items():
            if mood in mood_lower:
                relevant_keywords.extend(keywords)
        
        # Score tracks based on mood keywords
        for track in tracks:
            score = track.get('score', 0.5)
            track_name = track.get('track', '').lower()
            
            # Boost score if track name contains mood keywords
            for keyword in relevant_keywords:
                if keyword in track_name:
                    score += 0.1
                    break
            
            track['mood_score'] = score
        
        # Sort by mood score
        scored_tracks = sorted(tracks, key=lambda x: x.get('mood_score', 0), reverse=True)
        print(f"{self.logger_prefix} 😊 Applied mood scoring for '{self.mood_tags}'")
        return scored_tracks

    def _select_by_duration(self, tracks):
        """Select tracks to match target duration"""
        if not tracks:
            return []
        
        target_duration_ms = self.time_minutes * 60 * 1000
        avg_track_duration = 3.5 * 60 * 1000  # 3.5 minutes average
        target_track_count = int(target_duration_ms / avg_track_duration)
        
        # Take top tracks up to target count with some buffer
        selected = tracks[:int(target_track_count * 1.5)]
        
        print(f"{self.logger_prefix} ⏱️ Duration selection: targeting {target_track_count} tracks")
        return selected

    def find_spotify_tracks(self):
        """Search for tracks on Spotify and validate availability"""
        print(f"{self.logger_prefix} 🔍 Finding tracks on Spotify...")
        
        spotify_tracks = []
        not_found_count = 0
        
        for track_data in self.track_candidates:
            try:
                artist = track_data.get('artist', '')
                track_name = track_data.get('track', '')
                
                if not artist or not track_name:
                    continue
                
                # Search for track on Spotify
                spotify_uri = search_spotify_track(artist, track_name, self.headers)
                
                if spotify_uri:
                    # Get full track details
                    track_details = self._get_spotify_track_details(spotify_uri)
                    if track_details:
                        # Apply explicit content filter
                        if self._passes_content_filter(track_details):
                            # Apply quality filter
                            if self._passes_quality_filter(track_details):
                                track_data['spotify_uri'] = spotify_uri
                                track_data['spotify_details'] = track_details
                                spotify_tracks.append(track_data)
                            else:
                                print(f"{self.logger_prefix} 🚫 Quality filtered: {artist} - {track_name}")
                        else:
                            print(f"{self.logger_prefix} 🚫 Content filtered: {artist} - {track_name}")
                    else:
                        not_found_count += 1
                else:
                    not_found_count += 1
                    
            except Exception as e:
                print(f"{self.logger_prefix} ⚠️ Error searching for track: {e}")
                not_found_count += 1
        
        # If we have too few tracks, use fallback search
        if len(spotify_tracks) < 5:
            print(f"{self.logger_prefix} ⚠️ Too few tracks found ({len(spotify_tracks)}), using fallback search...")
            fallback_tracks = self._fallback_spotify_search()
            spotify_tracks.extend(fallback_tracks)
        
        print(f"{self.logger_prefix} ✅ Spotify search complete: {len(spotify_tracks)} found, {not_found_count} not found")
        self.final_playlist = self._optimize_playlist_order(spotify_tracks)
        return self.final_playlist

    def _get_spotify_track_details(self, spotify_uri):
        """Get detailed track information from Spotify"""
        try:
            track_id = spotify_uri.split(':')[-1]
            response = requests.get(
                f"https://api.spotify.com/v1/tracks/{track_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            print(f"{self.logger_prefix} ❌ Error getting track details: {e}")
            return None

    def _passes_content_filter(self, track_details):
        """Check if track passes content filter"""
        if not track_details:
            return False
        
        is_explicit = track_details.get('explicit', False)
        
        if self.playlist_type.lower() == 'clean' and is_explicit:
            return False
        elif self.playlist_type.lower() == 'explicit' and not is_explicit:
            return False
        
        return True

    def _passes_quality_filter(self, track_details):
        """Filter out low-quality tracks"""
        if not track_details:
            return False
        
        # Check duration (1-7 minutes)
        duration_ms = track_details.get('duration_ms', 0)
        if duration_ms < 60000 or duration_ms > 420000:
            return False
        
        # Check for low-quality indicators in name
        track_name = track_details.get('name', '').lower()
        quality_blacklist = [
            'instrumental', 'karaoke', 'meditation', 'sleep music',
            'background music', 'royalty free', 'no copyright',
            'clean version', 'radio edit'
        ]
        
        if any(term in track_name for term in quality_blacklist):
            return False
        
        return True

    def _fallback_spotify_search(self):
        """Fallback search when not enough tracks are found"""
        print(f"{self.logger_prefix} 🚨 Running fallback Spotify search...")
        
        fallback_tracks = []
        search_url = "https://api.spotify.com/v1/search"
        
        # Multiple search strategies
        search_queries = []
        
        # Strategy 1: Genre-based search
        spotify_genre = self._sanitize_genre(self.genre)
        if spotify_genre:
            search_queries.append(f"genre:{spotify_genre}")
        
        # Strategy 2: Mood-based search
        if self.mood_tags:
            search_queries.append(self.mood_tags)
        
        # Strategy 3: Year-based search
        current_year = datetime.now().year
        search_queries.append(f"year:{current_year}")
        search_queries.append(f"year:{current_year-1}")
        
        for query in search_queries:
            if len(fallback_tracks) >= 10:
                break
                
            try:
                params = {
                    "q": query,
                    "type": "track",
                    "limit": 10,
                    "market": "US"
                }
                
                response = requests.get(search_url, headers=self.headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    tracks = data.get('tracks', {}).get('items', [])
                    
                    for track in tracks:
                        if len(fallback_tracks) >= 10:
                            break
                        
                        if self._passes_content_filter(track) and self._passes_quality_filter(track):
                            fallback_track = {
                                'artist': track['artists'][0]['name'],
                                'track': track['name'],
                                'spotify_uri': track['uri'],
                                'spotify_details': track,
                                'score': 0.5,
                                'source': 'fallback'
                            }
                            fallback_tracks.append(fallback_track)
                            
            except Exception as e:
                print(f"{self.logger_prefix} ❌ Fallback search query failed: {e}")
        
        print(f"{self.logger_prefix} ✅ Fallback search found {len(fallback_tracks)} tracks")
        return fallback_tracks

    def _sanitize_genre(self, genre):
        """Map app genres to valid Spotify genres"""
        if not genre or genre.lower() == "any":
            return None
            
        genre_clean = genre.strip().lower().replace(" ", "-")
        
        # Check if it's directly in our mapping
        if genre_clean in GENRE_MAPPING:
            spotify_genre = GENRE_MAPPING[genre_clean]
            return spotify_genre
        
        # Check if it's already a valid Spotify genre
        if genre_clean in SPOTIFY_VALID_GENRES:
            return genre_clean
        
        # Fallback: try to find a similar genre
        for valid_genre in SPOTIFY_VALID_GENRES:
            if genre_clean in valid_genre or valid_genre in genre_clean:
                return valid_genre
        
        return "pop"

    def _optimize_playlist_order(self, tracks):
        """Optimize the order of tracks to avoid artist clustering"""
        if len(tracks) <= 3:
            return tracks
        
        print(f"{self.logger_prefix} 🎭 Optimizing playlist order...")
        
        # Group tracks by artist
        artist_groups = {}
        for track in tracks:
            artist = track.get('artist', 'Unknown')
            if artist not in artist_groups:
                artist_groups[artist] = []
            artist_groups[artist].append(track)
        
        # If mostly single tracks per artist, just shuffle
        if len(artist_groups) >= len(tracks) * 0.8:
            optimized = tracks.copy()
            random.shuffle(optimized)
            return optimized
        
        # Distribute tracks to avoid clustering
        optimized = []
        max_rounds = max(len(group) for group in artist_groups.values())
        
        for round_num in range(max_rounds):
            for artist, group in artist_groups.items():
                if round_num < len(group):
                    optimized.append(group[round_num])
        
        print(f"{self.logger_prefix} ✅ Playlist order optimized")
        return optimized

    def create_spotify_playlist(self):
        """Create the final Spotify playlist"""
        print(f"{self.logger_prefix} 🎵 Creating Spotify playlist...")
        
        if not self.final_playlist:
            print(f"{self.logger_prefix} ❌ No tracks available for playlist creation")
            return None
        
        if not self.spotify_user_id:
            print(f"{self.logger_prefix} ❌ No Spotify user ID available")
            return None
        
        # Create playlist
        playlist_id = create_new_playlist(
            self.headers,
            self.spotify_user_id,
            self.event_name,
            f"MoodQue playlist for {self.event_name}"
        )
        
        if not playlist_id:
            print(f"{self.logger_prefix} ❌ Failed to create playlist")
            return None
        
        # Extract URIs and add tracks
        track_uris = [track['spotify_uri'] for track in self.final_playlist if track.get('spotify_uri')]
        
        if not track_uris:
            print(f"{self.logger_prefix} ❌ No valid track URIs")
            return None
        
        success = add_tracks_to_playlist(self.headers, self.spotify_user_id, playlist_id, track_uris)
        
        if success:
            playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
            
            # Calculate actual duration
            total_duration = sum(
                track.get('spotify_details', {}).get('duration_ms', 210000)
                for track in self.final_playlist
            ) / 60000
            
            print(f"{self.logger_prefix} ✅ Playlist created: {len(track_uris)} tracks, {total_duration:.1f} minutes")
            print(f"{self.logger_prefix} 🔗 URL: {playlist_url}")
            
            # Track interaction
            try:
                track_interaction(
                    user_id=self.user_id,
                    event_type="built_playlist",
                    data={
                        "playlist_id": playlist_id,
                        "mood_tags": [self.mood_tags] if self.mood_tags else [],
                        "genres": [self.genre] if self.genre else [],
                        "event": self.event_name,
                        "track_count": len(track_uris),
                        "duration_minutes": total_duration
                    }
                )
            except Exception as e:
                print(f"{self.logger_prefix} ⚠️ Failed to track interaction: {e}")
            
            return playlist_url
        else:
            print(f"{self.logger_prefix} ❌ Failed to add tracks to playlist")
            return None

    def build_playlist(self):
        """Main method to build the complete playlist"""
        print(f"{self.logger_prefix} 🚀 Starting playlist build process...")
        
        try:
            # Step 1: Authenticate
            if not self.authenticate_spotify():
                print(f"{self.logger_prefix} ❌ Authentication failed")
                return None
            
            # Step 2: Analyze preferences
            era_weights = self.analyze_era_preferences()
            
            # Step 3: Discover artists
            self.discover_artists_lastfm(era_weights)
            
            # Step 4: Select tracks with logic
            self.select_tracks_with_logic(era_weights)
            
            # Step 5: Find tracks on Spotify
            self.find_spotify_tracks()
            
            # Step 6: Create playlist
            playlist_url = self.create_spotify_playlist()
            
            if playlist_url:
                print(f"{self.logger_prefix} 🎉 Playlist build complete!")
                return playlist_url
            else:
                print(f"{self.logger_prefix} ❌ Playlist build failed")
                return None
                
        except Exception as e:
            print(f"{self.logger_prefix} ❌ Critical error in playlist build: {e}")
            traceback.print_exc()
            return None


# Main function to replace build_smart_playlist_enhanced
def build_smart_playlist_enhanced(event_name, genre, time, mood_tags, search_keywords,
                                  favorite_artist, user_id=None, playlist_type="clean",
                                  request_id=None, birth_year=None):
    """
    Enhanced playlist builder using the new MoodQue Engine
    """
    # CRITICAL: request_id is now required - do not generate fallback
    if not request_id:
        error_msg = "❌ CRITICAL: request_id is required but not provided to build_smart_playlist_enhanced"
        print(error_msg)
        raise ValueError("request_id parameter is required")
    
    # FIXED: Ensure user_id is properly handled
    if not user_id or user_id == 'unknown':
        user_id = 'anonymous'
    
    # FIXED: Validate and clean parameters
    if not event_name:
        event_name = "My MoodQue Playlist"
    
    if not genre:
        genre = "pop"
    
    # FIXED: Handle time parameter safely
    try:
        time = int(time) if time else 30
    except (ValueError, TypeError):
        time = 30
    
    # Prepare request data with validated parameters
    request_data = {
        'event_name': event_name,
        'genre': genre,
        'time': time,
        'mood_tags': mood_tags,
        'search_keywords': search_keywords,
        'favorite_artist': favorite_artist,
        'user_id': user_id,
        'playlist_type': playlist_type,
        'request_id': request_id,  # CRITICAL: Pass the exact request_id from Glide
        'birth_year': birth_year
    }
    
    # ADDED: Log the request data for debugging
    print(f"[{request_id}] 🔧 Building playlist with parameters:")
    for key, value in request_data.items():
        print(f"[{request_id}]   {key}: {value}")
    
    # Initialize and run engine
    try:
        engine = MoodQueEngine(request_data)
        result = engine.build_playlist()
        
        if result:
            print(f"[{request_id}] ✅ Playlist build completed successfully")
        else:
            print(f"[{request_id}] ❌ Playlist build failed")
            
        return result
        
    except Exception as e:
        print(f"[{request_id}] ❌ Critical error in playlist builder: {e}")
        import traceback
        traceback.print_exc()
        
        return None