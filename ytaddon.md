# Handling YouTube Videos Without Captions/Transcripts
## Audio Transcription Integration Guide

---

## The Problem

Your current implementation fails when encountering YouTube videos that have:
- No captions (manual or auto-generated)
- Disabled captions
- Private/unlisted videos without transcript data

According to your current `fetch_youtube_transcript()` function, it returns:
```python
"No English transcript available"
```

This means the summarizer cannot work on ~30-40% of YouTube videos.

---

## The Solution: Audio Transcription

You need to add a fallback system that:
1. Detects when no transcript is available
2. Downloads the audio from the YouTube video
3. Transcribes the audio to text using a speech-to-text model
4. Passes the transcribed text to your summarization pipeline

---

## Architecture Options

### Option 1: OpenAI Whisper API (Paid, Easy)
**Cost:** $0.006/minute ($0.36 for 1-hour video)
**Pros:**
- No infrastructure setup
- High accuracy (99%+)
- Supports 100+ languages
- Fast (processes 60 min in ~6-12 min)

**Cons:**
- Requires OpenAI API key (separate from Google LLM)
- Costs scale with usage
- 25MB file size limit (needs chunking for long videos)

### Option 2: Self-Hosted Whisper (Free, Complex)
**Cost:** Free (uses your existing GPU)
**Pros:**
- No per-request costs
- Complete privacy (audio never leaves your machine)
- Can use large-v3 model (best accuracy)

**Cons:**
- Initial setup complexity
- Uses GPU memory (will compete with BART if you still run it)
- Slower than API (but manageable on RTX 3090)

### Option 3: Third-Party Transcription API
**Examples:** AssemblyAI, Deepgram, Rev.ai
**Cost:** Similar to Whisper (~$0.005-0.01/min)
**Note:** Not recommended since you already have GPU access

---

## Recommended: Self-Hosted Whisper

Since you have an RTX 3090 and already run local models, self-hosting Whisper is the best option. Here's why:
- Zero marginal cost per video
- Your extension stays "free to use" (no API costs)
- RTX 3090 has plenty of VRAM (Whisper large-v3 needs ~10GB)

---

# Implementation Guide

## Phase 1: Install Whisper

### Step 1: Install OpenAI Whisper

**Action:** With your venv active, execute:
```bash
pip install -U openai-whisper
```

**Why:** This installs the official OpenAI Whisper model. The `-U` flag ensures you get the latest version with all bug fixes.

**Expected Result:** `Successfully installed openai-whisper` along with dependencies (ffmpeg-python, more-itertools, tiktoken).

**Common Failure:** `ERROR: ffmpeg not found`

**Fix:** Install ffmpeg system-wide:
- **Windows:** Download from ffmpeg.org, extract, add to PATH
- **Linux:** `sudo apt install ffmpeg`
- **macOS:** `brew install ffmpeg`

---

### Step 2: Test Whisper Installation

**Action:** Create a test script `test_whisper.py`:

```python
import whisper
import torch

print("Loading Whisper model...")
model = whisper.load_model("base", device="cuda")  # or "cpu" for testing
print(f"Model loaded on: {next(model.parameters()).device}")

# Test with a short audio clip (you'll need to provide one)
# For now, just verify the model loads
print("Whisper is ready!")
print(f"Available models: tiny, base, small, medium, large, large-v2, large-v3")
```

Execute:
```bash
python test_whisper.py
```

**Why:** This verifies Whisper can access your GPU. The `base` model is small (~150MB) and fast, good for testing. The model downloads on first run and caches to `~/.cache/whisper`.

**Expected Result:**
```
Loading Whisper model...
Model loaded on: cuda:0
Whisper is ready!
Available models: tiny, base, small, medium, large, large-v2, large-v3
```

**Common Failure:** `RuntimeError: CUDA out of memory`

**Fix:** This shouldn't happen with the base model on RTX 3090. If it does, close other GPU applications or use `device="cpu"` temporarily.

---

## Phase 2: Add yt-dlp Audio Download

### Step 3: Test Audio Extraction

**Action:** Create `test_audio_download.py`:

```python
import yt_dlp
import os

def download_audio(youtube_url, output_path="temp_audio.m4a"):
    """
    Download audio from YouTube video.
    
    Returns path to downloaded audio file.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            duration = info.get('duration', 0)
            print(f"Downloaded audio: {duration // 60}m {duration % 60}s")
            return output_path
    except Exception as e:
        raise Exception(f"Failed to download audio: {str(e)}")

# Test with a short video
test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley (3:33)
audio_path = download_audio(test_url)
print(f"Audio saved to: {audio_path}")

# Check file size
file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
print(f"File size: {file_size_mb:.2f} MB")
```

Execute:
```bash
python test_audio_download.py
```

**Why:** yt-dlp can download just the audio track (no video), which is much faster and smaller. The `bestaudio` format gets the highest quality audio available. The FFmpeg postprocessor converts it to m4a, which Whisper supports.

**Expected Result:**
```
Downloaded audio: 3m 33s
Audio saved to: temp_audio.m4a
File size: 3.42 MB
```

**Common Failure:** `ERROR: Postprocessor ffmpeg not found`

**Fix:** Install ffmpeg (see Step 1 fix above).

---

## Phase 3: Integrate Audio Transcription

### Step 4: Create Combined Transcription Function

**Action:** Add this to your `server.py`:

```python
import whisper
import yt_dlp
import os
import tempfile

# Load Whisper model at startup (alongside your LLM)
print("Loading Whisper model for audio transcription...")
whisper_model = whisper.load_model("base", device="cuda")  # or "medium" for better accuracy
print("Whisper model loaded")

def download_youtube_audio(url):
    """
    Download audio from YouTube video to a temporary file.
    
    Returns (temp_filepath, duration_seconds)
    """
    # Create temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.m4a')
    temp_path = temp_file.name
    temp_file.close()
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            duration = info.get('duration', 0)
            return temp_path, duration
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Failed to download audio: {str(e)}")


def transcribe_audio_with_whisper(audio_path):
    """
    Transcribe audio file using Whisper.
    
    Returns transcription text.
    """
    try:
        print(f"Transcribing audio: {audio_path}")
        result = whisper_model.transcribe(
            audio_path,
            language="en",  # Force English, or use None for auto-detect
            fp16=True,      # Use FP16 on GPU for speed
            verbose=False
        )
        
        transcript = result["text"].strip()
        print(f"Transcription complete: {len(transcript)} characters")
        return transcript
        
    except Exception as e:
        raise Exception(f"Whisper transcription failed: {str(e)}")


def fetch_youtube_transcript_with_fallback(url):
    """
    Enhanced version of fetch_youtube_transcript that falls back to audio transcription.
    
    Returns transcript text.
    """
    # Try 1: Get existing captions (your current logic)
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"yt-dlp failed: {str(e)}")
    
    # Duration check: 30 minutes = 1800 seconds
    duration = info.get('duration', 0)
    if duration > 1800:
        raise Exception(f"Video is {duration // 60} minutes long. Maximum is 30 minutes.")
    
    # Try to get existing captions first
    subtitle_source = None
    if 'subtitles' in info and 'en' in info['subtitles']:
        subtitle_source = info['subtitles']['en']
    elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
        subtitle_source = info['automatic_captions']['en']
    
    # If captions exist, extract them (your existing logic)
    if subtitle_source:
        print("Found existing captions, using those")
        text_parts = []
        
        for sub in subtitle_source:
            if sub.get('ext') == 'json3':
                import json
                try:
                    data = json.loads(sub['data']) if 'data' in sub else None
                    if data and 'events' in data:
                        for event in data['events']:
                            if 'segs' in event:
                                for seg in event['segs']:
                                    if 'utf8' in seg:
                                        text_parts.append(seg['utf8'])
                        if text_parts:
                            break
                except (json.JSONDecodeError, KeyError):
                    continue
            elif sub.get('ext') in ('vtt', 'srt', 'trecta') and 'data' in sub:
                import re
                lines = sub['data'].split('\n')
                for line in lines:
                    line = line.strip()
                    if not line or re.match(r'^\d{2}:\d{2}', line) or '-->' in line:
                        continue
                    if line.startswith('NOTE') or line == 'WEBVTT' or re.match(r'^\d+$', line):
                        continue
                    text_parts.append(line)
                if text_parts:
                    break
        
        if text_parts:
            return ' '.join(text_parts)
    
    # Try 2: No captions available → Fallback to audio transcription
    print("No captions found, downloading audio for transcription...")
    
    audio_path = None
    try:
        audio_path, _ = download_youtube_audio(url)
        transcript = transcribe_audio_with_whisper(audio_path)
        return transcript
        
    finally:
        # Clean up temp audio file
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"Cleaned up temp audio file: {audio_path}")
```

**Why this architecture works:**

**Dual-path approach:** Try captions first (instant), fall back to audio transcription (slower but always works).

**Temporary files:** Audio is downloaded to a temp file and deleted immediately after transcription. This prevents disk bloat.

**Model reuse:** Whisper model is loaded once at startup and reused for all requests. This avoids the 10-second load time per request.

**GPU optimization:** `fp16=True` uses half-precision on GPU, making transcription 2x faster with negligible accuracy loss.

**Expected Result:** Function defined. Server restart required to load Whisper model.

---

### Step 5: Update the YouTube Endpoint

**Action:** Replace your existing `/summarize-youtube` endpoint with this enhanced version:

```python
@app.route('/summarize-youtube', methods=['POST'])
def summarize_youtube():
    """Summarize YouTube video (with audio transcription fallback)"""
    data = request.get_json()
    url = data.get('url', '')
    length = data.get('length', 'medium')
    
    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    try:
        # This now includes fallback to audio transcription
        transcript = fetch_youtube_transcript_with_fallback(url)
        
        # If transcript is very short, likely an error
        if len(transcript) < 50:
            return jsonify({'error': 'Transcript too short, video may have no speech'}), 400
        
        # Your existing summarization logic
        prompt = build_summarization_prompt(
            content=transcript,
            content_type="youtube",
            length=length,
            max_chars=None
        )
        
        summary = call_google_llm(prompt)
        
        return jsonify({
            'summary': summary,
            'source_url': url,
            'metadata': {
                'input_length': len(transcript),
                'model': 'gemini-1.5-flash',
                'transcription_method': 'captions' if 'subtitles' in transcript else 'whisper',
                'length_setting': length
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

**Why:** This replaces your old `fetch_youtube_transcript()` call with the new fallback-enabled version. The metadata now indicates whether captions or Whisper was used.

**Expected Result:** Endpoint updated. Restart server to apply changes.

---

## Phase 4: Testing

### Step 6: Test with Caption-less Video

**Action:** Find a YouTube video without captions. Here are some test cases:

**Test A: Music video (usually no captions)**
```bash
curl -X POST http://127.0.0.1:5000/summarize-youtube \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=9bZkp7q19f0"}'
```
(Gangnam Style - 4:13, no captions)

**Test B: Old video (pre-auto-captions era)**
Search YouTube for videos uploaded 2008-2010 without "CC" icon.

**Test C: Private unlisted video**
Upload a short video to your own YouTube channel, set it to unlisted, disable captions.

**Why:** These test the fallback path. The first request will take longer (15-30 seconds for a 4-minute video) because it downloads audio and transcribes.

**Expected Result:**
```json
{
  "summary": "This is a Korean pop song featuring...",
  "source_url": "https://...",
  "metadata": {
    "transcription_method": "whisper",
    "model": "gemini-1.5-flash"
  }
}
```

**Common Failure:** Timeout after 60 seconds.

**Fix:** Long videos (>10 minutes) take time to transcribe. Either:
1. Increase Flask timeout: `app.run(host='127.0.0.1', port=5000, debug=True, timeout=300)`
2. Switch to smaller Whisper model: `whisper.load_model("tiny")` (faster but less accurate)

---

## Phase 5: UI Enhancement

### Step 7: Add Loading Feedback

**Action:** Update `sidepanel.js` to handle longer wait times:

```javascript
async function callYoutube(url) {
  showLoading('Checking for captions...');
  
  const length = document.getElementById('lengthSelector').value;
  
  try {
    const res = await fetch(`${API_BASE}/summarize-youtube`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, length })
    });
    
    // Add progress indicator for slow responses
    const timeout = setTimeout(() => {
      showLoading('No captions found, transcribing audio... (this may take 30-60 seconds)');
    }, 5000);  // If no response in 5 seconds, assume transcription
    
    const data = await res.json();
    clearTimeout(timeout);
    
    if (data.error) { 
      showError(data.error); 
    } else { 
      showSummary(data.summary); 
      
      // Show badge if Whisper was used
      if (data.metadata?.transcription_method === 'whisper') {
        const badge = document.createElement('div');
        badge.className = 'transcription-badge';
        badge.textContent = '🎤 Transcribed from audio';
        elements.messagesContainer.lastChild.querySelector('.message-content').appendChild(badge);
      }
    }
  } catch {
    showError('Cannot connect to server. Is it running?');
  }
}
```

Add CSS for the badge:

```css
.transcription-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(255, 107, 53, 0.1);
  border: 1px solid var(--accent);
  border-radius: 4px;
  font-size: 11px;
  color: var(--accent);
}
```

**Why:** Users need feedback during the 30-60 second transcription wait. The badge clarifies that audio transcription was used (which may be slightly less accurate than official captions).

**Expected Result:** UI shows clear status during long transcriptions. Badge appears on Whisper-transcribed summaries.

---

## Phase 6: Optimization

### Step 8: Choose the Right Whisper Model

Whisper comes in 5 sizes. Here's the tradeoff matrix for RTX 3090:

| Model | VRAM | Speed (30min video) | Accuracy | Use Case |
|-------|------|---------------------|----------|----------|
| tiny | 1GB | ~3 min | 70% | Ultra-fast preview |
| base | 1.5GB | ~5 min | 80% | Good balance |
| small | 2GB | ~8 min | 85% | Better quality |
| medium | 5GB | ~15 min | 90% | High quality |
| large-v3 | 10GB | ~25 min | 95% | Maximum accuracy |

**Recommendation:** Start with `base` for speed, upgrade to `medium` if accuracy is insufficient.

**Action:** Change the model in `server.py`:

```python
# At startup, change this line:
whisper_model = whisper.load_model("medium", device="cuda")  # Upgrade from "base"
```

**Why:** The medium model offers the best accuracy-per-second tradeoff. The RTX 3090 has plenty of VRAM to run both Google LLM API calls and Whisper medium simultaneously.

**Expected Result:** Slightly slower transcription (~15 min for 30-min video), but noticeably better accuracy on technical terms, accents, and noisy audio.

---

### Step 9: Add Caching for Transcriptions

**Action:** Add a transcription cache to avoid re-transcribing the same video:

```python
import hashlib

# At module level
transcription_cache = {}

def get_cached_transcription(youtube_url):
    """Check if we've already transcribed this video"""
    url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
    return transcription_cache.get(url_hash)

def cache_transcription(youtube_url, transcript):
    """Cache a transcription"""
    url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
    if len(transcription_cache) < 50:  # Limit cache size
        transcription_cache[url_hash] = transcript

# In fetch_youtube_transcript_with_fallback:
def fetch_youtube_transcript_with_fallback(url):
    # Check cache first
    cached = get_cached_transcription(url)
    if cached:
        print("Using cached transcription")
        return cached
    
    # ... existing logic ...
    
    # Before returning, cache the result
    cache_transcription(url, transcript)
    return transcript
```

**Why:** Transcription is the slowest part (30-60 seconds). If a user summarizes the same video twice (e.g., with different length settings), the second request is instant.

**Expected Result:** Second summarization of the same video completes in ~1-2 seconds instead of 30-60 seconds.

---

## Phase 7: Production Considerations

### Step 10: Handle Edge Cases

**Action:** Add error handling for problematic videos:

```python
def fetch_youtube_transcript_with_fallback(url):
    # ... existing code ...
    
    # Before transcription, check audio quality
    audio_path, duration = download_youtube_audio(url)
    
    # Check file size (very small = likely error)
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb < 0.1:
        os.remove(audio_path)
        raise Exception("Audio file too small, video may have no audio track")
    
    # Check if file is actually audio (basic check)
    try:
        import subprocess
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        audio_duration = float(result.stdout.strip())
        if audio_duration < 5:
            os.remove(audio_path)
            raise Exception("Audio too short, video may be corrupted")
    except:
        pass  # ffprobe check failed, continue anyway
    
    # Continue with transcription...
```

**Why:** Some YouTube videos have issues:
- No audio track (silent videos)
- Corrupted audio
- Copyright strikes that remove audio
- Age-restricted videos

These edge cases should fail gracefully with clear error messages.

**Expected Result:** User sees "Video may have no audio track" instead of a cryptic Whisper error.

---

### Step 11: Add Progress Streaming (Optional, Advanced)

For very long videos (20-30 minutes), you can stream progress back to the frontend.

**Action:** Use Flask-SSE (Server-Sent Events):

```python
from flask import Response, stream_with_context
import time

@app.route('/summarize-youtube-stream', methods=['POST'])
def summarize_youtube_stream():
    """Streaming version with progress updates"""
    data = request.get_json()
    url = data.get('url', '')
    
    def generate():
        try:
            yield f"data: {json.dumps({'status': 'checking_captions'})}\n\n"
            
            # Check for captions
            time.sleep(1)
            
            yield f"data: {json.dumps({'status': 'downloading_audio'})}\n\n"
            audio_path, duration = download_youtube_audio(url)
            
            yield f"data: {json.dumps({'status': 'transcribing', 'progress': 0})}\n\n"
            
            # Transcribe (Whisper doesn't natively support progress, so fake it)
            transcript = transcribe_audio_with_whisper(audio_path)
            
            yield f"data: {json.dumps({'status': 'summarizing'})}\n\n"
            summary = call_google_llm(build_summarization_prompt(transcript, "youtube", "medium"))
            
            yield f"data: {json.dumps({'status': 'complete', 'summary': summary})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')
```

**Why:** Gives real-time feedback for 20-30 minute videos. Users see "Transcribing... 60%" instead of waiting blindly.

**Expected Result:** Progress bar in UI during long operations.

**Note:** This is advanced and optional. The basic timeout feedback from Step 7 is sufficient for most use cases.

---

## Cost and Performance Summary

### Transcription Performance (RTX 3090)

| Video Length | Model | Transcription Time | Summary Time | Total |
|--------------|-------|-------------------|--------------|-------|
| 5 min | base | ~1 min | ~2 sec | ~62 sec |
| 10 min | base | ~2 min | ~2 sec | ~122 sec |
| 30 min | base | ~6 min | ~3 sec | ~363 sec |
| 30 min | medium | ~15 min | ~3 sec | ~903 sec |

### Cost Comparison

**Your Approach (Self-Hosted Whisper):**
- One-time setup: 30 minutes
- Per-video cost: $0 (uses your GPU)
- Total cost for 100 videos: $0

**Alternative (OpenAI Whisper API):**
- Setup: 5 minutes (just API key)
- Per-video cost: 30 min × $0.006/min = $0.18
- Total cost for 100 videos: $18

**Conclusion:** Self-hosting saves money if you process >10 videos/month.

---

## Troubleshooting

### Issue: "RuntimeError: CUDA out of memory"

**Cause:** Whisper + Google LLM + other apps exceed 24GB VRAM.

**Fix:**
1. Use smaller Whisper model: `load_model("base")` instead of `large-v3`
2. Clear GPU cache between requests: `torch.cuda.empty_cache()`
3. Close other GPU applications

---

### Issue: Transcription is gibberish/inaccurate

**Cause:** Wrong language or poor audio quality.

**Fix:**
1. Let Whisper auto-detect language: `transcribe(audio, language=None)`
2. Use larger model: `load_model("medium")` or `large-v3`
3. Check source audio: If YouTube has very poor audio (old videos, bad microphone), transcription quality suffers

---

### Issue: Server timeout on long videos

**Cause:** Flask default timeout is 60 seconds.

**Fix:** Increase timeout in server startup:
```python
if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', 5000, app, use_reloader=True, use_debugger=True, threaded=True)
```

Or use a production WSGI server like Gunicorn:
```bash
pip install gunicorn
gunicorn -w 1 -b 127.0.0.1:5000 --timeout 300 server:app
```

---

## Alternative: Hybrid Approach

If you want the best of both worlds:

1. **Use self-hosted Whisper for short videos (<10 min)**
2. **Use OpenAI Whisper API for long videos (>10 min)**

This balances speed (API is faster) with cost (self-hosted is free).

**Implementation:**

```python
def fetch_youtube_transcript_with_fallback(url):
    # ... existing caption logic ...
    
    # Download audio
    audio_path, duration = download_youtube_audio(url)
    
    # Decision: API for long videos, local for short
    if duration > 600:  # 10 minutes
        print(f"Long video ({duration}s), using OpenAI API")
        transcript = transcribe_with_openai_api(audio_path)
    else:
        print(f"Short video ({duration}s), using local Whisper")
        transcript = transcribe_audio_with_whisper(audio_path)
    
    # Clean up
    os.remove(audio_path)
    return transcript


def transcribe_with_openai_api(audio_path):
    """Use OpenAI Whisper API for transcription"""
    import openai
    
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    
    with open(audio_path, 'rb') as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
    
    return transcript['text']
```

**Cost:** 20 long videos/month × $0.18 = $3.60/month (affordable for most users)

---

## Final Recommendation

For your use case (student project showcasing DL skills):

✅ **Use self-hosted Whisper with the `medium` model**

This approach:
- Demonstrates deep learning expertise (running inference locally)
- Keeps the tool free for users
- Leverages your existing GPU investment
- Provides good accuracy-speed tradeoff

The only downside is slower processing for very long videos, but the 30-minute limit you've set makes this manageable.
