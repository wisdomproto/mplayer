"""Verify the completed expansion against its preserved baseline and MP3 tags."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
import urllib.request
import app
from expand_ballads import key

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    baseline=json.loads((app.DATA/'ballads-100-baseline.json').read_text(encoding='utf-8'))
    plan=json.loads((app.DATA/'ballads-100-plan.json').read_text(encoding='utf-8'))
    with app.db() as c:tracks=[dict(t) for t in c.execute('SELECT * FROM tracks')]
    byid={t['id']:t for t in tracks};oldids={t['id'] for t in baseline}
    new=[t for t in tracks if t['id'] not in oldids]
    assert len(tracks)==540 and len(new)==250
    for old in baseline:
        assert all(byid[old['id']][k]==v for k,v in old.items()),old['id']
        # Original C: files remain available as the migration backup.
        original=app.ROOT/'data'/'music'/old['filename']
        assert digest(original)==digest(app.MEDIA/old['filename']),old['filename']
    assert len({key(t['artist'],t['title']) for t in new})==250
    assert not {key(t['artist'],t['title']) for t in new}&{key(t['artist'],t['title']) for t in baseline}
    specs={key(s['artist'],s['title']):s for s in plan}
    def check(t):
        spec=specs[key(t['artist'],t['title'])]
        duration,tags=app.metadata(app.MEDIA/t['filename'])
        assert duration>120 and abs(duration-t['duration'])<.1
        for k in ('artist','title','album'):assert tags[k]==t[k],(t['title'],k)
        assert tags['date']==str(spec['year'])
        assert t['source']=='https://www.youtube.com/watch?v='+spec['id']
        return t['id']
    with ThreadPoolExecutor(4) as pool:verified=list(pool.map(check,new))
    counts=Counter(t['album'] for t in tracks if t['album'].endswith('년대 인기 발라드'))
    assert len(counts)==5 and all(n==100 for n in counts.values()),counts
    for album in counts:
        track=next(t for t in new if t['album']==album)
        req=urllib.request.Request('http://127.0.0.1:8765/media/'+track['id'],headers={'Range':'bytes=0-1023'})
        with urllib.request.urlopen(req) as response:assert response.status==206 and len(response.read())==1024
    report=dict(total=len(tracks),new=len(new),baseline_preserved=len(baseline),new_unique=True,
                albums=dict(counts),mp3_tags_verified=len(verified),range_checks=5,storage=str(app.DATA))
    (app.DATA/'ballads-100-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
