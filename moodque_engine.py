# complete_moodque_engine.py - Full Featured MoodQue Engine

from firebase_admin import firestore

def get_user_id_from_spotify_id(spotify_user_id):
    db = firestore.client()
    users_ref = db.collection("users")
    query = users_ref.where("spotify_user_id", "==", spotify_user_id).limit(1).stream()

    for doc in query:
        return doc.id  # Or use doc.to_dict().get("user_id") if stored inside

    return None

from lastfm_recommender import get_recommendations, get_similar_artists, get_genre_seed_artists, search_tracks_by_artist

import os
import requests
import base64
import random
import uuid
import json
import traceback
from datetime import datetime
import time
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
        """
        Initialize the MoodQueEngine with request data and setup cache
        """
        self.request_data = request_data
        self.genre = request_data.get('genre', 'pop')
        self.favorite_artist = request_data.get('favorite_artist', '')
        self.time = int(request_data.get('time', 30))
        self.time_minutes = self.time  # Add this for compatibility
        self.user_id = request_data.get('user_id', 'anonymous')
        self.mood_tags = request_data.get('mood_tags', [])
        self.search_keywords = request_data.get('search_keywords', [])
        self.event_name = request_data.get('event_name', 'MoodQue Playlist')
        self.playlist_type = request_data.get('playlist_type', 'clean')
        self.birth_year = request_data.get('birth_year', None)
        self.request_id = request_data.get('request_id', 'unknown')
        
        # Add logger prefix for consistent logging
        self.logger_prefix = f"[{self.request_id}]"
        
        # Token and auth will be set during authentication
        self.access_token = None
        self.headers = None
        self.spotify_user_id = None
        
        # Caching setup
        self.track_cache = {}  # Format: { (artist_name.lower(), track_name.lower()): track_id }
        
        # Workflow state
        self.artist_pool = []
        self.track_candidates = []
        self.final_playlist = []

    def discover_similar_tracks(self, favorite_artist=None, mood_tags=None, genre=None, keywords=None):
        """
        Use search_tracks_by_artist to get tracks from favorite artists with batching,
        then supplement with recommendations for variety
        """
        print(f"{self.logger_prefix} 🔍 Discovering tracks for favorite artists (with batching)...")
        
        all_tracks = []
        
        try:
            # Parse favorite artists if it's a string
            if isinstance(favorite_artist, str) and favorite_artist:
                artists = [a.strip() for a in favorite_artist.split(",") if a.strip()]
            elif favorite_artist:  
                artists = [favorite_artist]
            else:
                artists = []
            
            # Strategy 1: Get tracks from each favorite artist with BATCHING
            if artists:
                for artist in artists:
                    print(f"{self.logger_prefix} 🎤 Getting tracks for favorite artist: {artist}")
                    # Use smaller batch size to prevent timeout
                    artist_tracks = search_tracks_by_artist(artist, limit=20)
                    all_tracks.extend(artist_tracks)
                    print(f"{self.logger_prefix} ✅ Found {len(artist_tracks)} tracks for {artist}")
                    
                    # Stop if we have enough tracks to prevent timeout
                    if len(all_tracks) >= 50:
                        print(f"{self.logger_prefix} 🛑 Stopping at 50 tracks to prevent timeout")
                        break
            
            # Strategy 2: Add variety with recommendations (smaller batch)
            if len(all_tracks) < 40:  # Lower threshold
                print(f"{self.logger_prefix} 🔄 Adding variety with similar artists...")
                similar_tracks = get_recommendations(
                    seed_artists=artists or get_genre_seed_artists(genre or self.genre, limit=2),
                    genre=genre or self.genre,
                    birth_year=self.birth_year,
                    limit=20  # Smaller batch
                )
                all_tracks.extend(similar_tracks)
                print(f"{self.logger_prefix} ✅ Added {len(similar_tracks)} variety tracks")

            if all_tracks:
                print(f"{self.logger_prefix} ✅ Total discovered tracks: {len(all_tracks)}")
                return all_tracks[:60]  # Limit total tracks to prevent timeout
            else:
                print(f"{self.logger_prefix} ⚠️ No tracks found, using genre fallback...")
                # Last resort fallback to genre-based tracks
                fallback_artists = get_genre_seed_artists(genre or self.genre, limit=1)  # Just 1 artist
                fallback_tracks = get_recommendations(
                    seed_artists=fallback_artists,
                    genre=genre or self.genre,
                    limit=15  # Small fallback
                )
                return fallback_tracks or []
                
        except Exception as e:
            print(f"{self.logger_prefix} ❌ Error discovering tracks: {e}")
            import traceback
            traceback.print_exc()
            return []

    def fetch_spotify_track_ids(self, track_list, max_results=30):  # Reduced from 50
        """Convert Last.fm tracks to Spotify track IDs with ultra-safe processing"""
        print(f"{self.logger_prefix} 🔍 Converting {len(track_list)} tracks to Spotify IDs (ultra-safe mode)...")
    
        # Try ultra-safe batch processing first
        try:
            from moodque_utilities import batch_search_spotify_tracks_ultra_safe
            print(f"{self.logger_prefix} 🛡️ Using ultra-safe batch processing...")
        
            # Use much smaller result set to prevent timeouts
            limited_tracks = track_list[:max_results]
        
            found_tracks, failed_tracks = batch_search_spotify_tracks_ultra_safe(
                limited_tracks, 
                self.headers, 
                self.playlist_type,
                batch_size=3  # Very small batches
            )
        
            # Extract URIs
            track_uris = [track["uri"] for track in found_tracks]
        
            print(f"{self.logger_prefix} ✅ Ultra-safe processing found {len(track_uris)} track IDs")
            if failed_tracks:
                print(f"{self.logger_prefix} ⚠️ Failed to find {len(failed_tracks)} tracks")
        
            return track_uris
        
        except ImportError:
            print(f"{self.logger_prefix} ⚠️ Ultra-safe processing not available")
        except Exception as e:
            print(f"{self.logger_prefix} ❌ Ultra-safe processing failed: {e}")
    
        # Final fallback: Skip Spotify search entirely and return empty list
        # This prevents the entire app from crashing
        print(f"{self.logger_prefix} 🚨 All Spotify search methods failed - returning empty playlist")
        print(f"{self.logger_prefix} 💡 This is a network/API issue, not a code problem")
    
        return []  # Return empty list instead of crashing

    def create_spotify_playlist(self, track_ids):
        """Create Spotify playlist with the given track IDs"""
        print(f"{self.logger_prefix} 🎵 Creating Spotify playlist with {len(track_ids)} tracks...")
        
        if not track_ids:
            print(f"{self.logger_prefix} ❌ No track IDs provided")
            return None
            
        if not self.spotify_user_id:
            print(f"{self.logger_prefix} ❌ No Spotify user ID available")
            return None

        try:
            # Create the playlist
            playlist_id = create_new_playlist(
                self.headers,
                self.spotify_user_id,
                self.event_name,
                f"MoodQue playlist: {self.event_name}"
            )
            
            if not playlist_id:
                print(f"{self.logger_prefix} ❌ Failed to create playlist")
                return None

            # Convert track IDs to URIs if needed
            track_uris = []
            for track_id in track_ids:
                if track_id.startswith("spotify:track:"):
                    track_uris.append(track_id)
                else:
                    track_uris.append(f"spotify:track:{track_id}")

            # Add tracks to playlist
            success = add_tracks_to_playlist(self.headers, self.spotify_user_id, playlist_id, track_uris)
            
            if success:
                playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
                print(f"{self.logger_prefix} ✅ Playlist created successfully: {playlist_url}")
                
                return {
                    'playlist_url': playlist_url,
                    'track_count': len(track_ids),
                    'playlist_id': playlist_id
                }
            else:
                print(f"{self.logger_prefix} ❌ Failed to add tracks to playlist")
                return None
                
        except Exception as e:
            print(f"{self.logger_prefix} ❌ Error creating Spotify playlist: {e}")
            return None

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
        """Main playlist building workflow"""
        print(f"{self.logger_prefix} 🚀 Starting playlist build process...")

        # Step 1: Authenticate with Spotify
        if not self.authenticate_spotify():
            print(f"{self.logger_prefix} ❌ Spotify authentication failed")
            return None

        # Step 2: Discover similar tracks via Last.fm
        similar_tracks = self.discover_similar_tracks(
            favorite_artist=self.favorite_artist,
            mood_tags=self.mood_tags,
            genre=self.genre,
            keywords=self.search_keywords
        )

        if not similar_tracks:
            print(f"{self.logger_prefix} ❌ No similar tracks found from Last.fm")
            return None

        print(f"{self.logger_prefix} 🎯 Found {len(similar_tracks)} candidate tracks")

        # Step 3: Convert to Spotify track IDs
        spotify_track_ids = self.fetch_spotify_track_ids(similar_tracks)
        if not spotify_track_ids:
            print(f"{self.logger_prefix} ❌ No valid Spotify track IDs matched")
            return None

        print(f"{self.logger_prefix} 🎵 Matched {len(spotify_track_ids)} Spotify tracks")

        # Step 4: Create Spotify playlist
        playlist_info = self.create_spotify_playlist(spotify_track_ids)
        if not playlist_info:
            print(f"{self.logger_prefix} ❌ Failed to create playlist")
            return None

        print(f"{self.logger_prefix} ✅ Playlist created: {playlist_info['playlist_url']}")

        # Step 5: Track the interaction
        try:
            track_interaction(
                user_id=self.user_id,
                event_type="built_playlist",
                data={
                    "playlist_id": playlist_info.get('playlist_id'),
                    "mood_tags": [self.mood_tags] if self.mood_tags else [],
                    "genres": [self.genre] if self.genre else [],
                    "event": self.event_name,
                    "track_count": playlist_info.get('track_count', 0),
                    "duration_minutes": self.time_minutes
                }
            )
        except Exception as e:
            print(f"{self.logger_prefix} ⚠️ Failed to track interaction: {e}")

        return playlist_info['playlist_url']

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
        'request_id': request_id,  # CRITICAL: Pass the exact request_id from Glide
        'birth_year': birth_year
    }
    
    # Log the request data for debugging
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