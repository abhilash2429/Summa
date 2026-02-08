import os
import hashlib
import requests
import re
import json
import time
import tempfile
from flask import Flask, request, jsonify
from urllib.parse import urlparse
from datetime import datetime
from flask_cors import CORS
from bs4 import BeautifulSoup
import yt_dlp
from dotenv import load_dotenv
import google.generativeai as genai
import torch
import whisper

# ─── Load environment variables ──────────────────────────────
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in .env file")

# ─── Configure Gemini ────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')
print("Gemini API configured (gemini-2.5-flash-lite)")

# ─── Load Whisper for audio transcription ────────────────────
print("Loading Whisper model for audio transcription...")
WHISPER_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
whisper_model = whisper.load_model("base", device=WHISPER_DEVICE)
print(f"Whisper model loaded on: {WHISPER_DEVICE}")

# ─── App and CORS ────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ─── V3 Professional Summarization Prompts ───────────────────

SYSTEM_PROMPT = """You are a precise summarization engine designed for professional use.

Core Identity:
- You summarize content for curious users who value clarity and depth
- You are factual and never invent details
- You extract signal from noise, prioritizing substance over fluff

Hard Rules (Never Violate):
1. Never mention sponsors, ads, promotions, or calls-to-action
2. Never acknowledge that you skipped or ignored sponsor content
3. Never output sponsor language, brand names (e.g., Squarespace), or CTA phrases (e.g., "discount code")
4. Never use quotation marks of any kind (straight " or curly "")
5. Apostrophes in contractions are allowed (e.g., "don't", "it's")
6. Never output literal label text like "Title:" or "Headline:"
7. Never use emojis

Content Processing:
- Omit all sponsor messages, ad reads, promos, and promotional content entirely
- If transcript contains podcast ad reads, skip them without acknowledgment
- Focus on substantive claims, concepts, and insights
- Compress aggressively without hallucinating

Output Format:
- Use Markdown formatting
- Use ## for headings (never "Title:" labels)
- Use short paragraphs for readability
- Use bullet lists only when they improve scanability
- Use **double asterisks** to bold important terms
- Avoid rigid templates or formulaic structures

Excerpts (Optional):
- If a standout line exists, include 1-2 short exact excerpts (max 25 words each)
- Format excerpts as italics using single asterisks: *like this*
- Never use quotation marks around excerpts
- Never include ad/sponsor/boilerplate excerpts
- If you cannot format an italic excerpt properly, omit it entirely

Final Validation:
- Remove any sponsor/ad references or mentions of skipping content
- Remove all quotation marks from output
- Ensure excerpts are italicized; if not possible, remove them
- Output only the summary, no meta-commentary
"""

FOLLOWUP_SYSTEM_PROMPT = """You are a helpful assistant answering follow-up questions about previously summarized content.

Core Rules:
- Answer questions based on the original summary and content
- Be concise and direct
- Never mention sponsors, ads, or promotional content
- Never use quotation marks for emphasis (apostrophes in contractions are OK)
- If asked about something not in the summary, say so clearly
- Stay focused on the substantive content

Response Format:
- Use Markdown formatting
- Short paragraphs preferred
- Bullet lists only when they clarify the answer
- No emojis
- If referencing the original content, use italics with single asterisks

Never do:
- Invent details not in the original content
- Include sponsor/ad information even if asked
- Use quotation marks of any kind (straight or curly)
- Provide overly long responses (aim for 2-4 paragraphs max)
"""

# ─── Length Instructions ─────────────────────────────────────
LENGTH_INSTRUCTIONS = {
    'S': 'Provide a brief summary (2-3 short paragraphs maximum). Only the absolute core insight.',
    'M': 'Provide a balanced summary with key insights and supporting details (3-5 paragraphs).',
    'L': 'Provide a thorough summary covering all major points and nuances (5-7 paragraphs).',
    'XL': 'Provide a comprehensive summary covering all major points, context, details, examples, and nuances (no strict length limit, but stay concise).'
}

# ─── Content Type Guidance ───────────────────────────────────
CONTENT_TYPE_GUIDANCE = {
    'youtube': 'This is a video transcript. Focus on the main arguments and insights. Ignore any in-video sponsor segments or promotional content.',
    'webpage': 'This is web page content. Extract the core information, ignoring navigation elements, ads, and boilerplate text.',
    'text': 'This is user-provided text. Summarize the main points and key insights.'
}

def build_summarization_prompt(content, content_type='text', length='M'):
    """
    Builds a complete prompt for the summarization request.
    
    Args:
        content: The text/transcript/article to summarize
        content_type: Type of content being summarized ('text', 'webpage', 'youtube')
        length: Desired summary length ('S', 'M', 'L', 'XL')
    
    Returns:
        Complete prompt string ready for LLM
    """
    instructions = []
    
    # Length directive
    instructions.append(LENGTH_INSTRUCTIONS.get(length, LENGTH_INSTRUCTIONS['M']))
    
    # Content-type specific guidance
    if content_type in CONTENT_TYPE_GUIDANCE:
        instructions.append(CONTENT_TYPE_GUIDANCE[content_type])
    
    # Final check reminder
    instructions.append("\nFinal check before outputting:")
    instructions.append("- Remove all sponsor/ad references")
    instructions.append("- Remove all quotation marks (straight and curly)")
    instructions.append("- Verify excerpts are italicized with single asterisks")
    instructions.append("- Use ## for headings (never 'Title:' labels)")
    instructions.append("- Output only the summary, no meta-commentary")
    
    # Assemble final prompt
    prompt = f"""{SYSTEM_PROMPT}

<instructions>
{chr(10).join(instructions)}
</instructions>

<content>
{content}
</content>

Output the summary now:"""
    
    return prompt


def build_followup_prompt(question, original_summary, conversation_history=None):
    """
    Build prompt for follow-up question.
    
    Args:
        question: User's follow-up question
        original_summary: The summary that was previously generated
        conversation_history: List of {"role": "user/assistant", "content": "..."}
    """
    # Build conversation context
    history_text = ""
    if conversation_history:
        recent_history = conversation_history[-4:]  # Last 2 exchanges
        for msg in recent_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role_label}: {msg['content']}\n\n"
    
    prompt = f"""{FOLLOWUP_SYSTEM_PROMPT}

Original Summary:
{original_summary}

Recent Conversation:
{history_text if history_text else "(No prior questions)"}

User's Question:
{question}

Provide a clear, concise answer based on the summary:"""
    
    return prompt


# ─── Caching layer ───────────────────────────────────────────
_summary_cache = {}
_transcription_cache = {}  # Cache for audio transcriptions

def extract_heading_from_markdown(text):
    """Extract first ## heading from markdown text, or generate a default."""
    lines = text.strip().split('\n')
    for line in lines:
        if line.startswith('## '):
            return line[3:].strip()
    # No heading found, return first 8 words as heading
    words = text.split()[:8]
    return ' '.join(words) + '...' if len(words) == 8 else ' '.join(words)


def gemini_summarize(text, length='M', content_type='text'):
    """Call Gemini API to generate markdown summary."""
    cache_key = hashlib.md5((text + length + content_type).encode()).hexdigest()
    if cache_key in _summary_cache:
        return _summary_cache[cache_key]
    
    # Truncate very long texts (Gemini has 1M context but we want speed)
    if len(text) > 30000:
        text = text[:30000] + "..."
    
    prompt = build_summarization_prompt(text, content_type, length)
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
            }
        )
        raw_text = response.text.strip()
        
        # Extract heading from markdown
        heading = extract_heading_from_markdown(raw_text)
        
        # Remove the heading line from body if it exists
        body = raw_text
        if body.startswith('## '):
            body = '\n'.join(body.split('\n')[1:]).strip()
        
        result = {
            "heading": heading,
            "summary": body,
            "highlights": []  # Kept for backward compatibility
        }
        
        # Cache it
        if len(_summary_cache) < 100:
            _summary_cache[cache_key] = result
        
        return result
    except Exception as e:
        raise Exception(f"Gemini API error: {str(e)}")


def format_summary_response(data):
    """Format the structured data into API response."""
    return {
        'heading': data.get('heading', 'Summary'),
        'summary': data.get('summary', ''),
        'highlights': data.get('highlights', [])
    }

def generate_citation(url, summary_text):
    """Generate MLA-style citation."""
    try:
        domain = urlparse(url).netloc
        date = datetime.now().strftime("%d %b. %Y")
        snippet = summary_text.replace('\n', ' ')[:50] + "..."
        return f'"{snippet}" {domain}, {date}. Web.'
    except:
        return ""


# ─── Web page text extraction ────────────────────────────────
def fetch_url_text(url):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; SummarizBot/1.0)'}
    try:
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
    except requests.Timeout:
        raise Exception("Website took too long to respond (15s timeout)")
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch URL: {str(e)}")

    soup = BeautifulSoup(response.content, 'html.parser')
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    if not text or len(text) < 100:
        raise Exception("No meaningful text found on this page (may be paywalled or JavaScript-rendered)")
    return text

# ─── YouTube transcript extraction with Whisper fallback ─────

def download_youtube_audio(url):
    """
    Download audio from YouTube video to a temporary file.
    
    Returns (temp_filepath, duration_seconds)
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.m4a')
    temp_path = temp_file.name
    temp_file.close()
    
    # Remove extension as yt-dlp adds it
    output_template = temp_path.replace('.m4a', '')
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'quiet': True,
        'no_warnings': True,
        # Options to bypass 403 errors
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            duration = info.get('duration', 0)
            # yt-dlp may create file with slightly different name
            actual_path = output_template + '.m4a'
            if not os.path.exists(actual_path):
                actual_path = temp_path
            return actual_path, duration
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
        print(f"Transcribing audio with Whisper: {audio_path}")
        result = whisper_model.transcribe(
            audio_path,
            language="en",  # Force English
            fp16=(WHISPER_DEVICE == "cuda"),  # FP16 on GPU for speed
            verbose=False
        )
        transcript = result["text"].strip()
        print(f"Transcription complete: {len(transcript)} characters")
        return transcript
    except Exception as e:
        raise Exception(f"Whisper transcription failed: {str(e)}")


def get_cached_transcription(youtube_url):
    """Check if we've already transcribed this video."""
    url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
    return _transcription_cache.get(url_hash)


def cache_transcription(youtube_url, transcript):
    """Cache a transcription (limit to 50 entries)."""
    url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
    if len(_transcription_cache) < 50:
        _transcription_cache[url_hash] = transcript


def fetch_youtube_transcript_with_fallback(url):
    """
    Enhanced YouTube transcript extraction with Whisper audio fallback.
    
    Returns (transcript_text, method) where method is 'captions' or 'whisper'
    """
    # Check cache first
    cached = get_cached_transcription(url)
    if cached:
        print("Using cached transcription")
        return cached, 'cached'
    
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"yt-dlp failed: {str(e)}. If you see 'JS runtime' errors, ensure Deno is installed.")

    # Duration check: 30 minutes = 1800 seconds
    duration = info.get('duration', 0)
    if duration > 1800:
        raise Exception(f"Video is {duration // 60} minutes long. Maximum is 30 minutes.")

    # Try manual subtitles first (higher quality), then auto-generated
    subtitle_source = None
    if 'subtitles' in info and 'en' in info.get('subtitles', {}):
        subtitle_source = info['subtitles']['en']
        print("Found manual English subtitles")
    elif 'automatic_captions' in info and 'en' in info.get('automatic_captions', {}):
        subtitle_source = info['automatic_captions']['en']
        print("Found automatic English captions")
    else:
        print("No English subtitles or automatic captions found in video info")

    # If captions exist, extract them
    if subtitle_source:
        # Find a subtitle URL and fetch it
        sub_url = None
        for sub in subtitle_source:
            ext = sub.get('ext')
            if ext in ('vtt', 'srv1', 'srv2', 'srv3', 'json3'):
                sub_url = sub.get('url')
                print(f"Found subtitle URL with extension: {ext}")
                break
        
        if sub_url:
            try:
                print(f"Fetching subtitles from URL...")
                sub_response = requests.get(sub_url, timeout=15)
                sub_content = sub_response.text
                
                # Parse VTT/SRT content - extract just the text
                text_parts = []
                lines = sub_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # Skip timestamp lines, headers, and metadata
                    if re.match(r'^\d{2}:\d{2}', line):
                        continue
                    if line.startswith('NOTE') or line == 'WEBVTT' or '-->' in line:
                        continue
                    if re.match(r'^\d+$', line):
                        continue
                    # Remove HTML tags
                    line = re.sub(r'<[^>]+>', '', line)
                    if line:
                        text_parts.append(line)
                
                if text_parts:
                    transcript = ' '.join(text_parts)
                    print(f"Successfully extracted captions: {len(transcript)} characters")
                    cache_transcription(url, transcript)
                    return transcript, 'captions'
                else:
                    print("Captions parsed but no text extracted")
            except Exception as e:
                print(f"Caption extraction failed: {e}, falling back to audio transcription")
        else:
            print("No suitable subtitle URL found in subtitle_source")

    # No captions available or extraction failed → Fallback to audio transcription
    print("No captions found or extraction failed, downloading audio for transcription...")
    
    audio_path = None
    try:
        audio_path, _ = download_youtube_audio(url)
        
        # Verify audio file exists and has content
        if not os.path.exists(audio_path):
            raise Exception("Audio download failed - file not created")
        
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size_mb < 0.1:
            raise Exception("Audio file too small, video may have no audio track")
        
        transcript = transcribe_audio_with_whisper(audio_path)
        
        if len(transcript) < 50:
            raise Exception("Transcription too short, video may have no speech content")
        
        cache_transcription(url, transcript)
        return transcript, 'whisper'
        
    finally:
        # Clean up temp audio file
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"Cleaned up temp audio file")

# ─── API Endpoints ───────────────────────────────────────────

@app.route('/summarize', methods=['POST'])
def summarize_text():
    data = request.get_json()
    text = data.get('text', '')
    length = data.get('length', 'M')
    
    if not text or len(text.strip()) < 20:
        return jsonify({'error': 'Text must be at least 20 characters'}), 400
    try:
        structured_data = gemini_summarize(text, length, content_type='text')
        response = format_summary_response(structured_data)
        
        return jsonify({
            **response,
            'metadata': {
                'input_length': len(text),
                'word_count': len(text.split()),
                'length': length,
                'timestamp': time.time(),
                'model': 'gemini-2.5-flash-lite'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/summarize-url', methods=['POST'])
def summarize_url():
    data = request.get_json()
    url = data.get('url', '')
    length = data.get('length', 'M')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        text = fetch_url_text(url)
        structured_data = gemini_summarize(text, length, content_type='webpage')
        response = format_summary_response(structured_data)
        citation = generate_citation(url, response.get('summary', ''))
        
        return jsonify({
            **response,
            'citation': citation,
            'metadata': {
                'source': url,
                'length': length,
                'timestamp': time.time(),
                'model': 'gemini-2.5-flash-lite'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/summarize-youtube', methods=['POST'])
def summarize_youtube():
    data = request.get_json()
    url = data.get('url', '')
    length = data.get('length', 'M')
    
    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    try:
        # Now returns (transcript, method) tuple
        transcript, transcription_method = fetch_youtube_transcript_with_fallback(url)
        
        # Check for minimum transcript length
        if len(transcript) < 50:
            return jsonify({'error': 'Transcript too short, video may have no speech content'}), 400
        
        structured_data = gemini_summarize(transcript, length, content_type='youtube')
        response = format_summary_response(structured_data)
        citation = generate_citation(url, response.get('summary', ''))
        
        return jsonify({
            **response,
            'citation': citation,
            'metadata': {
                'source': 'YouTube',
                'video_url': url,
                'length': length,
                'timestamp': time.time(),
                'model': 'gemini-2.5-flash-lite',
                'transcription_method': transcription_method  # 'captions', 'whisper', or 'cached'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/follow-up', methods=['POST'])
def follow_up_question():
    data = request.get_json()
    question = data.get('question', '')
    context = data.get('context', '')
    history = data.get('history', [])
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    if not context:
        return jsonify({'error': 'No context available. Summarize something first.'}), 400
    
    try:
        prompt = build_followup_prompt(question, context, history)
        
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 1024,
            }
        )
        answer = response.text.strip()
        
        return jsonify({'answer': answer})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': 'gemini-2.5-flash-lite',
        'backend': 'Gemini API'
    })

# ─── Run ──────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
