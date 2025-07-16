from dotenv import load_dotenv
from lastfm_recommender import get_recommendations
import os
import requests
import base64
import random
import uuid
import json
import traceback

from firebase_admin_init import init_firebase_app, db
from tracking import track_interaction
from moodque_utilities import (
    get_valid_access_token,
    get_spotify_user_id,
    create_new_playlist,
    add_tracks_to_playlist,
    calculate_playlist_duration,
    search_spotify_tracks_enhanced_with_duration,
    search_spotify_track
)

# Add this function to fix the track_interaction call
def track_interaction_wrapper(user_id, playlist_id, interaction_type, data):
    """Wrapper to maintain compatibility with old function signature"""
    updated_data = {
        "playlist_id": playlist_id,
        **data
    }
    track_interaction(user_id, interaction_type, updated_data)

# Replace the track_interaction call in build_smart_playlist_enhanced with:
# track_interaction_wrapper(user_id, playlist_id, "built_playlist", {...})

# Rest of your moodque_engine.py file continues unchanged...