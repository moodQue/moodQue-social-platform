"""
Google Sheets Setup for MoodQue Social Platform
Run this script to automatically create all required sheets with proper headers
"""

import gspread
from google.oauth2.service_account import Credentials
import os

# Setup Google Sheets API credentials
SERVICE_ACCOUNT_FILE = "moodQue-automation-437f1e4eaa49.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def setup_all_sheets():
    """Create all required sheets for moodQue Social Platform"""
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # Open or create the main spreadsheet
        try:
            spreadsheet = client.open("Playlist App Data")
            print("✅ Found existing spreadsheet: Playlist App Data")
        except gspread.SpreadsheetNotFound:
            spreadsheet = client.create("Playlist App Data")
            print("✅ Created new spreadsheet: Playlist App Data")
            # Share with your email for access
            spreadsheet.share('greatdayteesstore@gmail.com', perm_type='user', role='owner')
        
        # 1. User Profiles Sheet
        setup_user_profiles_sheet(spreadsheet)
        
        # 2. Social Playlists Sheet  
        setup_social_playlists_sheet(spreadsheet)
        
        # 3. Social Interactions Sheet
        setup_social_interactions_sheet(spreadsheet)
        
        # 4. Genres Reference Sheet
        setup_genres_sheet(spreadsheet)
        
        # 5. Mood Tags Reference Sheet
        setup_mood_tags_sheet(spreadsheet)
        
        # 6. Analytics Summary Sheet
        setup_analytics_sheet(spreadsheet)
        
        print(f"\n🎉 All sheets created successfully!")
        print(f"📊 Spreadsheet URL: {spreadsheet.url}")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up sheets: {e}")
        return False

def setup_user_profiles_sheet(spreadsheet):
    """Create User Profiles sheet"""
    try:
        sheet = spreadsheet.worksheet("User Profiles")
        print("✅ User Profiles sheet already exists")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="User Profiles", rows="1000", cols="15")
        headers = [
            "User Email", "User Name", "Current Mood", "Last Active", 
            "Total Playlists", "Total Likes Received", "Total Likes Given",
            "Favorite Genre", "Favorite Mood", "Profile Created", 
            "Streak Days", "Last Streak Date", "Bio", "Avatar", "Status"
        ]
        sheet.append_row(headers)
        print("✅ Created User Profiles sheet")

def setup_social_playlists_sheet(spreadsheet):
    """Create Social Playlists sheet"""
    try:
        sheet = spreadsheet.worksheet("Social Playlists")
        print("✅ Social Playlists sheet already exists")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Social Playlists", rows="2000", cols="20")
        headers = [
            "Playlist ID", "Creator Email", "Creator Name", "Event Name",
            "Genre", "Mood", "Spotify URL", "Created Date", "Likes Count",
            "Views Count", "Shares Count", "Tags", "Description", 
            "Track Count", "Duration", "Is Public", "Is Trending",
            "Last Liked", "Featured", "Playlist Type"
        ]
        sheet.append_row(headers)
        print("✅ Created Social Playlists sheet")

def setup_social_interactions_sheet(spreadsheet):
    """Create Social Interactions sheet"""
    try:
        sheet = spreadsheet.worksheet("Social Interactions")
        print("✅ Social Interactions sheet already exists")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Social Interactions", rows="5000", cols="10")
        headers = [
            "Interaction ID", "User Email", "Playlist ID", "Interaction Type",
            "Timestamp", "Additional Data", "IP Address", "User Agent",
            "Session ID", "Source"
        ]
        sheet.append_row(headers)
        print("✅ Created Social Interactions sheet")

def setup_genres_sheet(spreadsheet):
    """Create Genres reference sheet with valid Spotify genres"""
    try:
        sheet = spreadsheet.worksheet("Valid Genres")
        print("✅ Valid Genres sheet already exists")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Valid Genres", rows="200", cols="5")
        headers = ["Spotify Genre", "Display Name", "Category", "Popularity", "Description"]
        sheet.append_row(headers)
        
        # Add some popular genres
        popular_genres = [
            ["pop", "Pop", "Mainstream", "High", "Popular mainstream music"],
            ["rock", "Rock", "Rock", "High", "Rock and roll music"],
            ["hip-hop", "Hip Hop", "Urban", "High", "Hip hop and rap music"],
            ["chill", "Chill/Lo-Fi", "Relaxed", "Medium", "Relaxed, chill music"],
            ["electronic", "Electronic", "Electronic", "Medium", "Electronic and EDM"],
            ["jazz", "Jazz", "Jazz", "Medium", "Jazz and blues"],
            ["classical", "Classical", "Classical", "Low", "Classical music"],
            ["indie", "Indie", "Alternative", "Medium", "Independent music"],
            ["r-n-b", "R&B", "Urban", "High", "Rhythm and blues"],
            ["reggae", "Reggae", "World", "Medium", "Reggae music"],
            ["country", "Country", "Country", "Medium", "Country music"],
            ["grunge", "Grunge", "Rock", "Medium", "Grunge rock music"],
            ["funk", "Funk", "Funk", "Medium", "Funk music"],
            ["soul", "Soul", "Soul", "Medium", "Soul music"],
            ["latin", "Latin", "World", "Medium", "Latin music"]
        ]
        
        for genre_row in popular_genres:
            sheet.append_row(genre_row)
        
        print("✅ Created Valid Genres sheet with popular genres")

def setup_mood_tags_sheet(spreadsheet):
    """Create Mood Tags reference sheet"""
    try:
        sheet = spreadsheet.worksheet("Mood Tags")
        print("✅ Mood Tags sheet already exists")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Mood Tags", rows="50", cols="6")
        headers = ["Mood Name", "Energy Level", "Valence", "Use Case", "Icon", "Description"]
        sheet.append_row(headers)
        
        # Add mood definitions
        moods = [
            ["Happy", "High", "Very High", "Celebration, Good Times", "😊", "Joyful, positive vibes"],
            ["Chill", "Low", "Medium", "Relaxation, Background", "😌", "Relaxed, laid-back music"],
            ["Upbeat", "High", "High", "Motivation, Exercise", "⚡", "High energy, motivational"],
            ["Hype", "Very High", "High", "Workout, Party Prep", "🔥", "Maximum energy, pump-up"],
            ["Party", "Very High", "Very High", "Dancing, Celebration", "🎉", "Dance, celebration music"],
            ["Workout", "High", "Medium", "Exercise, Gym", "💪", "Gym, exercise, training"],
            ["Focus", "Medium", "Low", "Study, Work", "🎯", "Concentration, productivity"],
            ["Romantic", "Low", "High", "Date Night, Love", "💕", "Love songs, intimate"],
            ["Melancholy", "Low", "Very Low", "Reflection, Sadness", "😔", "Sad, reflective music"],
            ["Energetic", "High", "High", "Active, Lively", "⚡", "High-energy, lively"],
            ["Calm", "Very Low", "Low", "Meditation, Peace", "🧘", "Peaceful, serene"],
            ["Sad", "Very Low", "Very Low", "Emotional Release", "😢", "Emotional, slower tempo"]
        ]
        
        for mood_row in moods:
            sheet.append_row(mood_row)
        
        print("✅ Created Mood Tags sheet with definitions")

def setup_analytics_sheet(spreadsheet):
    """Create Analytics Summary sheet"""
    try:
        sheet = spreadsheet.worksheet("Analytics Summary")
        print("✅ Analytics Summary sheet already exists") 
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Analytics Summary", rows="100", cols="10")
        headers = [
            "Metric", "Value", "Date", "Period", "Change", 
            "Top Genre", "Top Mood", "Top Creator", "Notes", "Updated"
        ]
        sheet.append_row(headers)
        
        # Add some initial metrics
        initial_metrics = [
            ["Total Users", "0", "2025-06-14", "All Time", "+0", "", "", "", "Tracks registered users", ""],
            ["Total Playlists", "0", "2025-06-14", "All Time", "+0", "", "", "", "All playlists created", ""],
            ["Total Likes", "0", "2025-06-14", "All Time", "+0", "", "", "", "All likes given", ""],
            ["Active Users (7d)", "0", "2025-06-14", "Weekly", "+0", "", "", "", "Users active in last 7 days", ""],
            ["Popular Genre", "", "2025-06-14", "Weekly", "", "", "", "", "Most used genre this week", ""],
            ["Popular Mood", "", "2025-06-14", "Weekly", "", "", "", "", "Most used mood this week", ""]
        ]
        
        for metric_row in initial_metrics:
            sheet.append_row(metric_row)
        
        print("✅ Created Analytics Summary sheet")

if __name__ == "__main__":
    print("🚀 Setting up MoodQue Social Platform Google Sheets...")
    print("📊 This will create all required sheets with proper structure")
    print()
    
    success = setup_all_sheets()
    
    if success:
        print("\n✅ Setup complete! Your Google Sheets are ready for MoodQue Social Platform")
        print("🔗 Next steps:")
        print("   1. Update your .env file with the spreadsheet ID")
        print("   2. Deploy your webhook server")
        print("   3. Start building social features in Glide!")
    else:
        print("\n❌ Setup failed. Please check your credentials and try again.")