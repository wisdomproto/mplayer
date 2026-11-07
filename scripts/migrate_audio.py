"""Upload local MP3s to this owner-private Site; credentials arrive on stdin only."""
import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from urllib.parse import urlsplit

if os.name == 'nt':
    import msvcrt
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-10)
    mode = ctypes.c_ulong()
    if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ctypes.windll.kernel32.SetConsoleMode(handle, mode.value & ~4)
print('Ready for migration JSON on stdin (input is hidden).', flush=True)
config = json.loads(sys.stdin.readline())
origin = urlsplit(config['url'])
if origin.scheme != 'https' or origin.hostname != 'mplayer-wisdomproto.kil210.chatgpt.site':
    raise SystemExit('Unexpected Site origin')
token = config['token']
data = Path(config.get('data', 'D:/codex-data/Mplayer/data'))
report = Path('D:/codex-data/Mplayer/sites/audio-migration.json')
lock = threading.Lock()
started = time.time()
done, failures = [], []
library = json.loads((Path(__file__).resolve().parents[1]/'library.json').read_text(encoding='utf-8'))

def call(method, path, body=None, headers=None):
    connection = http.client.HTTPSConnection(origin.hostname, timeout=240)
    try:
        connection.request(method, path, body=body, headers={'OAI-Sites-Authorization':'Bearer '+token, **(headers or {})})
        response = connection.getresponse()
        raw = response.read()
        if response.status >= 400:
            raise RuntimeError('HTTP '+str(response.status)+': '+raw[:180].decode('utf-8',errors='replace'))
        return json.loads(raw) if raw else {}
    finally:
        connection.close()

remote = {f['id']:f['bytes'] for f in call('GET','/api/migration')['files']}

def upload(track):
    path = (data/'music'/track['filename']).resolve()
    if path.parent != (data/'music').resolve() or path.suffix != '.mp3' or path.stat().st_size != track['bytes']:
        raise RuntimeError('Local file mismatch: '+track['id'])
    if remote.get(track['id']) == track['bytes']:
        return { 'id':track['id'], 'bytes':track['bytes'], 'reused':True }
    for attempt in range(5):
        try:
            with path.open('rb') as audio:
                result = call('PUT','/api/import/'+track['id'],audio,{'Content-Type':'audio/mpeg','Content-Length':str(track['bytes'])})
            return {'id':track['id'],'bytes':track['bytes'],'reused':result.get('reused',False)}
        except Exception:
            if attempt == 4: raise
            time.sleep(min(2**attempt,15))

def save():
    state={'expected':len(library['tracks']),'completed':len(done),'bytes':sum(x['bytes'] for x in done),'elapsed_seconds':round(time.time()-started),'files':done,'errors':failures}
    temporary=report.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(report)
    print(json.dumps({k:v for k,v in state.items() if k not in ('files',)},ensure_ascii=False),flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    pending={pool.submit(upload,t):t for t in library['tracks']}
    for future in concurrent.futures.as_completed(pending):
        track=pending[future]
        try: done.append(future.result())
        except Exception as e: failures.append({'id':track['id'],'error':str(e)})
        if len(done)%10==0 or failures: save()
save()
if failures: raise SystemExit(1)
remote = {f['id']:f['bytes'] for f in call('GET','/api/migration')['files']}
assert all(remote.get(t['id'])==t['bytes'] for t in library['tracks'])
print('VERIFIED all MP3 object sizes in R2',flush=True)
