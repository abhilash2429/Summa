"""
Test script to verify yt-dlp audio extraction works.
Run: python test_audio_download.py
"""
import yt_dlp
import os
import tempfile

print("=" * 50)
print("Audio Download Test")
print("=" * 50)

def download_audio(youtube_url, output_path):
    """Download audio from YouTube video."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path.replace('.m4a', ''),  # yt-dlp adds extension
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        duration = info.get('duration', 0)
        title = info.get('title', 'Unknown')
        return duration, title

# Test with a short video (Rick Astley - 3:33)
test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Create temp file
temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.m4a')
temp_path = temp_file.name
temp_file.close()

print(f"\nTest URL: {test_url}")
print(f"Temp path: {temp_path}")

try:
    print("\nDownloading audio...")
    duration, title = download_audio(test_url, temp_path)
    
    # The actual file might have a different path due to yt-dlp naming
    actual_path = temp_path.replace('.m4a', '') + '.m4a'
    if not os.path.exists(actual_path):
        actual_path = temp_path
    
    if os.path.exists(actual_path):
        file_size_mb = os.path.getsize(actual_path) / (1024 * 1024)
        print(f"\n✓ Download successful!")
        print(f"  Title: {title}")
        print(f"  Duration: {duration // 60}m {duration % 60}s")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Path: {actual_path}")
        
        # Cleanup
        os.remove(actual_path)
        print(f"\n✓ Cleaned up temp file")
    else:
        print(f"\n✗ File not found at expected path")
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    print("\nMake sure FFmpeg is installed and in your PATH:")
    print("  1. Download from https://ffmpeg.org/download.html")
    print("  2. Extract to C:\\ffmpeg")
    print("  3. Add C:\\ffmpeg\\bin to your system PATH")

print("=" * 50)
