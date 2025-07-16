import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase_app():
    """
    Initialize Firebase Admin SDK only if not already initialized.
    Handles both Railway (env var) and local (file) configurations.
    """
    if not firebase_admin._apps:
        try:
            # Check if we're in a Railway environment with JSON in env
            if "FIREBASE_CREDENTIALS_JSON" in os.environ:
                print("🔥 Loading Firebase credentials from environment variable")
                service_account_info = json.loads(os.environ["FIREBASE_CREDENTIALS_JSON"])
                cred = credentials.Certificate(service_account_info)
            elif "FIREBASE_ADMIN_JSON" in os.environ:
                print("🔥 Loading Firebase credentials from FIREBASE_ADMIN_JSON")
                service_account_info = json.loads(os.environ["FIREBASE_ADMIN_JSON"])
                cred = credentials.Certificate(service_account_info)
            else:
                # Fallback to local file if not in Railway
                print("🔥 Loading Firebase credentials from local file")
                cred_path = os.path.join("config", "firebase_credentials.json")
                cred = credentials.Certificate(cred_path)
            
            firebase_admin.initialize_app(cred)
            print("✅ Firebase initialized successfully")
        except Exception as e:
            print(f"❌ Firebase initialization failed: {e}")
            raise

# Initialize Firebase when module is imported
init_firebase_app()

# Create the Firestore client
db = firestore.client()