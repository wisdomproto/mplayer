"""Import the reviewed 1980s / 1990s / 2000s ballad selection."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

import app
from import_collection import import_source


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    songs = json.loads((Path(__file__).parent / 'ballads_catalog.json').read_text(encoding='utf-8'))
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(import_source, song): song for song in songs}
        for future in as_completed(futures):
            song = futures[future]
            try:
                result = future.result()
                result['decade'] = song['decade']
                result['artist'] = song['artist']
                results.append(result)
            except Exception as exc:
                errors.append({'title':song['title'], 'artist':song['artist'], 'id':song['id'], 'error':str(exc)})
                print('ERROR '+song['artist']+' '+song['title']+' '+str(exc),flush=True)
    report = {'sources':results, 'errors':errors,
              'classification':'원곡 발표 연대 기준. 원곡 가수의 재발매·리마스터 음원이 포함될 수 있음.'}
    (app.DATA/'ballads-import.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('COMPLETE '+json.dumps({'added':sum(s['count'] for s in results),'errors':errors}),flush=True)
    if errors: raise SystemExit(1)
