#!/usr/bin/env python3
"""
moodQue System Testing Script
Run this from VS Code terminal: python test_moodque.py
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
RAILWAY_URL = "https://web-production-ed9ad.up.railway.app/"  # Replace with your Railway URL
LOCAL_URL = "http://localhost:5000"

# Choose which to test
BASE_URL =  RAILWAY_URL  # Change to RAILWAY_URL for production testing

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.PURPLE}🎵 {text}{Colors.END}")
    print("=" * (len(text) + 4))

def print_test(description):
    print(f"\n{Colors.BLUE}📡 Testing: {description}{Colors.END}")

def print_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message):
    print(f"{Colors.CYAN}ℹ️  {message}{Colors.END}")

def make_request(method, endpoint, data=None, description=""):
    print_test(description)
    print(f"   Method: {method}")
    print(f"   Endpoint: {BASE_URL}{endpoint}")
    
    try:
        if method.upper() == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=30)
        elif method.upper() == "POST":
            if data:
                print(f"   Data: {json.dumps(data, indent=2)}")
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=30)
        else:
            print_error(f"Unsupported method: {method}")
            return False
        
        print(f"   Status: {response.status_code}")
        
        # Try to parse JSON response
        try:
            response_json = response.json()
            print("   Response:")
            print(json.dumps(response_json, indent=4))
        except:
            print(f"   Response: {response.text}")
        
        # Check success
        if 200 <= response.status_code < 300:
            print_success("SUCCESS")
            return True
        else:
            print_error(f"FAILED - HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_error("CONNECTION ERROR - Is the server running?")
        return False
    except requests.exceptions.Timeout:
        print_error("TIMEOUT - Request took too long")
        return False
    except Exception as e:
        print_error(f"EXCEPTION: {str(e)}")
        return False
    finally:
        print("-" * 50)

def run_tests():
    print_header("moodQue System Testing")
    print_info(f"Testing against: {BASE_URL}")
    
    results = []
    
    # Test 1: Basic health check
    results.append(make_request("GET", "/", description="Basic Health Check"))
    
    # Test 2: Detailed health check
    results.append(make_request("GET", "/health_detailed", description="Detailed Health Check"))
    
    # Test 3: Firebase connection
    results.append(make_request("GET", "/test_firebase", description="Firebase Connection Test"))
    
    # Test 4: Simple playlist creation
    playlist_data = {
        "row_id": "test_001",
        "user_id": "test@example.com",
        "genre": "jazz",
        "artist": "Miles Davis",
        "mood": "chill",
        "event": "VS Code Test Jazz Playlist",
        "time": 15,
        "playlist_type": "clean"
    }
    results.append(make_request("POST", "/glide_social", playlist_data, "Simple Playlist Creation (Jazz)"))
    
    # Test 5: Era overlap test (Snoop Dogg + Pharrell should find 2000s overlap)
    era_overlap_data = {
        "row_id": "test_002",
        "user_id": "test@example.com", 
        "genre": "hip-hop",
        "artist": "Snoop Dogg, Pharrell",
        "mood": "party",
        "event": "Era Overlap Test (2000s)",
        "time": 20,
        "playlist_type": "clean"
    }
    results.append(make_request("POST", "/glide_social", era_overlap_data, "Era Overlap Test (Hip-Hop)"))
    
    # Test 6: Different eras test (Frank Sinatra + Sade should be treated individually)
    different_eras_data = {
        "row_id": "test_003",
        "user_id": "test@example.com",
        "genre": "jazz", 
        "artist": "Frank Sinatra, Sade",
        "mood": "romantic",
        "event": "Different Eras Test",
        "time": 25,
        "playlist_type": "clean"
    }
    results.append(make_request("POST", "/glide_social", different_eras_data, "Different Eras Test"))
    
    # Test 7: Interaction tracking
    interaction_data = {
        "user_id": "test@example.com",
        "event_type": "playlist_played",
        "data": {
            "playlist_id": "test123",
            "mood_tags": ["happy"],
            "genres": ["pop"]
        }
    }
    results.append(make_request("POST", "/track", interaction_data, "Interaction Tracking Test"))
    
    # Test 8: Spotify connection status
    spotify_data = {
        "user_email": "test@example.com"
    }
    results.append(make_request("POST", "/check_spotify_status", spotify_data, "Spotify Connection Status"))
    
    # Test 9: ML Feedback
    feedback_data = {
        "user_id": "test@example.com",
        "playlist_id": "test123", 
        "feedback_type": "positive",
        "rating": 5,
        "comments": "Great playlist!"
    }
    results.append(make_request("POST", "/feedback", feedback_data, "ML Feedback Test"))
    
    # Summary
    print_header("Test Summary")
    passed = sum(results)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print_success("All tests passed! 🎉")
    elif passed > total // 2:
        print(f"{Colors.YELLOW}⚠️  Some tests failed. Check the output above.{Colors.END}")
    else:
        print_error("Many tests failed. Check your configuration and server status.")
    
    print_info("\nKey things to look for in successful responses:")
    print("  • Firebase: 'Firebase is working properly'")
    print("  • Playlists: 'Playlist created successfully' or Spotify URLs")
    print("  • Tracking: 'Interaction logged successfully'") 
    print("  • Era Logic: Messages about era overlap or individual treatment")
    
    print_info(f"\nIf testing locally, ensure your server is running:")
    print("  python moodQueSocial_webhook_service.py")
    
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)