# Enhanced lastfm_recommender.py with real Last.fm API integration

from datetime import datetime
from typing import List, Optional, Dict, Set
from collections import Counter
import requests
import os
import random

# Get Last.fm API key
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

# Expanded artist-to-era mapping
ARTIST_ERA_MAP = {
    "Michael Jackson": ["1970s", "1980s", "1990s", "2000s"],
    "Prince": ["1980s", "1990s", "2000s"],
    "Hall and Oates": ["1970s", "1980s"],
    "Taylor Swift": ["2000s", "2010s", "2020s"],
    "Sabrina Carpenter": ["2010s", "2020s"],
    "Chappell Roan": ["2020s"],
    "Adele": ["2000s", "2010s", "2020s"],
    "Doja Cat": ["2010s", "2020s"],
    "Britney Spears": ["1990s", "2000s", "2010s"],
    "Backstreet Boys": ["1990s", "2000s"],
    "Usher": ["1990s", "2000s", "2010s"],
    "Maxwell": ["1990s", "2000s", "2010s"],
    "John Legend": ["2000s", "2010s", "2020s"],
    "Drake": ["2000s", "2010s", "2020s"],
    "Snoop Dogg": ["1990s", "2000s", "2010s"],
    "Pharrell": ["1990s", "2000s", "2010s", "2020s"],
    "Marshmello": ["2010s", "2020s"],
    "Dr. Dre": ["1990s", "2000s", "2010s"],
    "Ice Cube": ["1990s", "2000s"],
    "Eminem": ["1990s", "2000s", "2010s", "2020s"],
    "Frank Sinatra": ["1940s", "1950s", "1960s", "1970s"],
    "Sade": ["1980s", "1990s", "2000s"],
    "Whitney Houston": ["1980s", "1990s", "2000s"],
    "Marvin Gaye": ["1960s", "1970s", "1980s"],
    "Stevie Wonder": ["1960s", "1970s", "1980s", "1990s"],
    "Elvis Presley": ["1950s", "1960s", "1970s"],
    "The Beatles": ["1960s", "1970s"],
    "Queen": ["1970s", "1980s", "1990s"],
    "David Bowie": ["1970s", "1980s", "1990s"],
    "Madonna": ["1980s", "1990s", "2000s"],
    "Janet Jackson": ["1980s", "1990s", "2000s"],
    "Arctic Monkeys": ["2000s", "2010s", "2020s"],
    "Tame Impala": ["2010s", "2020s"],
    "The 1975": ["2010s", "2020s"],
    "Imagine Dragons": ["2010s", "2020s"],
    "OneRepublic": ["2000s", "2010s", "2020s"],
    "Maroon 5": ["2000s", "2010s", "2020s"],
    "Dua Lipa": ["2010s", "2020s"],
    "Olivia Rodrigo": ["2020s"],
    "Harry Styles": ["2010s", "2020s"],
    "Kendrick Lamar": ["2010s", "2020s"],
    "Travis Scott": ["2010s", "2020s"]
}

# Genre-to-artist seed mapping for when no favorite artist is provided
GENRE_ARTIST_SEEDS = {
    "pop": ["Taylor Swift", "Dua Lipa", "Harry Styles", "Olivia Rodrigo"],
    "hip-hop": ["Drake", "Kendrick Lamar", "Travis Scott", "Eminem"],
    "indie": ["Arctic Monkeys", "Tame Impala", "The 1975"],
    "rock": ["Imagine Dragons", "OneRepublic", "Maroon 5", "Queen"],
    "r-n-b": ["Usher", "John Legend", "Maxwell", "Sade"],
    "electronic": ["Marshmello", "Calvin Harris", "The Chainsmokers"],
    "country": ["Taylor Swift", "Keith Urban", "Miranda Lambert"],
    "jazz": ["Frank Sinatra", "Norah Jones", "Diana Krall"],
    "classical": ["Ludovico Einaudi", "Max Richter", "Ólafur Arnalds"],
    "funk": ["Prince", "Pharrell", "Bruno Mars"],
    "soul": ["Stevie Wonder", "Adele", "John Legend"],
    "reggae": ["Bob Marley", "Jimmy Buffett", "UB40"],
    "latin": ["Bad Bunny", "J Balvin", "Shakira"],
    "blues": ["B.B. King", "Eric Clapton", "Stevie Ray Vaughan"],
    "alternative": ["Arctic Monkeys", "The 1975", "Tame Impala"],
    "metal": ["Metallica", "Iron Maiden", "Black Sabbath"],
    "grunge": ["Nirvana", "Pearl Jam", "Soundgarden"]
}

def find_era_overlap(seed_artists: List[str]) -> Dict[str, float]:
    """
    Find overlapping eras between multiple artists with intelligent fallback.
    Returns weighted eras based on overlap strength.
    """
    if not seed_artists:
        return {}
    
    print(f"🎵 Analyzing era overlap for artists: {seed_artists}")
    
    if len(seed_artists) == 1:
        # Single artist - use their primary eras with decreasing weights
        artist = seed_artists[0]
        eras = ARTIST_ERA_MAP.get(artist, [])
        if not eras:
            print(f"⚠️ Unknown artist: {artist}. Using current era.")
            current_decade = f"{datetime.now().year//10*10}s"
            return {current_decade: 1.0}
        
        # Weight recent eras higher for single artists
        era_weights = {}
        for i, era in enumerate(reversed(eras)):  # Start from most recent
            era_weights[era] = 1.0 - (i * 0.2)  # Decreasing weight
        print(f"✅ Single artist era weights: {era_weights}")
        return era_weights
    
    # Multiple artists - find overlaps
    artist_eras = []
    for artist in seed_artists:
        eras = ARTIST_ERA_MAP.get(artist, [])
        if eras:
            artist_eras.append(set(eras))
            print(f"  📅 {artist}: {eras}")
        else:
            print(f"  ⚠️ Unknown artist: {artist}")
    
    if not artist_eras:
        current_decade = f"{datetime.now().year//10*10}s"
        return {current_decade: 1.0}
    
    # Find intersection of all artists
    overlap = set.intersection(*artist_eras)
    
    if overlap:
        # Strong overlap found - weight these eras highly
        print(f"✅ Perfect era overlap found: {overlap}")
        return {era: 1.0 for era in overlap}
    
    # No perfect overlap - find the most common eras
    era_count = Counter()
    for era_set in artist_eras:
        for era in era_set:
            era_count[era] += 1
    
    if era_count:
        max_count = max(era_count.values())
        # Weight eras by how many artists share them
        era_weights = {}
        for era, count in era_count.items():
            if count >= 2:  # At least 2 artists share this era
                era_weights[era] = count / max_count
            elif len(seed_artists) <= 2:  # For 2 artists, include individual eras with lower weight
                era_weights[era] = 0.3
        
        if era_weights:
            print(f"✅ Partial era overlap: {era_weights}")
            return era_weights
    
    # Last resort - treat each artist individually
    print(f"⚠️ No era overlap found. Using individual artist eras.")
    era_weights = {}
    for artist in seed_artists:
        eras = ARTIST_ERA_MAP.get(artist, [])
        for era in eras:
            era_weights[era] = era_weights.get(era, 0) + (1.0 / len(seed_artists))
    
    return era_weights

def get_lastfm_similar_artists(artist_name: str, limit: int = 5) -> List[str]:
    """Get similar artists from Last.fm API"""
    if not LASTFM_API_KEY:
        print("⚠️ No LASTFM_API_KEY found")
        return []
    
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name.strip(),
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "error" in data:
                print(f"❌ Last.fm API Error: {data.get('message', 'Unknown error')}")
                return []
            
            similar_artists = data.get("similarartists", {})
            if isinstance(similar_artists, dict):
                artists_list = similar_artists.get("artist", [])
                if isinstance(artists_list, list):
                    return [a.get("name") for a in artists_list if isinstance(a, dict) and "name" in a]
                elif isinstance(artists_list, dict):
                    name = artists_list.get("name")
                    return [name] if name else []
        return []
    except Exception as e:
        print(f"❌ Error fetching similar artists: {e}")
        return []

def get_lastfm_top_tracks(artist_name: str, limit: int = 5) -> List[tuple]:
    """Get top tracks for an artist from Last.fm API"""
    if not LASTFM_API_KEY:
        return []
    
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.gettoptracks",
        "artist": artist_name.strip(),
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "error" in data:
                return []
            
            top_tracks = data.get("toptracks", {})
            if isinstance(top_tracks, dict):
                tracks_list = top_tracks.get("track", [])
                if isinstance(tracks_list, list):
                    return [(t["name"], artist_name) for t in tracks_list if isinstance(t, dict) and "name" in t]
                elif isinstance(tracks_list, dict):
                    track_name = tracks_list.get("name")
                    return [(track_name, artist_name)] if track_name else []
        return []
    except Exception as e:
        print(f"❌ Error fetching top tracks for {artist_name}: {e}")
        return []

def get_genre_seed_artists(genre: str, limit: int = 3) -> List[str]:
    """Get seed artists for a genre when no favorite artist is provided"""
    genre_clean = genre.lower().strip()
    
    # Direct match
    if genre_clean in GENRE_ARTIST_SEEDS:
        artists = GENRE_ARTIST_SEEDS[genre_clean][:limit]
        print(f"🎵 Found genre seed artists for '{genre}': {artists}")
        return artists
    
    # Fuzzy matching
    for genre_key, artists in GENRE_ARTIST_SEEDS.items():
        if genre_clean in genre_key or genre_key in genre_clean:
            selected = artists[:limit]
            print(f"🎵 Fuzzy matched '{genre}' to '{genre_key}': {selected}")
            return selected
    
    # Default fallback to pop
    fallback = GENRE_ARTIST_SEEDS["pop"][:limit]
    print(f"⚠️ No genre match for '{genre}', using pop artists: {fallback}")
    return fallback

def get_similar_artists(artist_name: str, limit: int = 10) -> List[str]:
    """Wrapper function for get_lastfm_similar_artists to match expected interface"""
    return get_lastfm_similar_artists(artist_name, limit)

def get_recommendations(seed_artists: Optional[List[str]] = None, 
                       genre: str = "pop", 
                       birth_year: Optional[int] = None,
                       era_weights: Optional[Dict[str, float]] = None,
                       limit: int = 20,
                       return_artists_only: bool = False) -> List[Dict]:
    """
    Enhanced recommendation system with Last.fm integration and era overlap logic
    """
    # Handle string input for seed_artists
    if isinstance(seed_artists, str):
        seed_artists = [a.strip() for a in seed_artists.split(",") if a.strip()]
    
    # If no seed artists provided, get them from genre
    if not seed_artists:
        seed_artists = get_genre_seed_artists(genre, limit=2)
        print(f"🎵 No seed artists provided, using genre-based seeds: {seed_artists}")
    
    print(f"🎵 Getting recommendations for artists: {seed_artists}")
    print(f"🎼 Genre: {genre}")
    print(f"🎂 Birth year: {birth_year}")
    
    # Use provided era weights or calculate them
    if not era_weights:
        era_weights = find_era_overlap(seed_artists)
        
        # If no artist-based eras and we have birth year, use age-based inference
        if not era_weights and birth_year:
            era_weights = infer_era_from_age(birth_year)
            print(f"🎂 Using age-based era weights: {era_weights}")
    
    # Default fallback for current trends
    if not era_weights:
        current_year = datetime.now().year
        if current_year >= 2020:
            era_weights = {"2020s": 1.0, "2010s": 0.7}
        else:
            era_weights = {"2010s": 1.0, "2000s": 0.8}
        print(f"🔄 Using default era weights: {era_weights}")
    
    # Get expanded artist list using Last.fm
    expanded_artists = set(seed_artists)
    for artist in seed_artists:
        similar = get_lastfm_similar_artists(artist, limit=3)
        expanded_artists.update(similar)
        print(f"🔗 Similar to {artist}: {similar}")
    
    # If return_artists_only is True, return artist list with scores
    if return_artists_only:
        artist_recommendations = []
        for artist in expanded_artists:
            artist_eras = ARTIST_ERA_MAP.get(artist, [f"{datetime.now().year//10*10}s"])
            max_score = 0
            best_era = None
            
            for era in artist_eras:
                era_weight = era_weights.get(era, 0.1)
                if era_weight > max_score:
                    max_score = era_weight
                    best_era = era
            
            artist_recommendations.append({
                "artist": artist,
                "era": best_era,
                "score": max_score,
                "is_seed": artist in seed_artists
            })
        
        # Sort by score, prioritizing seed artists
        artist_recommendations.sort(key=lambda x: (x["is_seed"], x["score"]), reverse=True)
        return artist_recommendations[:limit]
    
    # Get track recommendations
    recommendations = []
    tracks_per_artist = max(1, limit // max(len(expanded_artists), 1))
    
    # Get tracks from seed artists (higher priority)
    for artist in seed_artists:
        tracks = get_lastfm_top_tracks(artist, limit=tracks_per_artist + 1)
        for track_name, artist_name in tracks:
            artist_eras = ARTIST_ERA_MAP.get(artist_name, [f"{datetime.now().year//10*10}s"])
            for era in artist_eras:
                era_weight = era_weights.get(era, 0.1)
                genre_match = 1.0 if genre.lower() in track_name.lower() else 0.8
                artist_bonus = 1.5  # Higher bonus for seed artists
                
                score = genre_match * era_weight * artist_bonus
                
                recommendations.append({
                    "artist": artist_name,
                    "track": track_name,
                    "era": era,
                    "genre": genre,
                    "score": round(score, 3),
                    "source": "seed_artist"
                })
    
    # Get tracks from similar artists
    for artist in expanded_artists - set(seed_artists):
        tracks = get_lastfm_top_tracks(artist, limit=max(1, tracks_per_artist // 2))
        for track_name, artist_name in tracks:
            artist_eras = ARTIST_ERA_MAP.get(artist_name, [f"{datetime.now().year//10*10}s"])
            for era in artist_eras:
                era_weight = era_weights.get(era, 0.1)
                genre_match = 1.0 if genre.lower() in track_name.lower() else 0.8
                artist_bonus = 1.0  # Normal bonus for similar artists
                
                score = genre_match * era_weight * artist_bonus
                
                recommendations.append({
                    "artist": artist_name,
                    "track": track_name,
                    "era": era,
                    "genre": genre,
                    "score": round(score, 3),
                    "source": "similar_artist"
                })
    
    # Remove duplicates and sort by score
    seen_tracks = set()
    unique_recommendations = []
    
    for rec in recommendations:
        track_key = f"{rec['artist']}||{rec['track']}"
        if track_key not in seen_tracks:
            seen_tracks.add(track_key)
            unique_recommendations.append(rec)
    
    unique_recommendations.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"🎯 Top recommendations:")
    for i, rec in enumerate(unique_recommendations[:min(10, len(unique_recommendations))]):
        print(f"  {i+1}. {rec['artist']} - {rec['track']} (Era: {rec['era']}, Score: {rec['score']}, Source: {rec['source']})")
    
    return unique_recommendations[:limit]

def infer_era_from_age(birth_year: int) -> Dict[str, float]:
    """Infer preferred musical eras based on birth year"""
    current_year = datetime.now().year
    age = current_year - birth_year
    
    # Musical preference tends to peak in late teens/early 20s
    peak_music_years = list(range(birth_year + 16, birth_year + 25))
    
    era_weights = {}
    
    for year in peak_music_years:
        decade = f"{year//10*10}s"
        era_weights[decade] = era_weights.get(decade, 0) + 0.2
    
    # Add some weight to current era for ongoing exposure
    current_decade = f"{current_year//10*10}s"
    era_weights[current_decade] = era_weights.get(current_decade, 0) + 0.3
    
    # Normalize weights
    if era_weights:
        max_weight = max(era_weights.values())
        era_weights = {era: weight / max_weight for era, weight in era_weights.items()}
    
    return era_weights

def get_lastfm_track_info(artist: str, track: str) -> Optional[Dict]:
    """Get detailed track information from Last.fm"""
    if not LASTFM_API_KEY:
        return None
    
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "track.getInfo",
        "artist": artist.strip(),
        "track": track.strip(),
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "error" not in data and "track" in data:
                track_data = data["track"]
                return {
                    "name": track_data.get("name"),
                    "artist": track_data.get("artist", {}).get("name"),
                    "playcount": int(track_data.get("playcount", 0)),
                    "listeners": int(track_data.get("listeners", 0)),
                    "tags": [tag.get("name") for tag in track_data.get("toptags", {}).get("tag", [])],
                    "duration_ms": int(track_data.get("duration", 0))
                }
    except Exception as e:
        print(f"❌ Error getting track info: {e}")
    
    return None