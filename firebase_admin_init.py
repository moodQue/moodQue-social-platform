import firebase_admin
from firebase_admin import credentials, firestore

# Path to the downloaded service account key
cred = credentials.Certificate("config/firebase_credentials.json")

# Initialize Firebase app
firebase_admin.initialize_app(cred)

# Firestore DB instance
db = firestore.client()
