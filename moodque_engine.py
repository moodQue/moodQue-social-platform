# complete_moodque_engine.py v2.0 - Multi-Service Architecture with Caching

from firebase_admin import firestore

def get_user_id_from_spotify_id(spotify_user_id):
    db = firestore.client()
    users_ref = db.collection("users")
    query = users_ref.where("spotify_user_id", "==", spotify_user_id).limit(1).stream()
    for doc in query:
        return doc.id
    return None

from lastfm_recommender import get_recommendations, get_similar_artists, get_genre_seed_artists, search_tracks_by_artist

import os
import requests
import base64
import random
import uuid
import json
import traceback
import time
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
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
    search_spotify_track_ultra_robust
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

# Map your app genres to streaming service genres
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

class TrackCache:
    """Persistent track ID cache for all streaming services"""
    
    def __init__(self):
        self.cache_collection = "track_cache"
    
    def _get_cache_key(self, artist, track, service="spotify"):
        """Generate consistent cache key"""
        # Normalize artist and track names
        artist_clean = artist.lower().strip().replace(" ", "").replace("&", "and")
        track_clean = track.lower().strip().replace(" ", "").replace("&", "and")
        
        # Create hash for consistency
        key_string = f"{service}_{artist_clean}_{track_clean}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_track_id(self, artist, track, service="spotify"):
        """Get cached track ID if it exists"""
        try:
            cache_key = self._get_cache_key(artist, track, service)
            doc_ref = db.collection(self.cache_collection).document(cache_key)
            doc = doc_ref.get()
            
            if doc.exists:
                cache_data = doc.to_dict()
                # Check if cache is not too old (30 days)
                cached_date = cache_data.get("cached_at")
                if cached_date:
                    cached_datetime = datetime.fromisoformat(cached_date)
                    if datetime.now() - cached_datetime < timedelta(days=30):
                        print(f"💾 Cache HIT: {artist} - {track} ({service})")
                        return cache_data.get("track_id")
            
            return None
            
        except Exception as e:
            print(f"❌ Cache read error: {e}")
            return None
    
    def store_track_id(self, artist, track, track_id, service="spotify"):
        """Store track ID in cache"""
        try:
            cache_key = self._get_cache_key(artist, track, service)
            cache_data = {
                "artist": artist,
                "track": track,
                "track_id": track_id,
                "service": service,
                "cached_at": datetime.now().isoformat(),
                "cache_key": cache_key
            }
            
            db.collection(self.cache_collection).document(cache_key).set(cache_data)
            print(f"💾 Cache STORE: {artist} - {track} ({service})")
            
        except Exception as e:
            print(f"❌ Cache store error: {e}")

class SmartTrackCurator:
    """Curates tracks based on mood, valence, and playlist requirements before streaming service search"""
    
    # Mood to musical characteristics mapping
    MOOD_CHARACTERISTICS = {
        "happy": {"energy": "high", "valence": "positive", "tempo": "upbeat"},
        "energetic": {"energy": "very_high", "valence": "positive", "tempo": "fast"},
        "hype": {"energy": "very_high", "valence": "very_positive", "tempo": "very_fast"},
        "party": {"energy": "very_high", "valence": "very_positive", "tempo": "danceable"},
        "workout": {"energy": "high", "valence": "positive", "tempo": "driving"},
        "chill": {"energy": "low", "valence": "neutral", "tempo": "slow"},
        "relaxed": {"energy": "very_low", "valence": "positive", "tempo": "slow"},
        "calm": {"energy": "very_low", "valence": "neutral", "tempo": "very_slow"},
        "focus": {"energy": "low", "valence": "neutral", "tempo": "steady"},
        "romantic": {"energy": "low", "valence": "positive", "tempo": "slow"},
        "melancholy": {"energy": "low", "valence": "negative", "tempo": "slow"},
        "sad": {"energy": "very_low", "valence": "negative", "tempo": "slow"},
        "upbeat": {"energy": "high", "valence": "positive", "tempo": "fast"},
        "groovy": {"energy": "medium", "valence": "positive", "tempo": "rhythmic"}
    }
    
    # Genre characteristics
    GENRE_CHARACTERISTICS = {
        "grunge": {"energy": "high", "rawness": "high", "era_weight": 1.5},
        "alternative": {"energy": "medium", "complexity": "high", "era_weight": 1.3},
        "rock": {"energy": "high", "intensity": "high", "era_weight": 1.2},
        "pop": {"energy": "medium", "accessibility": "high", "era_weight": 1.0},
        "hip-hop": {"energy": "high", "rhythm": "strong", "era_weight": 1.1},
        "jazz": {"energy": "medium", "sophistication": "high", "era_weight": 1.4},
        "electronic": {"energy": "high", "synthetic": "high", "era_weight": 0.9}
    }
    
    def __init__(self, mood_tags, genre, time_minutes, playlist_type="clean"):
        self.mood_tags = mood_tags.lower() if isinstance(mood_tags, str) else ""
        self.genre = genre.lower() if genre else "alternative"
        self.time_minutes = time_minutes
        self.playlist_type = playlist_type
        self.target_track_count = max(8, min(25, time_minutes // 2))  # 8-25 tracks based on time
        
    def score_track(self, track_info):
        """Score a track based on mood, genre, and characteristics"""
        score = 1.0
        
        # Base scoring
        artist = track_info.get("artist", "").lower()
        track_name = track_info.get("track", "").lower()
        source = track_info.get("source", "")
        
        # Artist bonus (seed artists get priority)
        if source == "artist_search":
            score *= 1.5
        
        # Mood matching
        mood_characteristics = self.MOOD_CHARACTERISTICS.get(self.mood_tags, {})
        
        # Energy level inference from track name
        energy_keywords = {
            "high": ["rock", "pump", "power", "energy", "wild", "crazy", "loud", "heavy"],
            "low": ["soft", "quiet", "gentle", "calm", "peaceful", "slow", "rest"],
            "medium": ["groove", "smooth", "easy", "flow", "steady"]
        }
        
        expected_energy = mood_characteristics.get("energy", "medium")
        for energy_level, keywords in energy_keywords.items():
            if any(keyword in track_name for keyword in keywords):
                if energy_level == expected_energy:
                    score *= 1.3
                break
        
        # Genre matching
        genre_characteristics = self.GENRE_CHARACTERISTICS.get(self.genre, {})
        genre_weight = genre_characteristics.get("era_weight", 1.0)
        score *= genre_weight
        
        # Special grunge characteristics
        if self.genre == "grunge":
            grunge_indicators = ["unplugged", "live", "acoustic", "raw", "demo"]
            if any(indicator in track_name for indicator in grunge_indicators):
                score *= 1.2
        
        # Valence (positivity) matching
        expected_valence = mood_characteristics.get("valence", "neutral")
        positive_words = ["love", "happy", "good", "great", "beautiful", "shine", "light"]
        negative_words = ["pain", "hurt", "sad", "dark", "broken", "lost", "alone", "die"]
        
        if expected_valence in ["positive", "very_positive"]:
            if any(word in track_name for word in positive_words):
                score *= 1.2
        elif expected_valence in ["negative"]:
            if any(word in track_name for word in negative_words):
                score *= 1.2
        
        # Avoid explicit content for clean playlists
        explicit_indicators = ["explicit", "parental", "dirty", "fuck", "shit", "bitch"]
        if self.playlist_type == "clean":
            if any(indicator in track_name.lower() for indicator in explicit_indicators):
                score *= 0.3
        
        # Randomization to avoid same tracks every time
        score *= random.uniform(0.8, 1.2)
        
        return score
    
    def curate_tracks(self, all_tracks):
        """Curate the best tracks for this playlist"""
        print(f"🎯 Curating tracks for {self.mood_tags} {self.genre} playlist ({self.time_minutes} min)")
        
        # Score all tracks
        scored_tracks = []
        for track in all_tracks:
            if isinstance(track, dict):
                score = self.score_track(track)
                track["curation_score"] = score
                scored_tracks.append(track)
        
        # Sort by score
        scored_tracks.sort(key=lambda x: x["curation_score"], reverse=True)
        
        # Artist diversity - don't have too many tracks from same artist
        curated_tracks = []
        artist_count = defaultdict(int)
        max_per_artist = max(2, self.target_track_count // 8)  # Max 2-3 tracks per artist
        
        for track in scored_tracks:
            artist = track.get("artist", "").lower()
            
            if artist_count[artist] < max_per_artist:
                curated_tracks.append(track)
                artist_count[artist] += 1
                
                if len(curated_tracks) >= self.target_track_count:
                    break
        
        # If we don't have enough, fill with remaining tracks
        if len(curated_tracks) < self.target_track_count:
            remaining = [t for t in scored_tracks if t not in curated_tracks]
            curated_tracks.extend(remaining[:self.target_track_count - len(curated_tracks)])
        
        print(f"🎵 Curated {len(curated_tracks)} tracks from {len(all_tracks)} candidates")
        print(f"📊 Top artists: {list(dict.fromkeys([t.get('artist', 'Unknown')[:20] for t in curated_tracks[:5]]))}")
        print(f"🎯 Average curation score: {sum(t['curation_score'] for t in curated_tracks) / len(curated_tracks):.2f}")
        
        return curated_tracks

class StreamingServiceAdapter:
    """Abstract adapter for streaming services (Spotify, YouTube Music, Apple Music)"""
    
    def __init__(self, service_name, cache):
        self.service_name = service_name
        self.cache = cache
    
    def search_track(self, artist, track, playlist_type="clean"):
        """Override in subclasses"""
        raise NotImplementedError
    
    def create_playlist(self, name, description, track_ids):
        """Override in subclasses"""
        raise NotImplementedError

class SpotifyAdapter(StreamingServiceAdapter):
    """Spotify streaming service adapter"""
    
    def __init__(self, headers, cache):
        super().__init__("spotify", cache)
        self.headers = headers
    
    def search_track(self, artist, track, playlist_type="clean"):
        """Search for track on Spotify with caching"""
        # Check cache first
        cached_id = self.cache.get_track_id(artist, track, "spotify")
        if cached_id:
            return cached_id
        
        # Search Spotify
        try:
            track_uri = search_spotify_track_ultra_robust(artist, track, self.headers, playlist_type, max_retries=1)
            
            if track_uri:
                # Store in cache
                self.cache.store_track_id(artist, track, track_uri, "spotify")
                return track_uri
        except Exception as e:
            print(f"❌ Spotify search error for {artist} - {track}: {e}")
        
        return None
    
    def create_playlist(self, user_id, name, description, track_uris):
        """Create Spotify playlist"""
        try:
            playlist_id = create_new_playlist(self.headers, user_id, name, description)
            if playlist_id and track_uris:
                success = add_tracks_to_playlist(self.headers, user_id, playlist_id, track_uris)
                if success:
                    return f"https://open.spotify.com/playlist/{playlist_id}"
        except Exception as e:
            print(f"❌ Spotify playlist creation error: {e}")
        return None

# Future adapters for other services
class YouTubeMusicAdapter(StreamingServiceAdapter):
    """YouTube Music adapter (future implementation)"""
    
    def search_track(self, artist, track, playlist_type="clean"):
        # TODO: Implement YouTube Music search
        print(f"🎵 YouTube Music search: {artist} - {track} (Coming Soon)")
        return None
    
    def create_playlist(self, name, description, track_ids):
        # TODO: Implement YouTube Music playlist creation
        print(f"🎵 YouTube Music playlist creation (Coming Soon)")
        return None

class AppleMusicAdapter(StreamingServiceAdapter):
    """Apple Music adapter (future implementation)"""
    
    def search_track(self, artist, track, playlist_type="clean"):
        # TODO: Implement Apple Music search
        print(f"🎵 Apple Music search: {artist} - {track} (Coming Soon)")
        return None
    
    def create_playlist(self, name, description, track_ids):
        # TODO: Implement Apple Music playlist creation
        print(f"🎵 Apple Music playlist creation (Coming Soon)")
        return None

class MoodQueEngine:
    """Main class for building MoodQue playlists with multi-service support and caching"""
    
    def __init__(self, request_data):
        """Initialize the MoodQueEngine with request data and setup cache"""
        self.request_data = request_data
        self.genre = request_data.get('genre', 'pop')
        self.favorite_artist = request_data.get('favorite_artist', '')
        self.time = int(request_data.get('time', 30))
        self.time_minutes = self.time
        self.user_id = request_data.get('user_id', 'anonymous')
        self.mood_tags = request_data.get('mood_tags', [])
        self.search_keywords = request_data.get('search_keywords', [])
        self.event_name = request_data.get('event_name', 'MoodQue Playlist')
        self.playlist_type = request_data.get('playlist_type', 'clean')
        self.birth_year = request_data.get('birth_year', None)
        self.request_id = request_data.get('request_id', 'unknown')
        self.preferred_service = request_data.get('streaming_service', 'spotify')  # Future: user choice
        
        # Add logger prefix for consistent logging
        self.logger_prefix = f"[{self.request_id}]"
        
        # Initialize caching system
        self.cache = TrackCache()
        
        # Token and auth will be set during authentication
        self.access_token = None
        self.headers = None
        self.spotify_user_id = None
        
        # Streaming service adapters
        self.streaming_adapters = {}
        
        # Workflow state
        self.discovered_tracks = []
        self.curated_tracks = []
        self.final_playlist = []

    def discover_tracks_from_lastfm(self, favorite_artist=None, mood_tags=None, genre=None, keywords=None):
        """Step 1: Discover tracks from Last.fm"""
        print(f"{self.logger_prefix} 🔍 Step 1: Discovering tracks from Last.fm...")
        
        all_tracks = []
        
        try:
            # Parse favorite artists if it's a string
            if isinstance(favorite_artist, str) and favorite_artist:
                artists = [a.strip() for a in favorite_artist.split(",") if a.strip()]
            elif favorite_artist:  
                artists = [favorite_artist]
            else:
                artists = []
            
            # Get tracks from favorite artists
            if artists:
                for artist in artists:
                    print(f"{self.logger_prefix} 🎤 Getting tracks for favorite artist: {artist}")
                    artist_tracks = search_tracks_by_artist(artist, limit=20)
                    all_tracks.extend(artist_tracks)
                    print(f"{self.logger_prefix} ✅ Found {len(artist_tracks)} tracks for {artist}")
                    
                    if len(all_tracks) >= 80:  # Get more tracks for better curation
                        break
            
            # Add variety with recommendations
            if len(all_tracks) < 60:
                print(f"{self.logger_prefix} 🔄 Adding variety with similar artists...")
                similar_tracks = get_recommendations(
                    seed_artists=artists or get_genre_seed_artists(genre or self.genre, limit=2),
                    genre=genre or self.genre,
                    birth_year=self.birth_year,
                    limit=40
                )
                all_tracks.extend(similar_tracks)
                print(f"{self.logger_prefix} ✅ Added {len(similar_tracks)} variety tracks")
            
            if not all_tracks:
                print(f"{self.logger_prefix} ⚠️ No tracks found, using genre fallback...")
                fallback_artists = get_genre_seed_artists(genre or self.genre, limit=1)
                all_tracks = get_recommendations(
                    seed_artists=fallback_artists,
                    genre=genre or self.genre,
                    limit=20
                )
            
            self.discovered_tracks = all_tracks
            print(f"{self.logger_prefix} 🎯 Step 1 Complete: Discovered {len(all_tracks)} tracks from Last.fm")
            return all_tracks
            
        except Exception as e:
            print(f"{self.logger_prefix} ❌ Error in Last.fm discovery: {e}")
            import traceback
            traceback.print_exc()
            return []

    def curate_optimal_playlist(self):
        """Step 2: Curate optimal tracks using mood/valence analysis"""
        print(f"{self.logger_prefix} 🎯 Step 2: Curating optimal playlist...")
        
        if not self.discovered_tracks:
            print(f"{self.logger_prefix} ❌ No discovered tracks to curate")
            return []
        
        curator = SmartTrackCurator(
            mood_tags=self.mood_tags,
            genre=self.genre,
            time_minutes=self.time_minutes,
            playlist_type=self.playlist_type
        )
        
        self.curated_tracks = curator.curate_tracks(self.discovered_tracks)
        print(f"{self.logger_prefix} ✨ Step 2 Complete: Curated {len(self.curated_tracks)} optimal tracks")
        return self.curated_tracks

    def setup_streaming_services(self):
        """Step 3: Setup streaming service adapters"""
        print(f"{self.logger_prefix} 🔧 Step 3: Setting up streaming services...")
        
        # Setup Spotify adapter
        if self.headers:
            self.streaming_adapters['spotify'] = SpotifyAdapter(self.headers, self.cache)
            print(f"{self.logger_prefix} ✅ Spotify adapter ready")
        
        # Setup future adapters
        # self.streaming_adapters['youtube_music'] = YouTubeMusicAdapter(self.cache)
        # self.streaming_adapters['apple_music'] = AppleMusicAdapter(self.cache)
        
        print(f"{self.logger_prefix} 🔧 Step 3 Complete: {len(self.streaming_adapters)} streaming services ready")

    def search_streaming_services(self):
        """Step 4: Search streaming services for curated tracks"""
        print(f"{self.logger_prefix} 🔍 Step 4: Searching streaming services for {len(self.curated_tracks)} curated tracks...")
        
        found_tracks = []
        adapter = self.streaming_adapters.get(self.preferred_service)
        
        if not adapter:
            print(f"{self.logger_prefix} ❌ No adapter for {self.preferred_service}")
            return []
        
        cache_hits = 0
        api_searches = 0
        
        for track in self.curated_tracks:
            artist = track.get("artist", "")
            track_name = track.get("track", "")
            
            if not artist or not track_name:
                continue
            
            # Check if this will be a cache hit
            cached_id = self.cache.get_track_id(artist, track_name, self.preferred_service)
            if cached_id:
                cache_hits += 1
            else:
                api_searches += 1
            
            track_id = adapter.search_track(artist, track_name, self.playlist_type)
            
            if track_id:
                found_tracks.append(track_id)
                print(f"{self.logger_prefix} ✅ Found: {artist} - {track_name}")
            else:
                print(f"{self.logger_prefix} ❌ Not found: {artist} - {track_name}")
        
        print(f"{self.logger_prefix} 📊 Search Stats: {cache_hits} cache hits, {api_searches} API searches")
        print(f"{self.logger_prefix} 🔍 Step 4 Complete: Found {len(found_tracks)}/{len(self.curated_tracks)} tracks")
        return found_tracks

    def create_streaming_playlist(self, track_ids):
        """Step 5: Create playlist on streaming service"""
        print(f"{self.logger_prefix} 🎵 Step 5: Creating playlist with {len(track_ids)} tracks...")
        
        if not track_ids:
            print(f"{self.logger_prefix} ❌ No track IDs to create playlist")
            return None
        
        adapter = self.streaming_adapters.get(self.preferred_service)
        if not adapter:
            print(f"{self.logger_prefix} ❌ No adapter for {self.preferred_service}")
            return None
        
        playlist_url = adapter.create_playlist(
            self.spotify_user_id,
            self.event_name,
            f"MoodQue playlist: {self.event_name}",
            track_ids
        )
        
        if playlist_url:
            print(f"{self.logger_prefix} 🎵 Step 5 Complete: Playlist created successfully")
        else:
            print(f"{self.logger_prefix} ❌ Step 5 Failed: Playlist creation failed")
        
        return playlist_url

    def authenticate_spotify(self):
        """Handle Spotify authentication with proper fallback"""
        print(f"{self.logger_prefix} 🔐 Authenticating with Spotify...")
        
        # Try user token first if we have a user_id
        if self.user_id and self.user_id != 'unknown' and self.user_id != 'anonymous':
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

    def build_playlist(self):
        """Main playlist building workflow - NEW 5-STEP PROCESS"""
        print(f"{self.logger_prefix} 🚀 Starting MoodQue v2.0 playlist build process...")

        # Step 0: Authenticate with streaming services
        if not self.authenticate_spotify():
            print(f"{self.logger_prefix} ❌ Streaming service authentication failed")
            return None

        # Step 1: Discover tracks from Last.fm
        discovered_tracks = self.discover_tracks_from_lastfm(
            favorite_artist=self.favorite_artist,
            mood_tags=self.mood_tags,
            genre=self.genre,
            keywords=self.search_keywords
        )

        if not discovered_tracks:
            print(f"{self.logger_prefix} ❌ No tracks discovered from Last.fm")
            return None

        # Step 2: Curate optimal playlist
        curated_tracks = self.curate_optimal_playlist()

        if not curated_tracks:
            print(f"{self.logger_prefix} ❌ No tracks curated")
            return None

        # Step 3: Setup streaming services
        self.setup_streaming_services()

        # Step 4: Search streaming services for curated tracks
        track_ids = self.search_streaming_services()

        if not track_ids:
            print(f"{self.logger_prefix} ❌ No tracks found on streaming services")
            return None

        # Step 5: Create playlist
        playlist_url = self.create_streaming_playlist(track_ids)

        if not playlist_url:
            print(f"{self.logger_prefix} ❌ Playlist creation failed")
            return None

        # Step 6: Track the interaction
        try:
            track_interaction(
                user_id=self.user_id,
                event_type="built_playlist",
                data={
                    "playlist_url": playlist_url,
                    "mood_tags": [self.mood_tags] if self.mood_tags else [],
                    "genres": [self.genre] if self.genre else [],
                    "event": self.event_name,
                    "track_count": len(track_ids),
                    "duration_minutes": self.time_minutes,
                    "streaming_service": self.preferred_service,
                    "curation_strategy": "smart_mood_valence_v2",
                    "discovered_tracks": len(discovered_tracks),
                    "curated_tracks": len(curated_tracks),
                    "found_tracks": len(track_ids)
                }
            )
        except Exception as e:
            print(f"{self.logger_prefix} ⚠️ Failed to track interaction: {e}")

        print(f"{self.logger_prefix} ✅ MoodQue v2.0 playlist build completed successfully!")
        return playlist_url

# Main function to replace build_smart_playlist_enhanced
def build_smart_playlist_enhanced(event_name, genre, time, mood_tags, search_keywords,
                                  favorite_artist, user_id=None, playlist_type="clean",
                                  request_id=None, birth_year=None, streaming_service="spotify"):
    """
    Enhanced playlist builder using the new MoodQue Engine v2.0
    """
    # CRITICAL: request_id is now required - do not generate fallback
    if not request_id:
        error_msg = "❌ CRITICAL: request_id is required but not provided to build_smart_playlist_enhanced"
        print(error_msg)
        raise ValueError("request_id parameter is required")
    
    # Handle user_id properly
    if not user_id or user_id == 'unknown':
        user_id = 'anonymous'
    
    # Validate and clean parameters
    if not event_name:
        event_name = "My MoodQue Playlist"
    
    if not genre:
        genre = "pop"
    
    # Handle time parameter safely
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
        'request_id': request_id,
        'birth_year': birth_year,
        'streaming_service': streaming_service  # NEW: Support for multiple services
    }
    
    # Log the request data for debugging
    print(f"[{request_id}] 🔧 Building MoodQue v2.0 playlist with parameters:")
    for key, value in request_data.items():
        print(f"[{request_id}]   {key}: {value}")
    
    # Initialize and run engine
    try:
        engine = MoodQueEngine(request_data)
        result = engine.build_playlist()
        
        if result:
            print(f"[{request_id}] ✅ MoodQue v2.0 playlist build completed successfully")
        else:
            print(f"[{request_id}] ❌ MoodQue v2.0 playlist build failed")
            
        return result
        
    except Exception as e:
        print(f"[{request_id}] ❌ Critical error in MoodQue v2.0 playlist builder: {e}")
        import traceback
        traceback.print_exc()
        
        return None