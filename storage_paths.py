"""Shared paths: source stays in the checkout; runtime data defaults to D:."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = Path('D:/codex-data/Mplayer') if Path('D:/').is_dir() else ROOT
DATA = Path(os.environ.get('MPLAYER_DATA', RUNTIME / 'data'))
TEMP = RUNTIME / 'tmp'
CACHE = RUNTIME / 'cache'
for directory in (DATA, TEMP, CACHE):
    directory.mkdir(parents=True, exist_ok=True)
os.environ['TEMP'] = str(TEMP)
os.environ['TMP'] = str(TEMP)
os.environ['XDG_CACHE_HOME'] = str(CACHE)
