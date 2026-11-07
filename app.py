"""Mplayer — local music library. Python 3.11+, ffmpeg, yt-dlp."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import argparse
from contextlib import contextmanager
import json
import math
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import uuid

from storage_paths import ROOT, DATA, CACHE
MEDIA = DATA / 'music'
MEDIA.mkdir(parents=True, exist_ok=True)
JOBS = {}
LOCK = threading.Lock()

@contextmanager
def db():
    c = sqlite3.connect(DATA / 'library.db', timeout=30)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()

with db() as c:
    c.execute('CREATE TABLE IF NOT EXISTS tracks (id TEXT PRIMARY KEY, title TEXT, artist TEXT, album TEXT, duration REAL, filename TEXT, source TEXT, liked INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP)')

def run(args, timeout=180):
    if Path(str(args[0])).stem.lower() == 'yt-dlp':
        args = [args[0], '--cache-dir', str(CACHE / 'yt-dlp'), *args[1:]]
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        raise ValueError(result.stderr[-1800:] or '처리하지 못했습니다.')
    return result.stdout

def metadata(path):
    info = json.loads(run(['ffprobe', '-v', 'quiet', '-show_format', '-of', 'json', str(path)]))['format']
    return float(info['duration']), {k.lower(): v for k, v in info.get('tags', {}).items()}

def add_track(path, title='', artist='이승환', album='내 음악', source=''):
    duration, tags = metadata(path)
    tid = path.stem
    with db() as c:
        c.execute('INSERT INTO tracks (id,title,artist,album,duration,filename,source) VALUES (?,?,?,?,?,?,?)',
                  (tid, title or tags.get('title') or path.stem, tags.get('artist') or artist, tags.get('album') or album, duration, path.name, source))
    return tid

def youtube_url(value):
    p = urlparse(value)
    if p.scheme != 'https' or p.hostname not in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com'):
        raise ValueError('유튜브 HTTPS 영상 주소를 입력해 주세요.')
    return value

def seconds(value):
    parts = str(value).strip().split(':')
    if len(parts) > 3: raise ValueError('시간 형식을 확인해 주세요.')
    try:
        nums = [float(x) for x in parts]
        if any(not math.isfinite(x) or x < 0 for x in nums) or any(x >= 60 for x in nums[1:]): raise ValueError()
        result = 0
        for n in nums: result = result * 60 + n
        return result
    except ValueError:
        raise ValueError('시간은 초 또는 01:23:45 형식으로 입력해 주세요.')

def split_track(payload):
    with db() as c: track = c.execute('SELECT * FROM tracks WHERE id=?', (payload.get('id'),)).fetchone()
    if not track: raise ValueError('원본 곡이 없습니다.')
    lines = payload.get('chapters', '').strip().splitlines()
    if not lines or len(lines) > 200: raise ValueError('구간을 1~200개 입력해 주세요.')
    marks = []
    for line in lines:
        match = re.fullmatch(r'\s*([\d:.]+)\s+(.+?)\s*', line)
        if not match: raise ValueError('각 줄에 시작 시간과 곡 제목을 입력해 주세요. 예: 00:00 천일동안')
        marks.append((seconds(match[1]), match[2]))
    if any(t >= track['duration'] for t, _ in marks) or any(marks[i][0] >= marks[i+1][0] for i in range(len(marks)-1)):
        raise ValueError('시작 시간은 원본 길이 안에서 오름차순이어야 합니다.')
    made = []
    paths = []
    try:
        for i, (start, title) in enumerate(marks):
            end = marks[i+1][0] if i+1 < len(marks) else track['duration']
            path = MEDIA / (uuid.uuid4().hex + '.mp3')
            paths.append(path)
            run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(start), '-i', str(MEDIA / track['filename']), '-t', str(end-start), '-map', '0:a:0', '-map_metadata', '-1', '-codec:a', 'libmp3lame', '-q:a', '2', '-metadata', 'title='+title, '-metadata', 'artist='+track['artist'], str(path)])
            made.append(add_track(path, title, track['artist'], '곡별 자르기', track['source']))
        return {'ids': made}
    except Exception:
        with db() as c: c.executemany('DELETE FROM tracks WHERE id=?', [(x,) for x in made])
        for path in paths: path.unlink(missing_ok=True)
        raise

def download_job(jid, payload):
    folder = DATA / 'downloads' / jid
    folder.mkdir(parents=True)
    try:
        with LOCK: JOBS[jid]['message'] = '유튜브에서 오디오를 가져오는 중…'
        url = youtube_url(payload['url'])
        run(['yt-dlp', '--no-playlist', '--no-warnings', '--socket-timeout', '25', '--retries', '2', '--max-filesize', '500M', '-x', '--audio-format', 'mp3', '--audio-quality', '0', '--write-info-json', '-o', str(folder / 'audio.%(ext)s'), url], timeout=600)
        path = folder / 'audio.mp3'
        if not path.exists(): raise ValueError('변환된 MP3 파일을 찾지 못했습니다.')
        info = json.loads((folder / 'audio.info.json').read_text(encoding='utf-8'))
        target = MEDIA / (uuid.uuid4().hex + '.mp3')
        shutil.move(str(path), target)
        try: tid = add_track(target, payload.get('title') or info['title'], payload.get('artist') or '이승환', 'YouTube 가져오기', url)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        chapters = info.get('chapters') or []
        with LOCK: JOBS[jid].update(status='done', message='MP3 저장 완료', track_id=tid, chapters=chapters)
    except Exception as exc:
        with LOCK: JOBS[jid].update(status='error', message=str(exc))
    finally: shutil.rmtree(folder, ignore_errors=True)

class Handler(BaseHTTPRequestHandler):
    def reply(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            p = urlparse(self.path)
            if p.path == '/api/library':
                with db() as c: rows = [dict(x) for x in c.execute('SELECT * FROM tracks ORDER BY created DESC, rowid DESC')]
                return self.reply({'tracks': rows, 'tools': {'ffmpeg': bool(shutil.which('ffmpeg')), 'yt_dlp': bool(shutil.which('yt-dlp'))}})
            if p.path == '/api/jobs':
                with LOCK: jobs = [dict(v, id=k) for k, v in JOBS.items()]
                return self.reply(jobs)
            if p.path == '/api/search':
                query = parse_qs(p.query).get('q', ['이승환 official'])[0][:150]
                info = json.loads(run(['yt-dlp', '--flat-playlist', '--dump-single-json', '--no-warnings', '--socket-timeout', '20', 'ytsearch8:'+query], timeout=75))
                return self.reply([{'title': x.get('title'), 'url': x.get('url'), 'duration': x.get('duration'), 'channel': x.get('channel'), 'video_id': x.get('id')} for x in info.get('entries', [])])
            if p.path.startswith('/media/'):
                with db() as c: row = c.execute('SELECT filename FROM tracks WHERE id=?', (p.path.split('/')[-1],)).fetchone()
                if not row: return self.reply({'error':'곡을 찾지 못했습니다.'}, 404)
                return self.send_file(MEDIA / row['filename'], True)
            name = 'index.html' if p.path == '/' else unquote(p.path.lstrip('/'))
            path = (ROOT / 'web' / name).resolve()
            if not path.is_relative_to((ROOT / 'web').resolve()) or not path.is_file(): return self.reply({'error':'Not found'},404)
            self.send_file(path)
        except Exception as exc: self.reply({'error': str(exc)}, 400)

    def send_file(self, path, ranges=False):
        size = path.stat().st_size
        start, end, code = 0, size-1, 200
        header = self.headers.get('Range')
        if ranges and header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
            if not match or not any(match.groups()): return self.reply({'error':'Invalid range'},416)
            a,b = match.groups()
            if a:
                start = int(a)
                end = min(int(b), end) if b else end
            else: start = max(0, size-int(b))
            if start > end or start >= size:
                self.send_response(416); self.send_header('Content-Range',f'bytes */{size}'); self.end_headers(); return
            code = 206
        self.send_response(code)
        self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(end-start+1))
        if ranges:
            self.send_header('Accept-Ranges','bytes')
            if code == 206: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with path.open('rb') as f:
                f.seek(start)
                remaining = end-start+1
                while remaining > 0:
                    chunk = f.read(min(65536,remaining))
                    if not chunk: break
                    self.wfile.write(chunk); remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass

    def do_POST(self):
        try:
            origin = self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host',''): return self.reply({'error':'Origin rejected'},403)
            if self.headers.get('Sec-Fetch-Site') == 'cross-site': return self.reply({'error':'Origin rejected'},403)
            length = int(self.headers.get('Content-Length',0))
            if length <= 0 or length > 512*1024*1024: return self.reply({'error':'파일은 최대 512MB까지 가능합니다.'},413)
            p = urlparse(self.path)
            if p.path == '/api/upload':
                name = parse_qs(p.query).get('name',['music.mp3'])[0]
                ext = Path(name).suffix.lower()
                if ext not in ('.mp3','.wav','.m4a','.flac','.ogg','.mp4','.webm'): raise ValueError('지원하지 않는 파일 형식입니다.')
                temp = MEDIA / (uuid.uuid4().hex + ext)
                target = MEDIA / (uuid.uuid4().hex + '.mp3')
                try:
                    with temp.open('wb') as f:
                        remaining = length
                        while remaining:
                            chunk = self.rfile.read(min(65536,remaining))
                            if not chunk: raise ValueError('업로드가 중단되었습니다.')
                            f.write(chunk); remaining -= len(chunk)
                    if ext == '.mp3': shutil.move(temp, target)
                    else: run(['ffmpeg','-nostdin','-v','error','-y','-i',str(temp),'-map','0:a:0','-codec:a','libmp3lame','-q:a','2',str(target)])
                    tid = add_track(target, Path(name).stem)
                    return self.reply({'id':tid})
                except Exception:
                    target.unlink(missing_ok=True)
                    raise
                finally: temp.unlink(missing_ok=True)
            if length > 1024*1024: return self.reply({'error':'요청이 너무 큽니다.'},413)
            payload = json.loads(self.rfile.read(length))
            if p.path == '/api/download':
                youtube_url(payload.get('url',''))
                if not shutil.which('yt-dlp') or not shutil.which('ffmpeg'): raise ValueError('yt-dlp와 ffmpeg 설치가 필요합니다.')
                with LOCK:
                    if sum(j['status']=='working' for j in JOBS.values()) >= 3: raise ValueError('진행 중인 다운로드가 끝나면 다시 시도해 주세요.')
                    jid = uuid.uuid4().hex
                    JOBS[jid] = {'status':'working','message':'다운로드 준비 중…'}
                threading.Thread(target=download_job,args=(jid,payload),daemon=True).start()
                return self.reply({'id':jid},202)
            if p.path == '/api/split': return self.reply(split_track(payload))
            if p.path == '/api/like':
                with db() as c: c.execute('UPDATE tracks SET liked=? WHERE id=?',(int(bool(payload.get('liked'))),payload.get('id')))
                return self.reply({'ok':True})
            if p.path == '/api/edit':
                title = str(payload.get('title','')).strip()
                if not title: raise ValueError('곡 제목을 입력해 주세요.')
                with db() as c: c.execute('UPDATE tracks SET title=?,artist=?,album=? WHERE id=?',(title,str(payload.get('artist','')),str(payload.get('album','')),payload.get('id')))
                return self.reply({'ok':True})
            return self.reply({'error':'Not found'},404)
        except subprocess.TimeoutExpired: self.reply({'error':'처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.'},408)
        except Exception as exc: self.reply({'error':str(exc)},400)

class LocalServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can let two processes bind the same local port.
    allow_reuse_address = os.name != 'nt'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    args = parser.parse_args()
    server = LocalServer(('127.0.0.1',args.port),Handler)
    print(f'Mplayer ready: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()
