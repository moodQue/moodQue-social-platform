from datetime import datetime
from firebase_admin import firestore
from firebase_admin_init import db

def track_interaction(user_id, event_type, data):
    """
    Logs a user interaction into the Firestore 'interactions' collection.

    Args:
        user_id (str): Unique identifier for the user.
        event_type (str): Type of interaction (e.g., 'like', 'play', 'skip', 'built_playlist').
        data (dict): Dictionary with additional info like mood_tags, genres, etc.

    Example data:
        {
            "playlist_id": "abc123",
            "mood_tags": ["happy", "focus"],
            "genres": ["hip-hop", "funk"],
            "event": "morning_run"
        }
    """
    interaction = {
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.utcnow(),
        **data
    }

    try:
        db.collection("interactions").add(interaction)
        print(f"✅ Interaction logged successfully: {event_type}")
    except Exception as e:
        print(f"❌ Failed to log interaction: {e}")

# Legacy function for backward compatibility
def track_interaction_legacy(user_id, playlist_id, interaction_type, context_data):
    """
    Legacy function for backward compatibility.
    Maps old parameter structure to new one.
    """
    data = {
        "playlist_id": playlist_id,
        **context_data
    }
    track_interaction(user_id, interaction_type, data)