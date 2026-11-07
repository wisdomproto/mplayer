"""Final audit of MP3 retention, complete podcast import, and range streaming."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import urllib.request
import app
from import_podcasts import validate, ALBUM, PLAN, REPORT

def main():
    validate()
    baseline=json.loads((app.DATA/'cleanup-baseline-20261028.json').read_text(encoding='utf-8'))
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    imported=json.loads(REPORT.read_text(encoding='utf-8'))
    with app.db() as c:tracks=[dict(t) for t in c.execute('SELECT * FROM tracks')]
    byid={t['id']:t for t in tracks}
    assert all(all(byid[t['id']][k]==t[k] for k in ('id','filename','duration','source')) for t in baseline)
    assert len(plan)==len(imported['episodes'])==314 and not imported['errors']
    assert len(tracks)==854
    for root in [app.DATA.resolve(),(app.ROOT/'data').resolve()]:
        leftovers=[str(p) for p in root.rglob('*') if p.is_file() and (p.suffix.lower() in {'.webm','.m4a','.opus','.ogg','.mp4','.wav','.flac','.mkv'} or p.name.endswith(('.part','.ytdl')))]
        assert not leftovers,leftovers
    def stream(t):
        path=app.MEDIA/t['filename'];size=path.stat().st_size
        assert path.suffix=='.mp3' and size>1024
        request=urllib.request.Request('http://127.0.0.1:8765/media/'+t['id'],headers={'Range':f'bytes={size-1024}-{size-1}'})
        with urllib.request.urlopen(request,timeout=30) as response:
            assert response.status==206 and len(response.read())==1024
            assert response.headers['Content-Range']==f'bytes {size-1024}-{size-1}/{size}'
    with ThreadPoolExecutor(6) as pool:list(pool.map(stream,tracks))
    cleanup=json.loads((app.DATA/'audio-source-cleanup-20261028.json').read_text(encoding='utf-8'))
    assert not cleanup['errors']
    assert all(Path(t['path']).is_file() and Path(t['path']).stat().st_size==t['bytes'] for t in cleanup['verified_mp3'])
    result=dict(library_tracks=len(tracks),podcast_files=sum(t['album']==ALBUM for t in tracks),
                prior_tracks_preserved=len(baseline),source_audio_remaining=0,streaming_tail_checks=len(tracks),
                source_ids_unique=len({t['source'] for t in tracks if t['album']==ALBUM})==314)
    (app.DATA/'mp3-only-final-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
