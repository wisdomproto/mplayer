"""Start the local server in the background and open the player."""
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser
from storage_paths import DATA

root = Path(__file__).resolve().parent
url = 'http://127.0.0.1:8765'

def running():
    try:
        with urllib.request.urlopen(url+'/api/library', timeout=1) as response:
            return response.status == 200
    except OSError:
        return False

if not running():
    DATA.mkdir(exist_ok=True)
    with (DATA/'server.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, str(root/'app.py')], cwd=root,
                                   stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    for _ in range(40):
        if running(): break
        if process.poll() is not None: raise SystemExit('서버 실행 실패: data/server.log를 확인하세요.')
        time.sleep(.25)
    else: raise SystemExit('서버 시작 시간 초과: data/server.log를 확인하세요.')
webbrowser.open(url)
print('Mplayer: '+url)
