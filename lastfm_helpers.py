import os
import requests
from dotenv import load_dotenv

# Load local .env only if not running on Railway
if not os.environ.get("RAILWAY_ENVIRONMENT"):
    load_dotenv()

def get_similar_artists(artist_name, limit=5):
    """Fetch similar artists from Last.fm with better error handling and debugging"""
    
    # Debug: Check if API key exists
    if not LASTFM_API_KEY:
        print("❌ LASTFM_API_KEY not found in environment variables")
        return []
    
    print(f"🔍 Searching Last.fm for similar artists to: '{artist_name}'")
    
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name.strip(),  # Remove any extra whitespace
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit
    }
    
    print(f"🌐 Last.fm API request: {url}")
    print(f"📝 Parameters: {params}")
    
    try:
        res = requests.get(url, params=params, timeout=10)
        print(f"🔎 RAW Last.fm response: {res.status_code}")
        print(f"📄 Response content: {res.text[:500]}...")  # Show first 500 chars
        
        if res.status_code == 200:
            try:
                data = res.json()
                print(f"✅ Parsed JSON response: {type(data)}")
                
                # Check for error in response
                if "error" in data:
                    print(f"❌ Last.fm API Error {data['error']}: {data.get('message', 'Unknown error')}")
                    return []
                
                # Try to extract similar artists
                similar_artists = data.get("similarartists", {})
                if isinstance(similar_artists, dict):
                    artists_list = similar_artists.get("artist", [])
                    if isinstance(artists_list, list):
                        artist_names = [a.get("name") for a in artists_list if isinstance(a, dict) and "name" in a]
                        print(f"🎵 Found {len(artist_names)} similar artists: {artist_names}")
                        return artist_names
                    elif isinstance(artists_list, dict):
                        # Sometimes Last.fm returns a single artist as dict instead of list
                        artist_name = artists_list.get("name")
                        if artist_name:
                            print(f"🎵 Found 1 similar artist: {artist_name}")
                            return [artist_name]
                
                print("⚠️ No similar artists found in response structure")
                return []
                
            except Exception as e:
                print(f"❌ Failed to parse Last.fm JSON response: {e}")
                return []
        else:
            print(f"❌ Last.fm API request failed with status {res.status_code}")
            return []
            
    except requests.exceptions.Timeout:
        print("❌ Last.fm API request timed out")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Last.fm API request failed: {e}")
        return []

def get_top_tracks(artist_name, limit=5):
    """Get top tracks for a given artist from Last.fm with better error handling"""
    
    if not LASTFM_API_KEY:
        print("❌ LASTFM_API_KEY not found in environment variables")
        return []
    
    print(f"🔍 Getting top tracks for: '{artist_name}'")
    
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
        print(f"🎵 Top tracks response for {artist_name}: {res.status_code}")
        
        if res.status_code == 200:
            try:
                data = res.json()
                
                # Check for error in response
                if "error" in data:
                    print(f"❌ Last.fm API Error {data['error']}: {data.get('message', 'Unknown error')}")
                    return []
                
                top_tracks = data.get("toptracks", {})
                if isinstance(top_tracks, dict):
                    tracks_list = top_tracks.get("track", [])
                    if isinstance(tracks_list, list):
                        track_tuples = []
                        for t in tracks_list:
                            if isinstance(t, dict) and "name" in t:
                                track_tuples.append((t["name"], artist_name))
                        print(f"🎼 Found {len(track_tuples)} top tracks for {artist_name}")
                        return track_tuples
                    elif isinstance(tracks_list, dict):
                        # Single track case
                        track_name = tracks_list.get("name")
                        if track_name:
                            return [(track_name, artist_name)]
                
                print(f"⚠️ No top tracks found for {artist_name}")
                return []
                
            except Exception as e:
                print(f"❌ Error parsing top tracks for {artist_name}: {e}")
                return []
        else:
            print(f"❌ Top tracks request failed for {artist_name}: {res.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error fetching top tracks for {artist_name}: {e}")
        return []

def test_lastfm_connection():
    """Test function to verify Last.fm API is working"""
    print("🧪 Testing Last.fm API connection...")
    
    if not LASTFM_API_KEY:
        print("❌ No LASTFM_API_KEY found!")
        return False
    
    # Test with a very simple, guaranteed artist
    test_artists = ["Beatles", "Taylor Swift", "Drake"]
    
    for artist in test_artists:
        print(f"\n🎯 Testing with: {artist}")
        similar = get_similar_artists(artist, limit=2)
        if similar:
            print(f"✅ Success! Found similar artists: {similar}")
            return True
        else:
            print(f"❌ Failed for {artist}")
    
    print("❌ All Last.fm tests failed!")
    return False