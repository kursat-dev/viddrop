from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
import uuid

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

@app.route('/')
def index():
    return send_file('index.html')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")

progress_store = {}

def get_ydl_opts(quality, task_id):
    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            percent = int((downloaded / total) * 100) if total > 0 else 0
            progress_store[task_id] = {
                'status': 'downloading',
                'percent': percent,
                'speed': d.get('_speed_str', '...'),
                'eta': d.get('_eta_str', '...')
            }
        elif d['status'] == 'finished':
            progress_store[task_id] = {'status': 'processing', 'percent': 99}

    quality_map = {
        '4k':    'bestvideo[height<=2160][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best',
        '1080p': 'bestvideo[height<=1080][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best',
        '720p':  'bestvideo[height<=720][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best',
        '480p':  'bestvideo[height<=480][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best',
        '360p':  'bestvideo[height<=360][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best',
        'audio': 'bestaudio[ext=m4a]/bestaudio/best',
    }

    opts = {
        'format': quality_map.get(quality, quality_map['1080p']),
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': True,
        'noplaylist': True,
        'ffmpeg_location': FFMPEG_PATH,
        'merge_output_format': 'mp4',
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            },
            {
                'key': 'FFmpegMetadata',
            }
        ],
    }

    if quality == 'audio':
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
        opts.pop('merge_output_format', None)

    return opts


@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL gerekli'}), 400
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', 'Bilinmiyor'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', 'Bilinmiyor'),
                'view_count': info.get('view_count', 0),
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    quality = data.get('quality', '1080p')
    if not url:
        return jsonify({'error': 'URL gerekli'}), 400

    task_id = str(uuid.uuid4())
    progress_store[task_id] = {'status': 'starting', 'percent': 0}

    def run():
        try:
            opts = get_ydl_opts(quality, task_id)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if quality != 'audio':
                    filename = os.path.splitext(filename)[0] + '.mp4'
                progress_store[task_id] = {
                    'status': 'done',
                    'percent': 100,
                    'filename': os.path.basename(filename),
                    'filepath': filename
                }
        except Exception as e:
            progress_store[task_id] = {'status': 'error', 'error': str(e)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'task_id': task_id})


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    return jsonify(progress_store.get(task_id, {'status': 'not_found'}))


@app.route('/api/file/<task_id>')
def get_file(task_id):
    task = progress_store.get(task_id)
    if not task or task.get('status') != 'done':
        return jsonify({'error': 'Dosya hazır değil'}), 404
    filepath = task.get('filepath')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Dosya bulunamadı'}), 404
    return send_file(filepath, as_attachment=True)


if __name__ == '__main__':
    print("\n✅ YT Downloader başlatıldı!")
    print("🌐 Tarayıcında aç: http://localhost:5000\n")
    app.run(debug=False, port=5000)
