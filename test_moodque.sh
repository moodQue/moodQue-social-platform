#!/bin/bash

# moodQue Testing Script for VS Code Terminal
# Run this from your project root directory

echo "🎵 moodQue System Testing Script"
echo "=================================="

# Set your Railway app URL here (replace with your actual Railway URL)
RAILWAY_URL="https://your-app-name.up.railway.app"
LOCAL_URL="http://localhost:5000"

# Choose which URL to test (change to RAILWAY_URL when testing production)
BASE_URL=$LOCAL_URL

echo "🔧 Testing against: $BASE_URL"
echo ""

# Function to make HTTP requests with better formatting
make_request() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo "📡 Testing: $description"
    echo "   Method: $method"
    echo "   Endpoint: $BASE_URL$endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL$endpoint")
    else
        echo "   Data: $data"
        response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    # Extract HTTP code and response body
    http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
    response_body=$(echo "$response" | sed '/HTTP_CODE:/d')
    
    echo "   Status: $http_code"
    
    # Pretty print JSON response if possible
    if echo "$response_body" | python3 -m json.tool >/dev/null 2>&1; then
        echo "   Response:"
        echo "$response_body" | python3 -m json.tool | sed 's/^/     /'
    else
        echo "   Response: $response_body"
    fi
    
    echo ""
    
    # Check if successful
    if [[ $http_code -ge 200 && $http_code -lt 300 ]]; then
        echo "✅ SUCCESS"
    else
        echo "❌ FAILED"
    fi
    echo "----------------------------------------"
    echo ""
}

# Test 1: Basic health check
make_request "GET" "/" "" "Basic Health Check"

# Test 2: Detailed health check
make_request "GET" "/health_detailed" "" "Detailed Health Check"

# Test 3: Firebase connection test
make_request "GET" "/test_firebase" "" "Firebase Connection Test"

# Test 4: Simple playlist creation test
playlist_data='{
    "row_id": "test_001",
    "user_id": "test@example.com",
    "genre": "jazz",
    "artist": "Miles Davis",
    "mood": "chill",
    "event": "VS Code Test Jazz Playlist",
    "time": 15,
    "playlist_type": "clean"
}'

make_request "POST" "/glide_social" "$playlist_data" "Simple Playlist Creation (Jazz)"

# Test 5: Era overlap test (Snoop Dogg + Pharrell)
era_overlap_data='{
    "row_id": "test_002",
    "user_id": "test@example.com",
    "genre": "hip-hop",
    "artist": "Snoop Dogg, Pharrell",
    "mood": "party",
    "event": "Era Overlap Test (2000s)",
    "time": 20,
    "playlist_type": "clean"
}'

make_request "POST" "/glide_social" "$era_overlap_data" "Era Overlap Test (Hip-Hop)"

# Test 6: Vastly different eras test (Frank Sinatra + Sade)
different_eras_data='{
    "row_id": "test_003", 
    "user_id": "test@example.com",
    "genre": "jazz",
    "artist": "Frank Sinatra, Sade",
    "mood": "romantic",
    "event": "Different Eras Test",
    "time": 25,
    "playlist_type": "clean"
}'

make_request "POST" "/glide_social" "$different_eras_data" "Different Eras Test (Individual Treatment)"

# Test 7: Interaction tracking
interaction_data='{
    "user_id": "test@example.com",
    "event_type": "playlist_played",
    "data": {
        "playlist_id": "test123",
        "mood_tags": ["happy"],
        "genres": ["pop"]
    }
}'

make_request "POST" "/track" "$interaction_data" "Interaction Tracking Test"

# Test 8: Spotify connection status check
spotify_status_data='{
    "user_email": "test@example.com"
}'

make_request "POST" "/check_spotify_status" "$spotify_status_data" "Spotify Connection Status"

# Test 9: Legacy webhook endpoint
legacy_data='{
    "row_id": "test_004",
    "user_id": "test@example.com",
    "genre": "pop",
    "artist": "Taylor Swift",
    "mood": "happy",
    "event": "Legacy Test",
    "time": 30
}'

make_request "POST" "/webhook" "$legacy_data" "Legacy Webhook Test"

# Test 10: ML Feedback endpoint
ml_feedback_data='{
    "user_id": "test@example.com",
    "playlist_id": "test123",
    "feedback_type": "positive",
    "rating": 5,
    "comments": "Great playlist!"
}'

make_request "POST" "/feedback" "$ml_feedback_data" "ML Feedback Test"

echo "🎯 Testing Complete!"
echo ""
echo "📊 Summary:"
echo "• Check the responses above for any ❌ FAILED tests"
echo "• Look for specific success indicators:"
echo "  ✅ 'Firebase is working properly'"
echo "  ✅ 'Playlist created successfully'"
echo "  ✅ 'Interaction logged successfully'"
echo "  ✅ Era overlap messages in playlist responses"
echo ""
echo "🔍 If testing locally, make sure your Flask app is running:"
echo "  python moodQueSocial_webhook_service.py"
echo ""
echo "🚀 To test Railway deployment:"
echo "  1. Change BASE_URL to your Railway URL at the top of this script"
echo "  2. Run the script again"