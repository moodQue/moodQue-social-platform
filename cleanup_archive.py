import os
import shutil

# Files to archive
FILES_TO_ARCHIVE = [
    "SpotifyPlaylistBuilder.py",
    "SpotifyPlaylistBuilder_backup.py",
    "spotify_code_generator.py",
    "test_lastfm_pipeline.py",
    "moodQueSocial_webhook_service_backup.py",  # FIXED: Added missing comma
    "test_lastfm_pipeline.py"
]

ARCHIVE_DIR = "archive"

def ensure_archive_dir():
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
        print(f"📁 Created archive folder: {ARCHIVE_DIR}")

def move_files_to_archive():
    for filename in FILES_TO_ARCHIVE:
        if os.path.exists(filename):
            shutil.move(filename, os.path.join(ARCHIVE_DIR, filename))
            print(f"📦 Archived: {filename}")
        else:
            print(f"⚠️ File not found: {filename}")

if __name__ == "__main__":
    ensure_archive_dir()
    move_files_to_archive()
    print("✅ Cleanup complete.")