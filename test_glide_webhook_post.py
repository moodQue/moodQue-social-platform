import requests
import json

# Replace with your actual return webhook URL
GLIDE_RETURN_WEBHOOK_URL = "https://go.glideapps.com/api/container/plugin/webhook-trigger/WE36jV1c5vSHZWc5A4oC/a170355b-005a-4c5a-ab2a-c65bdf04ad7a"

# Sample payload you would normally send back to Glide
test_payload = {
    "row_id": "DrQVijN6Qtm2MSG8PIEtPA",  # Make sure this is a real row_id in your Glide sheet
    "playlist_id": "1234567890abcdef",
    "spotify_url": "https://open.spotify.com/playlist/1234567890abcdef",
    "spotify_code_url": "https://scannables.scdn.co/uri/plain/jpeg/black/white/640/spotify:playlist:1234567890abcdef",
    "has_code": "true",        # String version of boolean
    "track_count": "12"        # String version of integer
}

try:
    response = requests.post(
        GLIDE_RETURN_WEBHOOK_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_payload)
    )

    print(f"✅ Status Code: {response.status_code}")
    print(f"📨 Response Body:\n{response.text}")

except Exception as e:
    print(f"❌ Failed to send POST request: {e}")
