"""Import the curated Lee Seung Hwan collection, preserving source chapter times.

Run again safely: existing source/title pairs are verified and skipped.
Source metadata stays in data/sources; decoded MP3s replace the source audio.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import uuid

import app

SOURCES = [
    {'id': 'Km_PYtPuzBw', 'album': '이승환 · 봄에 듣는 노래 모음', 'chapters': True},
    {'id': 'W_8CDBkNcbQ', 'album': 'LIVE ON UNPLUGGED', 'chapters': True, 'live': True},
    {'id': 'smwP-6hrXSs', 'album': '이승환 · 뮤직비디오', 'title': '당부'},
    {'id': 'zCb5mwvTM84', 'album': '이승환 · 뮤직비디오', 'title': '꽃'},
    {'id': '_WggK9UUUA0', 'album': '이승환 · 뮤직비디오', 'title': '다만'},
]


def import_source(spec):
    vid = spec['id']
    artist = spec.get('artist', '이승환')
    url = 'https://www.youtube.com/watch?v=' + vid
    folder = app.DATA / 'sources' / vid
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / 'import.json'
    print('SOURCE ' + vid, flush=True)
    app.run(['yt-dlp', '--no-playlist', '--no-warnings', '--no-progress',
             '--socket-timeout', '25', '--retries', '2', '--max-filesize', '500M',
             '-f', 'bestaudio/best', '--write-info-json',
             '-o', str(folder / 'source.%(ext)s'), url], timeout=900)
    info = json.loads((folder / 'source.info.json').read_text(encoding='utf-8'))
    candidates = [p for p in folder.glob('source.*') if p.suffix.lower() in ('.m4a', '.webm', '.opus', '.mp3', '.mp4', '.ogg')]
    if len(candidates) != 1:
        raise ValueError('Expected one source audio: ' + vid)
    original = candidates[0]
    duration, _ = app.metadata(original)
    if spec.get('chapters'):
        chapters = info.get('chapters')
        if not chapters:
            raise ValueError('No verified chapter timestamps: ' + vid)
    else:
        chapters = [{'start_time': 0, 'end_time': duration, 'title': spec['title']}]
    entries = []
    for i, chapter in enumerate(chapters):
        start = float(chapter['start_time'])
        end = min(float(chapter.get('end_time') or duration), duration)
        if not 0 <= start < end or end - start < 30:
            raise ValueError('Invalid chapter: ' + repr(chapter))
        if i and start < float(chapters[i-1]['end_time']):
            raise ValueError('Overlapping chapters: ' + vid)
        title = chapter['title'].strip()
        if spec.get('live'):
            title = re.sub(r'\s*\([^)]*\)\s*$', '', title) + ' (Live on Unplugged)'
        with app.db() as c:
            existing = c.execute('SELECT * FROM tracks WHERE source=? AND title=?', (url, title)).fetchone()
        if existing and (app.MEDIA / existing['filename']).is_file():
            tid = existing['id']
            actual, _ = app.metadata(app.MEDIA / existing['filename'])
            if abs(actual - (end-start)) > 2:
                raise ValueError('Existing duration does not match: ' + title)
            print('SKIP ' + title, flush=True)
        else:
            target = app.MEDIA / (uuid.uuid4().hex + '.mp3')
            try:
                app.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(start),
                         '-i', str(original), '-t', str(end-start), '-map', '0:a:0',
                         '-map_metadata', '-1', '-codec:a', 'libmp3lame', '-q:a', '2',
                         '-id3v2_version', '3', '-metadata', 'title='+title,
                         '-metadata', 'artist='+artist, '-metadata', 'album='+spec['album'],
                         '-metadata', 'date='+str(spec.get('year', '')),
                         '-metadata', 'track='+str(i+1), '-metadata', 'comment='+url,
                         str(target)], timeout=180)
                actual, tags = app.metadata(target)
                if abs(actual-(end-start)) > .5 or tags.get('title') != title:
                    raise ValueError('Output verification failed: ' + title)
                tid = app.add_track(target, title, artist, spec['album'], url)
            except Exception:
                target.unlink(missing_ok=True)
                raise
            print('ADDED ' + title + ' | ' + str(round(actual,2)) + 's', flush=True)
        entries.append({'id': tid, 'title': title, 'artist': artist, 'year':spec.get('year'), 'start': start, 'end': end,
                        'duration': actual, 'source': url, 'album': spec['album']})
        receipt.write_text(json.dumps({'video_id':vid, 'source':url, 'source_title':info['title'],
                                      'channel':info.get('channel'), 'complete':len(entries)==len(chapters),
                                      'tracks':entries}, ensure_ascii=False, indent=2), encoding='utf-8')
    for entry in entries:
        app.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-threads', '1',
                 '-i', str(app.MEDIA/(entry['id']+'.mp3')), '-map', '0:a:0', '-f', 'null', '-'],timeout=900)
    assert original.resolve().is_relative_to((app.DATA/'sources').resolve())
    original.unlink()
    return {'video_id': vid, 'count':len(entries), 'tracks':entries}


if __name__ == '__main__':
    # Do not depend on the Windows console code page for Korean titles.
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    summaries, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [(s,pool.submit(import_source,s)) for s in SOURCES]
        for spec, future in futures:
            try: summaries.append(future.result())
            except Exception as exc:
                errors.append({'video_id':spec['id'], 'error':str(exc)})
                print('ERROR ' + spec['id'] + ' ' + str(exc), flush=True)
    result = {'sources':summaries, 'errors':errors}
    (app.DATA / 'collection-import.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('COMPLETE ' + json.dumps({'tracks':sum(x['count'] for x in summaries),'errors':errors}),flush=True)
    if errors: raise SystemExit(1)
