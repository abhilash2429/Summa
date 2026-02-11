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


load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in .env file")


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')
print("Gemini API configured (gemini-2.5-flash-lite)")


print("Loading Whisper model for audio transcription...")
WHISPER_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
whisper_model = whisper.load_model("base", device=WHISPER_DEVICE)
print(f"Whisper model loaded on: {WHISPER_DEVICE}")


app = Flask(__name__)
CORS(app)



SUMMARY_SYSTEM_PROMPT = """You are a precise summarization engine.
Follow the user instructions in <instructions> exactly.
Never mention sponsors/ads/promos or that they were skipped or ignored.
Do not output sponsor/ad/promo language or brand names (for example Squarespace) or CTA phrases (for example discount code).
If the instructions include [slide:N] markers, you must output those markers exactly on their own lines and never output "Slide X" / "Slide X/Y" label lines.
Never output the literal strings "Title:" or "Headline:" anywhere; use Markdown heading syntax (## Heading) instead.
Quotation marks are allowed; use straight quotes only (no curly quotes).
If you include exact excerpts, italicize them in Markdown using single asterisks.
Include 1-2 short exact excerpts (max 25 words each) when the content provides a strong, non-sponsor line.
Never include ad/sponsor/boilerplate excerpts."""

# Summary length specifications (from summary-lengths.ts)
SUMMARY_LENGTH_SPECS = {
    'short': {
        'guidance': 'Write a tight summary that delivers the primary claim plus one high-signal supporting detail.',
        'formatting': 'Use 1-2 short paragraphs (a single paragraph is fine). Aim for 2-5 sentences total.',
        'target_characters': 900,
        'min_characters': 600,
        'max_characters': 1200,
        'max_tokens': 768,
    },
    'medium': {
        'guidance': 'Write a clear summary that covers the core claim plus the most important supporting evidence or data points.',
        'formatting': 'Use 1-3 short paragraphs (2 is typical, but a single paragraph is okay if the content is simple). Aim for 2-3 sentences per paragraph.',
        'target_characters': 1800,
        'min_characters': 1200,
        'max_characters': 2500,
        'max_tokens': 1536,
    },
    'long': {
        'guidance': 'Write a detailed summary that prioritizes the most important points first, followed by key supporting facts or events, then secondary details or conclusions stated in the source.',
        'formatting': 'Paragraphs are optional; use up to 3 short paragraphs. Aim for 2-4 sentences per paragraph when you split into paragraphs.',
        'target_characters': 4200,
        'min_characters': 2500,
        'max_characters': 6000,
        'max_tokens': 3072,
    },
    'xl': {
        'guidance': 'Write a detailed summary that captures the main points, supporting facts, and concrete numbers or quotes when present.',
        'formatting': 'Use 2-5 short paragraphs. Aim for 2-4 sentences per paragraph.',
        'target_characters': 9000,
        'min_characters': 6000,
        'max_characters': 14000,
        'max_tokens': 6144,
    },
    'xxl': {
        'guidance': 'Write a comprehensive summary that covers background, main points, evidence, and stated outcomes in the source text; avoid adding implications or recommendations unless explicitly stated.',
        'formatting': 'Use 3-7 short paragraphs. Aim for 2-4 sentences per paragraph.',
        'target_characters': 17000,
        'min_characters': 14000,
        'max_characters': 22000,
        'max_tokens': 12288,
    },
}

# Map old length codes to new
LENGTH_MAP = {
    'S': 'short',
    'M': 'medium',
    'L': 'long',
    'XL': 'xl',
}

def format_count(value):
    """Format number with comma separators"""
    return f"{value:,}"

def build_link_summary_prompt(content, url=None, title=None, site_name=None, 
                               description=None, truncated=False, 
                               has_transcript=False, content_type='text', 
                               summary_length='medium'):
    """
    Build prompt for link/article/video summarization (from link-summary.ts)
    """
    content_characters = len(content)
    
    # Build context header
    context_lines = []
    if url:
        context_lines.append(f"Source URL: {url}")
    if title:
        context_lines.append(f"Page name: {title}")
    if site_name:
        context_lines.append(f"Site: {site_name}")
    if description:
        context_lines.append(f"Page description: {description}")
    if truncated:
        context_lines.append("Note: Content truncated to the first portion available.")
    
    context_header = '\n'.join(context_lines)
    
    # Determine audience line based on content type
    audience_line = (
        "You summarize online videos for curious Twitter users who want to know whether the clip is worth watching."
        if has_transcript else
        "You summarize online articles for curious Twitter users who want the gist before deciding to dive in."
    )
    
    # Get length spec
    spec = SUMMARY_LENGTH_SPECS[summary_length]
    
    # Build length guidance
    preset_length_line = (
        f"Target length: around {format_count(spec['target_characters'])} characters "
        f"(acceptable range {format_count(spec['min_characters'])}-{format_count(spec['max_characters'])}). "
        f"This is a soft guideline; prioritize clarity."
    )
    
    content_length_line = (
        f"Extracted content length: {format_count(content_characters)} characters. "
        f"Hard limit: never exceed this length. If the requested length is larger, "
        f"do not pad—finish early rather than adding filler."
        if content_characters > 0 else ""
    )
    
    # Determine if headings needed (xl, xxl, or content > 6000 chars)
    needs_headings = summary_length in ('xl', 'xxl') or content_characters >= 6000
    heading_instruction = (
        'Use Markdown headings with the "### " prefix to break sections. '
        'Include at least 3 headings and start with a heading. Do not use bold for headings.'
        if needs_headings else ''
    )
    
    # Sponsor instruction for transcripts
    sponsor_instruction = (
        "Omit sponsor messages, ads, promos, and calls-to-action (including podcast ad reads), "
        "even if they appear in the transcript or slide timeline. Do not mention or acknowledge them, "
        "and do not say you skipped or ignored anything. Avoid sponsor/ad/promo language, "
        "brand names like Squarespace, or CTA phrases like discount code. Treat them as if they do not exist."
        if has_transcript else ""
    )
    
    # Build base instructions
    base_instructions = [
        "IMPORTANT: Start your response with a concise, descriptive title using '### ' prefix. The title should be 3-8 words that capture the main topic or key insight. Do NOT just repeat the page name.",
        "Hard rules: never mention sponsor/ads; use straight quotation marks only (no curly quotes).",
        "Apostrophes in contractions are OK.",
        audience_line,
        sponsor_instruction,
        spec['guidance'],
        spec['formatting'],
        heading_instruction,
        preset_length_line,
        content_length_line,
        "Keep the response compact by avoiding blank lines between sentences or list items; use only the single newlines required by the formatting instructions.",
        "Do not use emojis, disclaimers, or speculation.",
        "Write in direct, factual language.",
        "Format the answer in Markdown and obey the length-specific formatting above.",
        "Use short paragraphs; use bullet lists only when they improve scanability; avoid rigid templates.",
        "Include 1-2 short exact excerpts (max 25 words each) formatted as Markdown italics using single asterisks when there is a strong, non-sponsor line. Use straight quotation marks (no curly) as needed. If no suitable line exists, omit excerpts. Never include ad/sponsor/boilerplate excerpts and do not mention them.",
        "Base everything strictly on the provided content and never invent details.",
        "Final check: remove any sponsor/ad references or mentions of skipping/ignoring content. Ensure excerpts (if any) are italicized and use only straight quotes.",
    ]
    
    # Filter empty lines and join
    instructions = '\n'.join([line for line in base_instructions if line.strip()])
    
    # Build tagged prompt
    return f"""<instructions>
{instructions}
</instructions>

<context>
{context_header}
</context>

<content>
{content}
</content>"""

def build_file_summary_prompt(content, filename=None, media_type=None, 
                               summary_length='medium', is_audio_video=False):
    """
    Build prompt for file summarization (from file.ts)
    NOTE: File summaries use stricter rules - NO quotation marks at all
    """
    content_characters = len(content)
    
    # Determine if we should ignore sponsors (audio/video files)
    should_ignore_sponsors = is_audio_video or (
        media_type and (media_type.startswith('audio/') or media_type.startswith('video/'))
    )
    
    # Get length spec
    spec = SUMMARY_LENGTH_SPECS[summary_length]
    
    # Build length guidance
    preset_length_line = (
        f"Target length: around {format_count(spec['target_characters'])} characters "
        f"(acceptable range {format_count(spec['min_characters'])}-{format_count(spec['max_characters'])}). "
        f"This is a soft guideline; prioritize clarity."
    )
    
    content_length_line = (
        f"Extracted content length: {format_count(content_characters)} characters. "
        f"Hard limit: never exceed this length. If the requested length is larger, "
        f"do not pad—finish early rather than adding filler."
        if content_characters > 0 else ""
    )
    
    # Build context header
    header_lines = []
    if filename:
        header_lines.append(f"Filename: {filename}")
    if media_type:
        header_lines.append(f"Media type: {media_type}")
    
    context_header = '\n'.join(header_lines)
    
    # Build base instructions - NOTE: NO quotation marks allowed for files
    base_instructions = [
        "IMPORTANT: Start your response with a concise, descriptive title using '### ' prefix. The title should be 3-8 words that capture the main topic or key insight.",
        "Hard rules: never mention sponsor/ads; never output quotation marks of any kind (straight or curly), even for titles.",
        "Never include quotation marks in the output. Apostrophes in contractions are OK. If a title or excerpt would normally use quotes, remove them and optionally italicize the text instead.",
        "You summarize files for curious users.",
        "Summarize the attached file.",
        "Be factual and do not invent details.",
        (
            "Omit sponsor messages, ads, promos, and calls-to-action (including podcast ad reads), "
            "even if they appear in the transcript. Do not mention or acknowledge them, and do not say "
            "you skipped or ignored anything. Avoid sponsor/ad/promo language, brand names like Squarespace, "
            "or CTA phrases like discount code."
            if should_ignore_sponsors else ""
        ),
        spec['guidance'],
        spec['formatting'],
        "Format the answer in Markdown.",
        "Use short paragraphs; use bullet lists only when they improve scanability; avoid rigid templates.",
        "If a standout line is present, include 1-2 short exact excerpts (max 25 words each) formatted as Markdown italics using single asterisks only. Do not use quotation marks of any kind (straight or curly). Remove any quotation marks from excerpts. If you cannot format an italic excerpt, omit it. Never include ad/sponsor/boilerplate excerpts and do not mention them.",
        "Do not use emojis.",
        preset_length_line,
        content_length_line,
        "Final check: remove any sponsor/ad references or mentions of skipping/ignoring content. Remove any quotation marks. Ensure standout excerpts are italicized; otherwise omit them.",
        "Return only the summary.",
    ]
    
    # Filter empty lines and join
    instructions = '\n'.join([line for line in base_instructions if line.strip()])
    
    # Build tagged prompt
    return f"""<instructions>
{instructions}
</instructions>

<context>
{context_header}
</context>

<content>
{content}
</content>"""

def build_summarization_prompt(content, content_type='text', length='M', 
                               url=None, title=None, site_name=None, 
                               description=None, truncated=False, filename=None,
                               media_type=None):
    """
    Main prompt builder - routes to appropriate template based on content type
    
    Args:
        content: The text/transcript/article to summarize
        content_type: Type of content ('text', 'webpage', 'youtube', 'file')
        length: Desired summary length ('S', 'M', 'L', 'XL' or 'short', 'medium', 'long', 'xl', 'xxl')
        url: Source URL (for link summaries)
        title: Page/video title
        site_name: Site name
        description: Page description
        truncated: Whether content was truncated
        filename: Filename (for file summaries)
        media_type: MIME type (for file summaries)
    """
    # Normalize length parameter
    if length in LENGTH_MAP:
        summary_length = LENGTH_MAP[length]
    else:
        summary_length = length if length in SUMMARY_LENGTH_SPECS else 'medium'
    
    # Route to appropriate builder
    if content_type == 'file':
        is_audio_video = media_type and (media_type.startswith('audio/') or media_type.startswith('video/'))
        return build_file_summary_prompt(
            content=content,
            filename=filename,
            media_type=media_type,
            summary_length=summary_length,
            is_audio_video=is_audio_video
        )
    else:
        # Use link summary for text, webpage, and youtube
        has_transcript = content_type in ('youtube', 'video')
        return build_link_summary_prompt(
            content=content,
            url=url,
            title=title,
            site_name=site_name,
            description=description,
            truncated=truncated,
            has_transcript=has_transcript,
            content_type=content_type,
            summary_length=summary_length
        )


_summary_cache = {}
_transcription_cache = {}

def extract_heading_from_markdown(text):
    """Extract first heading from markdown text (### or ##), or generate a default."""
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('### '):
            return line[4:].strip()
        if line.startswith('## '):
            return line[3:].strip()
        if line.startswith('# '):
            return line[2:].strip()
    
    
    first_line = lines[0] if lines else text[:100]
    # Remove any markdown formatting from first line
    first_line = re.sub(r'^#+\s*', '', first_line)
    first_line = re.sub(r'\*\*(.+?)\*\*', r'\1', first_line)
    first_line = first_line.strip()
    
    
    if len(first_line) > 80:
        first_line = first_line[:77] + '...'
    
    return first_line if first_line else 'Summary'

def get_summary_cache_key(content, length):
    """Generate cache key for summary."""
    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    return f"{content_hash}_{length}"

def cache_summary(key, summary):
    """Store summary in cache."""
    _summary_cache[key] = summary

def get_cached_summary(key):
    """Retrieve cached summary if exists."""
    return _summary_cache.get(key)

def cache_transcription(url, transcript):
    """Cache transcription for a URL."""
    _transcription_cache[url] = transcript
    print(f"Cached transcription for {url}")

def get_cached_transcription(url):
    """Get cached transcription if exists."""
    return _transcription_cache.get(url)

def gemini_summarize(text, length='M', content_type='text', url=None, title=None, 
                     site_name=None, description=None, truncated=False):
    """
    Generate summary using Gemini API with exact prompting structure.
    Returns structured data: {'summary': str, 'heading': str}
    """
    
    cache_key = get_summary_cache_key(text, length)
    cached = get_cached_summary(cache_key)
    if cached:
        print(f"Cache hit for summary (length={length})")
        return cached
    
    
    prompt = build_summarization_prompt(
        content=text,
        content_type=content_type,
        length=length,
        url=url,
        title=title,
        site_name=site_name,
        description=description,
        truncated=truncated
    )
    
    
    summary_length = LENGTH_MAP.get(length, length)
    if summary_length not in SUMMARY_LENGTH_SPECS:
        summary_length = 'medium'
    max_tokens = SUMMARY_LENGTH_SPECS[summary_length]['max_tokens']
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,
                'top_p': 0.9,
                'top_k': 40,
                'max_output_tokens': max_tokens,
            }
        )
        summary_text = response.text.strip()
        
        
        heading = extract_heading_from_markdown(summary_text)
        
        result = {
            'summary': summary_text,
            'heading': heading
        }
        
        
        cache_summary(cache_key, result)
        
        return result
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        raise

def format_summary_response(structured_data):
    """Format the structured summary response."""
    return {
        'summary': structured_data['summary'],
        'heading': structured_data['heading']
    }

def fetch_url_text(url):
    """Fetch and extract text from a URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
    except requests.Timeout:
        raise Exception(f"Request timed out after 15 seconds. The website may be slow or unresponsive.")
    except requests.ConnectionError:
        raise Exception(f"Could not connect to {urlparse(url).netloc}. Check your internet connection or verify the URL is correct.")
    except requests.HTTPError as e:
        if response.status_code == 403:
            raise Exception(f"Access forbidden (403). The website may block automated requests.")
        elif response.status_code == 404:
            raise Exception(f"Page not found (404). The URL may be incorrect or the page may have been removed.")
        elif response.status_code >= 500:
            raise Exception(f"Server error ({response.status_code}). The website may be experiencing issues.")
        else:
            raise Exception(f"HTTP error {response.status_code}: {str(e)}")
    except requests.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    
    try:
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script, style, nav, footer, ads
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
            tag.decompose()
        
        # Extract text
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        if len(text) < 100:
            raise ValueError("Could not extract meaningful text from URL. The page may be empty, JavaScript-rendered, or paywalled.")
        
        print(f"Successfully extracted {len(text)} characters from URL")
        return text
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise Exception(f"Failed to parse page content: {str(e)}")

def generate_citation(url, summary_text):
    """Generate a citation for the summarized content."""
    domain = urlparse(url).netloc.replace('www.', '')
    first_sentence = summary_text.split('.')[0] if summary_text else 'Summary'
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    return {
        'text': f'"{first_sentence}..." - {domain}',
        'url': url,
        'domain': domain,
        'accessed': timestamp
    }

def download_youtube_audio(url):
    """Download audio from YouTube video."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        # Critical options to bypass 403 errors
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    
    try:
        print(f"Downloading audio from YouTube: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info['id']
            audio_path = os.path.join(tempfile.gettempdir(), f"{video_id}.mp3")
            
            # Verify file was created
            if not os.path.exists(audio_path):
                raise Exception("Audio file was not created")
            
            print(f"Audio downloaded successfully: {audio_path}")
            return audio_path, info
            
    except Exception as e:
        raise Exception(f"Failed to download YouTube audio: {str(e)}")

def transcribe_audio_with_whisper(audio_path):
    """Transcribe audio file using Whisper."""
    print(f"Transcribing audio with Whisper on {WHISPER_DEVICE}...")
    result = whisper_model.transcribe(audio_path, language='en', fp16=(WHISPER_DEVICE == 'cuda'))
    transcript = result['text'].strip()
    print(f"Whisper transcription complete: {len(transcript)} characters")
    return transcript

def fetch_youtube_transcript_with_fallback(url):
    """
    Fetch YouTube transcript with intelligent fallback strategy.
    Returns: (transcript_text, method)
        method can be: 'cached', 'captions', or 'whisper'
    """
    # Check cache first
    cached = get_cached_transcription(url)
    if cached:
        print(f"Using cached transcription for {url}")
        return cached, 'cached'
    
    # Try to get captions using yt-dlp
    print(f"Attempting to extract captions for {url}...")
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'quiet': True,
        'no_warnings': True,
    }
    
    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"Failed to extract video info: {e}")
        raise Exception(f"Failed to get video information: {str(e)}")
    
    
    if info:
        duration = info.get('duration', 0)
        if duration > 1800:
            minutes = duration // 60
            raise Exception(f"Video is {minutes} minutes long. Maximum supported duration is 30 minutes.")
    
    # Check if English subtitles/captions exist
    subtitle_source = None
    if info and 'subtitles' in info and 'en' in info['subtitles']:
        subtitle_source = info['subtitles']['en']
        print("Found manual English subtitles")
    elif info and 'automatic_captions' in info and 'en' in info['automatic_captions']:
        subtitle_source = info['automatic_captions']['en']
        print("Found automatic English captions")
    else:
        print("No English subtitles or automatic captions found in video info")
    
    
    if subtitle_source:
        
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
                
                
                text_parts = []
                lines = sub_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

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
            'original_content': text,
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
        
        # Extract metadata for better prompting
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = soup.find('title')
            title = title.get_text().strip() if title else None
            
            site_name_meta = soup.find('meta', property='og:site_name')
            site_name = site_name_meta.get('content') if site_name_meta else None
            
            description_meta = soup.find('meta', {'name': 'description'}) or soup.find('meta', property='og:description')
            description = description_meta.get('content') if description_meta else None
        except:
            title = None
            site_name = None
            description = None
        
        structured_data = gemini_summarize(
            text, length, content_type='webpage',
            url=url, title=title, site_name=site_name, description=description
        )
        response = format_summary_response(structured_data)
        citation = generate_citation(url, response.get('summary', ''))
        
        return jsonify({
            **response,
            'original_content': text,
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
        # Get transcript with fallback
        transcript, transcription_method = fetch_youtube_transcript_with_fallback(url)
        
        # Check for minimum transcript length
        if len(transcript) < 50:
            return jsonify({'error': 'Transcript too short, video may have no speech content'}), 400
        
        # Extract video metadata
        try:
            ydl_opts = {'skip_download': True, 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title')
                description = info.get('description', '')[:200]  # First 200 chars
        except:
            title = None
            description = None
        
        structured_data = gemini_summarize(
            transcript, length, content_type='youtube',
            url=url, title=title, site_name='YouTube', description=description
        )
        response = format_summary_response(structured_data)
        citation = generate_citation(url, response.get('summary', ''))
        
        return jsonify({
            **response,
            'original_content': transcript,
            'citation': citation,
            'metadata': {
                'source': 'YouTube',
                'video_url': url,
                'length': length,
                'timestamp': time.time(),
                'model': 'gemini-2.5-flash-lite',
                'transcription_method': transcription_method
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/follow-up', methods=['POST'])
def follow_up_question():
    """
    Follow-up questions use both the summary and original source content
    for deeper, more accurate answers.
    """
    data = request.get_json()
    question = data.get('question', '')
    context = data.get('context', '')
    original_content = data.get('original_content', '')
    history = data.get('history', [])
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    if not context:
        return jsonify({'error': 'No context available. Summarize something first.'}), 400
    
    try:

        history_text = ""
        if history:
            recent_history = history[-4:]  # Last 2 exchanges
            for msg in recent_history:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role_label}: {msg['content']}\n\n"
        

        source_section = ""
        if original_content:

            truncated_content = original_content[:12000]
            was_truncated = len(original_content) > 12000
            source_section = f"""\n\nOriginal Source Content{' (truncated)' if was_truncated else ''}:
{truncated_content}"""
        
        prompt = f"""You are a helpful assistant answering follow-up questions about previously summarized content.

Core Rules:
- Use the summary for high-level context and the original source content for detailed answers
- If the answer exists in the original source content, provide it even if the summary omitted it
- Be concise and direct
- Never mention sponsors, ads, or promotional content
- Never use quotation marks for emphasis (apostrophes in contractions are OK)
- If the answer is not in either the summary or the original content, say so clearly
- Stay focused on the substantive content

Summary:
{context}{source_section}

Recent Conversation:
{history_text if history_text else "(No prior questions)"}

User's Question:
{question}

Provide a clear, concise answer:"""
        
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
        'backend': 'Gemini API',
        'prompt_version': 'typescript-exact-match'
    })


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
