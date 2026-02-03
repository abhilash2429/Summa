import os
import hashlib
import requests
import re
import json
import time
from flask import Flask, request, jsonify
from urllib.parse import urlparse
from datetime import datetime
from flask_cors import CORS
from bs4 import BeautifulSoup
import yt_dlp
from dotenv import load_dotenv
import google.generativeai as genai

# ─── Load environment variables ──────────────────────────────
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in .env file")

# ─── Configure Gemini ────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')
print("Gemini API configured (gemini-flash-latest)")

# ─── App and CORS ────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ─── Summarization Prompts by Length ─────────────────────────
LENGTH_INSTRUCTIONS = {
    'S': 'Be extremely concise. Maximum 2-3 sentences total. Only the absolute core insight.',
    'M': 'Be concise but complete. 1 short paragraph (4-6 sentences). Cover main points briefly.',
    'L': 'Be thorough. 2-3 paragraphs. Include key details and supporting points.',
    'XL': 'Be comprehensive. 4-5 paragraphs. Include context, details, examples, and nuances.'
}

SYSTEM_PROMPT = """You are a summarization engine. Not a chatbot.
Output ONLY in this exact JSON format, no deviations:

{
  "heading": "[compelling title, max 8 words, captures the essence]",
  "summary": "[main summary text with **bold** for key terms]",
  "highlights": ["keyword1", "keyword2", "keyword3"]
}

Rules:
- Output ONLY valid JSON, nothing else
- Use **double asterisks** to bold important terms in the summary
- highlights array: 3-7 key terms that are most important
- heading: should be engaging and descriptive, not generic
- No meta commentary, disclaimers, or source references
- Compress aggressively without hallucinating
"""

# ─── Caching layer ───────────────────────────────────────────
_summary_cache = {}

def gemini_summarize(text, length='M'):
    """Call Gemini API to generate structured summary."""
    cache_key = hashlib.md5((text + length).encode()).hexdigest()
    if cache_key in _summary_cache:
        return _summary_cache[cache_key]
    
    # Truncate very long texts (Gemini has 1M context but we want speed)
    if len(text) > 30000:
        text = text[:30000] + "..."
    
    length_instruction = LENGTH_INSTRUCTIONS.get(length, LENGTH_INSTRUCTIONS['M'])
    prompt = f"{SYSTEM_PROMPT}\n\nLength instruction: {length_instruction}\n\nContent to summarize:\n{text}"
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if raw_text.startswith('```'):
            raw_text = re.sub(r'^```json?\n?', '', raw_text)
            raw_text = re.sub(r'\n?```$', '', raw_text)
        
        summary_data = json.loads(raw_text)
        
        # Cache it
        if len(_summary_cache) < 100:
            _summary_cache[cache_key] = summary_data
        
        return summary_data
    except json.JSONDecodeError:
        # Fallback: return raw text as summary
        return {
            "heading": "Summary",
            "summary": raw_text,
            "highlights": []
        }
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

# ─── YouTube transcript extraction ───────────────────────────
def fetch_youtube_transcript(url):
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
    elif 'automatic_captions' in info and 'en' in info.get('automatic_captions', {}):
        subtitle_source = info['automatic_captions']['en']

    if not subtitle_source:
        raise Exception("No English captions found. Video needs manual or auto-generated English subtitles.")

    # Find a subtitle URL and fetch it
    sub_url = None
    for sub in subtitle_source:
        if sub.get('ext') in ('vtt', 'srv1', 'srv2', 'srv3', 'json3'):
            sub_url = sub.get('url')
            break
    
    if not sub_url:
        raise Exception("Could not find subtitle URL.")

    # Fetch and parse subtitles
    try:
        sub_response = requests.get(sub_url, timeout=15)
        sub_content = sub_response.text
    except Exception as e:
        raise Exception(f"Failed to fetch subtitles: {str(e)}")

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

    if not text_parts:
        raise Exception("Captions exist but contain no extractable text.")

    return ' '.join(text_parts)

# ─── API Endpoints ───────────────────────────────────────────

@app.route('/summarize', methods=['POST'])
def summarize_text():
    data = request.get_json()
    text = data.get('text', '')
    length = data.get('length', 'M')
    
    if not text or len(text.strip()) < 20:
        return jsonify({'error': 'Text must be at least 20 characters'}), 400
    try:
        structured_data = gemini_summarize(text, length)
        response = format_summary_response(structured_data)
        
        return jsonify({
            **response,
            'metadata': {
                'input_length': len(text),
                'word_count': len(text.split()),
                'length': length,
                'timestamp': time.time(),
                'model': 'gemini-flash-latest'
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
        structured_data = gemini_summarize(text, length)
        response = format_summary_response(structured_data)
        citation = generate_citation(url, response.get('summary', ''))
        
        return jsonify({
            **response,
            'citation': citation,
            'metadata': {
                'source': url,
                'length': length,
                'timestamp': time.time(),
                'model': 'gemini-flash-latest'
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
        transcript = fetch_youtube_transcript(url)
        structured_data = gemini_summarize(transcript, length)
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
                'model': 'gemini-flash-latest'
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
        prompt = f"""You are a helpful assistant answering follow-up questions about a summary.

Original Summary:
{context}

Conversation History:
"""
        for msg in history[-4:]:
            role_label = "User" if msg['role'] == 'user' else "Assistant"
            prompt += f"{role_label}: {msg['content']}\n"
        
        prompt += f"\nUser: {question}\nAssistant:"
        
        response = model.generate_content(prompt)
        answer = response.text
        
        return jsonify({'answer': answer})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': 'gemini-flash-latest',
        'backend': 'Gemini API'
    })

# ─── Run ──────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
