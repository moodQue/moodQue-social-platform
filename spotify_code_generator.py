"""
Spotify Code Generator for MoodQue Social Platform
Generates Spotify codes for playlists and integrates with the social features
"""

import requests
from urllib.parse import quote
import os
from dotenv import load_dotenv

load_dotenv()

class SpotifyCodeGenerator:
    def __init__(self):
        self.base_url = "https://scannables.scdn.co/uri/plain/"
        
    def extract_playlist_id(self, spotify_url):
        """Extract playlist ID from Spotify URL"""
        try:
            # Handle different Spotify URL formats
            if "open.spotify.com/playlist/" in spotify_url:
                # Extract from web URL: https://open.spotify.com/playlist/ID?si=...
                playlist_id = spotify_url.split("/playlist/")[1].split("?")[0]
            elif "spotify:playlist:" in spotify_url:
                # Extract from URI: spotify:playlist:ID
                playlist_id = spotify_url.split("spotify:playlist:")[1]
            else:
                raise ValueError("Invalid Spotify URL format")
                
            return playlist_id
        except Exception as e:
            print(f"❌ Error extracting playlist ID: {e}")
            return None
    
    def generate_spotify_code(self, spotify_url, format="png", size=320, background_color="white", bar_color="black"):
        """
        Generate Spotify code for a playlist
        
        Args:
            spotify_url: Spotify playlist URL or URI
            format: Image format (png, svg, jpeg)
            size: Image size (160, 320, 640)
            background_color: Background color (white, black, or hex code)
            bar_color: Bar color (white, black, or hex code)
        
        Returns:
            Dict with code URL and metadata
        """
        try:
            playlist_id = self.extract_playlist_id(spotify_url)
            if not playlist_id:
                return None
            
            # Construct Spotify URI
            spotify_uri = f"spotify:playlist:{playlist_id}"
            
            # URL encode the URI
            encoded_uri = quote(spotify_uri, safe='')
            
            # Construct final URL - using the working format
            code_url = f"https://scannables.scdn.co/uri/plain/{format}/{size}/{encoded_uri}"
            
            print(f"✅ Generated Spotify code URL: {code_url}")
            
            return {
                "code_url": code_url,
                "playlist_id": playlist_id,
                "spotify_uri": spotify_uri,
                "format": format,
                "size": size,
                "background_color": background_color,
                "bar_color": bar_color
            }
            
        except Exception as e:
            print(f"❌ Error generating Spotify code: {e}")
            return None
    
    def get_multiple_formats(self, spotify_url):
        """Generate Spotify codes in multiple formats for different use cases"""
        formats = {
            "small": {"size": 160, "format": "png"},
            "medium": {"size": 320, "format": "png"},
            "large": {"size": 640, "format": "png"},
            "svg": {"size": 320, "format": "svg"}
        }
        
        codes = {}
        for name, config in formats.items():
            code_data = self.generate_spotify_code(
                spotify_url, 
                format=config["format"], 
                size=config["size"]
            )
            if code_data:
                codes[name] = code_data
        
        return codes

def add_spotify_code_to_playlist_data(playlist_data, spotify_url):
    """Add Spotify code data to playlist information"""
    try:
        code_gen = SpotifyCodeGenerator()
        
        # Generate multiple code formats
        codes = code_gen.get_multiple_formats(spotify_url)
        
        if codes:
            # Add code data to playlist
            playlist_data["spotify_codes"] = codes
            playlist_data["has_spotify_code"] = True
            
            # Add primary code URL for easy access
            if "medium" in codes:
                playlist_data["primary_code_url"] = codes["medium"]["code_url"]
            elif codes:
                # Use first available code
                first_code = list(codes.values())[0]
                playlist_data["primary_code_url"] = first_code["code_url"]
            
            print(f"✅ Added Spotify codes to playlist data")
            return True
        else:
            playlist_data["has_spotify_code"] = False
            print("❌ Failed to generate Spotify codes")
            return False
            
    except Exception as e:
        print(f"❌ Error adding Spotify code: {e}")
        playlist_data["has_spotify_code"] = False
        return False

# Test function
def test_spotify_code_generation():
    """Test Spotify code generation with sample playlist"""
    print("🧪 Testing Spotify Code Generation...")
    
    # Test with a sample Spotify playlist URL
    test_url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"  # Today's Top Hits
    
    code_gen = SpotifyCodeGenerator()
    
    # Test single code generation
    code_data = code_gen.generate_spotify_code(test_url)
    if code_data:
        print(f"✅ Single code generated: {code_data['code_url']}")
    else:
        print("❌ Failed to generate single code")
    
    # Test multiple formats
    codes = code_gen.get_multiple_formats(test_url)
    if codes:
        print(f"✅ Multiple formats generated: {list(codes.keys())}")
        for name, data in codes.items():
            print(f"  {name}: {data['code_url']}")
    else:
        print("❌ Failed to generate multiple codes")

if __name__ == "__main__":
    test_spotify_code_generation()