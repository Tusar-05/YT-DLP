#!/usr/bin/env python3
"""
YT-DLP Local Backend Server
Runs locally on your machine for privacy-focused downloads

Usage:
    pip install flask yt_dlp
    python backend.py

This uses your local yt-dlp executable for all downloads.
Files download to ~/Downloads automatically.
"""

from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
from pathlib import Path
import subprocess

app = Flask(__name__)

# Configuration
DOWNLOAD_DIR = str(Path.home() / "Downloads")

@app.route('/api/extract', methods=['POST'])
def extract_info():
    """Extract video info and stream URLs"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get all formats
            formats = []
            if 'formats' in info:
                for fmt in info['formats']:
                    formats.append({
                        'url': fmt.get('url'),
                        'itag': fmt.get('itag', 'N/A'),
                        'resolution': fmt.get('resolution', 'Unknown'),
                        'quality_label': fmt.get('quality_label', ''),
                        'fps': fmt.get('fps', 0),
                        'vcodec': fmt.get('vcodec', 'unknown'),
                        'acodec': fmt.get('acodec', 'unknown'),
                        'filesize': fmt.get('filesize')
                    })
            
            return jsonify({
                'title': info.get('title', 'Unknown Video'),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'formats': formats,
                'description': info.get('description', '')
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subtitles/<video_id>', methods=['GET'])
def get_subtitles(video_id):
    """Get subtitle URLs for a video"""
    try:
        url = f'https://www.youtube.com/watch?v={video_id}'
        
        ydl_opts = {'writesubtitles': True, 'writeautomaticsub': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            subs = {}
            if 'subtitles' in info:
                for lang, subtitles in info['subtitles'].items():
                    subs[lang] = [s.get('url') for s in subtitles if s.get('url')]
            
            return jsonify({video_id: subs})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/video-status', methods=['GET'])
def video_status():
    """Check server status"""
    return jsonify({
        'status': 'running',
        'download_dir': DOWNLOAD_DIR,
        'yt_dlp_version': yt_dlp.__version__
    })

if __name__ == '__main__':
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"YT-DLP Local Backend starting...")
    print(f"Download directory: {DOWNLOAD_DIR}")
    print("Extension will connect to http://localhost:8000")
    app.run(host='localhost', port=8000, debug=False)
