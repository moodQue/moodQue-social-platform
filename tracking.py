from datetime import datetime
from firebase_admin import firestore
from firebase_admin_init import init_firebase_app

# Ensure Firebase is initialized (should be called in your main app or auth setup)
try:
    db = firestore.client()
except Exception as e:
    raise RuntimeError("Firestore client could not be initialized. Make sure Firebase is set up.") from e

def track_interaction(user_id, playlist_id, interaction_type, context_data):
    """
    Logs a user interaction into the Firestore 'interactions' collection.

    Args:
        user_id (str): Unique identifier for the user.
        playlist_id (str): ID of the playlist interacted with.
        interaction_type (str): Type of interaction (e.g., 'like', 'play', 'skip').
        context_data (dict): Dictionary with additional info like mood_tags, genres, etc.

    Example context_data:
        {
            "mood_tags": ["happy", "focus"],
            "seed_artists": ["Pharrell", "Snoop Dogg"],
            "genres": ["hip hop", "funk"],
            "energy_level": 0.8,
            "source_event": "morning_run"
        }
    """
    interaction = {
        "user_id": user_id,
        "playlist_id": playlist_id,
        "interaction_type": interaction_type,
        "timestamp": datetime.utcnow(),
        **context_data
    }

    try:
        db.collection("interactions").add(interaction)
        print("✅ Interaction logged successfully.")
    except Exception as e:
        print(f"❌ Failed to log interaction: {e}")
