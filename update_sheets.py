"""
Google Sheets Update Script for Spotify Code Features
Run this FIRST to add the new Spotify code columns to your existing Social Playlists sheet
"""

import gspread
from google.oauth2.service_account import Credentials
import os
import json

def get_google_credentials():
    """Get Google credentials from environment variable or file"""
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            return Credentials.from_service_account_info(creds_dict, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ])
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing Google credentials: {e}")
            return None
    else:
        SERVICE_ACCOUNT_FILE = "moodQue-automation-437f1e4eaa49.json"
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ])
        else:
            print(f"❌ No Google credentials found")
            return None

def update_social_playlists_sheet():
    """Add Spotify code columns to existing Social Playlists sheet"""
    try:
        creds = get_google_credentials()
        if not creds:
            print("❌ Failed to get Google credentials")
            return False
            
        client = gspread.authorize(creds)
        spreadsheet = client.open("Playlist App Data")
        
        # Get the Social Playlists sheet
        try:
            social_sheet = spreadsheet.worksheet("Social Playlists")
            print("✅ Found Social Playlists sheet")
        except gspread.WorksheetNotFound:
            print("❌ Social Playlists sheet not found")
            return False
        
        # Get current headers
        current_headers = social_sheet.row_values(1)
        print(f"📊 Current headers ({len(current_headers)}): {current_headers}")
        
        # Check if Spotify code columns already exist
        spotify_code_columns = [
            "Spotify Code URL",
            "Has Code", 
            "Code Generated",
            "Code Format"
        ]
        
        existing_spotify_columns = [col for col in spotify_code_columns if col in current_headers]
        
        if existing_spotify_columns:
            print(f"⚠️ Some Spotify code columns already exist: {existing_spotify_columns}")
            user_input = input("Do you want to continue anyway? (y/n): ")
            if user_input.lower() != 'y':
                print("❌ Update cancelled by user")
                return False
        
        # Add the new headers
        new_headers = current_headers + spotify_code_columns
        
        # Update the header row
        header_range = f"A1:{chr(64 + len(new_headers))}1"
        social_sheet.update(header_range, [new_headers])
        
        print(f"✅ Added Spotify code columns to Social Playlists sheet")
        print(f"📊 New columns added:")
        start_col = len(current_headers) + 1
        for i, col in enumerate(spotify_code_columns):
            col_letter = chr(64 + start_col + i)
            print(f"   {col_letter}: {col}")
        
        # Initialize new columns with default values for existing rows
        try:
            all_values = social_sheet.get_all_values()
            num_rows = len(all_values)
            
            if num_rows > 1:  # If there are data rows
                print(f"📝 Initializing {num_rows - 1} existing rows with default values...")
                
                # Prepare default values for existing rows
                default_values = []
                for row_num in range(2, num_rows + 1):  # Start from row 2 (after header)
                    default_row = [
                        "",      # Spotify Code URL (empty initially)
                        "FALSE", # Has Code
                        "",      # Code Generated (empty initially)
                        ""       # Code Format (empty initially)
                    ]
                    default_values.append(default_row)
                
                # Update the new columns for existing rows
                if default_values:
                    start_col_letter = chr(64 + start_col)
                    end_col_letter = chr(64 + start_col + len(spotify_code_columns) - 1)
                    range_name = f"{start_col_letter}2:{end_col_letter}{num_rows}"
                    social_sheet.update(range_name, default_values)
                    print(f"✅ Initialized {len(default_values)} existing rows")
                
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize existing rows: {e}")
            print("   This is okay - new columns are added but existing rows may need manual updating")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating Social Playlists sheet: {e}")
        return False

def main():
    """Main function to run the update process"""
    print("🚀 MoodQue Spotify Code Integration - Sheet Update")
    print("=" * 50)
    
    # Check credentials first
    creds = get_google_credentials()
    if not creds:
        print("❌ Cannot proceed without Google credentials")
        print("   Make sure you have either:")
        print("   1. GOOGLE_SERVICE_ACCOUNT_JSON environment variable set")
        print("   2. moodQue-automation-437f1e4eaa49.json file in current directory")
        return
    
    print("✅ Google credentials found")
    
    # Update the sheet structure
    print("\n📋 Adding Spotify code columns to Social Playlists sheet...")
    update_success = update_social_playlists_sheet()
    
    if update_success:
        print("\n🎉 Sheet update complete!")
        print("\n📋 Next steps:")
        print("1. Update your webhook service with the new code")
        print("2. Test the integration")
        print("3. Update your Glide app")
    else:
        print("\n❌ Sheet update failed!")
        print("Please check your credentials and try again.")

if __name__ == "__main__":
    main()