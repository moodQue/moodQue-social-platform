import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Check if we're in a Railway environment with JSON in env
if "FIREBASE_CREDENTIALS_JSON" in os.environ:
    service_account_info = json.loads(os.environ["FIREBASE_CREDENTIALS_JSON"])
    cred = credentials.Certificate(service_account_info)
else:
    # Fallback to local file if not in Railway
    cred_path = os.path.join("config", "firebase_credentials.json")
    cred = credentials.Certificate(cred_path)

# Initialize Firebase app and Firestore
firebase_admin.initialize_app(cred)
db = firestore.client()
