import os
import json
import datetime
import time
import base64
import requests

# Use your existing Firebase initialization instead of creating a new one
from firebase_admin_init import db

# Spotify credential environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://example.com/callback")

def get_spotify_access_token():
    """Get system/app access token for MoodQue"""
    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": SPOTIFY_REFRESH_TOKEN
    }
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)

    if response.status_code != 200:
        print("❌ Failed to refresh app access token", response.text)
        raise Exception("Spotify token refresh failed")

    token_info = response.json()
    return token_info["access_token"]

def refresh_token_with_spotify(refresh_token):
    """Refresh a user's token with Spotify API"""
    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    if response.status_code != 200:
        print("❌ Failed to refresh user token", response.text)
        raise Exception("Spotify user token refresh failed")

    token_data = response.json()
    return {
        "access_token": token_data["access_token"],
        "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(seconds=token_data["expires_in"])).isoformat()
    }

def refresh_access_token(user_id=None):
    """
    Main function to get access token - for user if user_id provided, else system token
    UPDATED to handle both field name formats for compatibility
    """
    if user_id and user_id != 'unknown':
        try:
            print(f"🔄 Refreshing token for user: {user_id}")
            
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                user_data = doc.to_dict()
                current_access_token = user_data.get("spotify_access_token")
                refresh_token = user_data.get("spotify_refresh_token")
                
                # Handle both field name formats for expires time
                token_expiry = (user_data.get("spotify_token_expires_at") or 
                               user_data.get("spotify_token_expiry"))

                # Check if current token is still valid
                if current_access_token and token_expiry:
                    try:
                        # Handle different expiry formats
                        if isinstance(token_expiry, str):
                            try:
                                # Try ISO format first
                                expiry_time = datetime.datetime.fromisoformat(token_expiry.replace('Z', '+00:00'))
                            except ValueError:
                                # Try timestamp format
                                expiry_time = datetime.datetime.fromtimestamp(float(token_expiry))
                        else:
                            expiry_time = datetime.datetime.fromtimestamp(float(token_expiry))
                        
                        # If token expires more than 5 minutes from now, use current token
                        if expiry_time > datetime.datetime.utcnow() + datetime.timedelta(minutes=5):
                            print(f"✅ Current token for user {user_id} is still valid")
                            return current_access_token
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ Error parsing expiry time: {e}")

                # Refresh the token if we have a refresh token
                if refresh_token:
                    print(f"🔄 Refreshing expired token for user {user_id}")
                    new_token_data = refresh_token_with_spotify(refresh_token)
                    
                    # Update with standardized field names
                    update_data = {
                        "spotify_access_token": new_token_data["access_token"],
                        "spotify_token_expires_at": new_token_data["expires_at"],
                        "last_token_refresh": datetime.datetime.now().isoformat()
                    }
                    
                    # Also update the old field name for backward compatibility
                    update_data["spotify_token_expiry"] = new_token_data["expires_at"]
                    
                    doc_ref.update(update_data)
                    
                    print(f"✅ Successfully refreshed token for user {user_id}")
                    return new_token_data["access_token"]
                else:
                    print(f"❌ No refresh token found for user {user_id}")

        except Exception as e:
            print(f"⚠️ Error refreshing user token from Firestore: {e}")

    # Fallback to system token
    print("🔐 Using system token as fallback")
    return get_spotify_access_token()

def get_user_access_token(user_id):
    """
    Get a valid access token for the user, refreshing if necessary
    """
    return refresh_access_token(user_id)

def is_user_connected(user_id):
    """
    Check if user has valid Spotify connection
    """
    try:
        if not user_id or user_id == 'unknown':
            return False
            
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        user_data = doc.to_dict()
        return bool(user_data.get("spotify_refresh_token"))
        
    except Exception as e:
        print(f"❌ Error checking user connection: {e}")
        return False

def revoke_user_tokens(user_id):
    """
    Revoke and clear user tokens from database
    """
    try:
        db.collection("users").document(user_id).update({
            "spotify_access_token": None,
            "spotify_refresh_token": None,
            "spotify_token_expires_at": None,
            "spotify_token_expiry": None,  # Clear old field name too
            "tokens_revoked_at": datetime.datetime.now().isoformat()
        })
        print(f"✅ Revoked tokens for user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error revoking tokens for user {user_id}: {e}")
        return False

def get_user_spotify_info(user_id):
    """
    Get user's Spotify profile information
    """
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            user_data = doc.to_dict()
            return {
                "spotify_user_id": user_data.get("spotify_user_id"),
                "spotify_display_name": user_data.get("spotify_display_name"),
                "connected_at": user_data.get("connected_at"),
                "is_connected": bool(user_data.get("spotify_refresh_token"))
            }
        return None
    except Exception as e:
        print(f"❌ Error getting user Spotify info: {e}")
        return None