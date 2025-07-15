import os
import firebase_admin
from firebase_admin import credentials, firestore

# Only load .env locally; Railway sets env vars directly
if os.getenv("RAILWAY_ENVIRONMENT") is None:
    from dotenv import load_dotenv
    load_dotenv()

# Path to the Firebase credentials file
cred = credentials.Certificate("config/firebase_credentials.json")

# Initialize Firebase app
firebase_admin.initialize_app(cred)

# Firestore DB instance
db = firestore.client()

