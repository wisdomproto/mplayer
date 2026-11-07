"""Delete only converted source audio after fully decoding every retained MP3."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import subprocess
import app

ROOTS=[app.DATA.resolve(),(app.ROOT/'data').resolve()]
REPORT=app.DATA/'audio-source-cleanup-20261028.json'
EXTENSIONS={'.webm','.m4a','.opus','.ogg','.mp4','.mkv','.wav','.flac'}

def save(data):
    temp=REPORT.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(REPORT)

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def verify(path):
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-threads','1','-i',str(path),
                    '-map','0:a:0','-f','null','-'],capture_output=True,check=True,timeout=1200)
    return dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size)

def main():
    with app.db() as c:tracks=[dict(t) for t in c.execute('SELECT * FROM tracks')]
    # Scan only the two explicitly known project data roots, never the whole disk.
    files=[p.resolve() for root in ROOTS if root.exists() for p in root.rglob('*') if p.is_file()]
    registered={t['filename'] for t in tracks}
    retained=[p for p in files if p.suffix.lower()=='.mp3' and (p.name in registered or 'correction-archive' in p.parts)]
    originals=[p for p in files if p.suffix.lower() in EXTENSIONS and 'sources' in p.parts]
    current=[p for p in retained if p.is_relative_to(app.DATA.resolve())]
    verified={};errors=[]
    with ThreadPoolExecutor(8) as pool:
        futures={pool.submit(verify,p):p for p in current}
        for f in as_completed(futures):
            p=futures[f]
            try:verified[p]=f.result()
            except Exception as exc:errors.append(dict(path=str(p),error=str(exc)))
            if len(verified)%50==0:print('VERIFIED '+str(len(verified)),flush=True)
    for p in retained:
        if p in verified:continue
        equivalent=app.MEDIA/p.name
        if equivalent in verified and digest(p)==verified[equivalent]['sha256']:
            verified[p]=dict(path=str(p),sha256=verified[equivalent]['sha256'],bytes=p.stat().st_size)
        else:
            try:verified[p]=verify(p)
            except Exception as exc:errors.append(dict(path=str(p),error=str(exc)))
    assert not errors,errors
    assert all((app.MEDIA/t['filename']).resolve() in verified for t in tracks)
    save(dict(verified_mp3=list(verified.values()),errors=errors,candidates=[],skipped=[],deleted=[]))
    candidates=[];skipped=[];already_removed=[]
    for p in originals:
        assert any(p.is_relative_to(root) for root in ROOTS)
        if not p.exists():
            already_removed.append(str(p));continue
        receipt=p.parent/'import.json';refs=[]
        if receipt.exists():
            info=json.loads(receipt.read_text(encoding='utf-8'))
            if 'tracks' in info:
                refs=[t['id']+'.mp3' for t in info['tracks']]
            elif info.get('filename'):refs=[info['filename']]
        if not refs:
            source='https://www.youtube.com/watch?v='+p.parent.name
            refs=[t['filename'] for t in tracks if t['source']==source]
        good=bool(refs) and all(any((folder/name).resolve() in verified for folder in [app.MEDIA,app.DATA/'correction-archive']) for name in refs)
        if good:
            try:candidates.append(dict(path=str(p),bytes=p.stat().st_size,mp3=refs))
            except FileNotFoundError:already_removed.append(str(p))
        else:skipped.append(str(p))
    report=dict(verified_mp3=list(verified.values()),errors=errors,candidates=candidates,skipped=skipped,already_removed=already_removed,deleted=[])
    save(report)
    for entry in candidates:
        path=Path(entry['path']).resolve()
        assert any(path.is_relative_to(root) for root in ROOTS)
        assert path.suffix.lower() in EXTENSIONS and 'sources' in path.parts
        if not path.exists():
            report['already_removed'].append(str(path));continue
        assert path.stat().st_size==entry['bytes']
        path.unlink()
        report['deleted'].append(entry)
    report['reclaimed_bytes']=sum(s['bytes'] for s in report['deleted'])
    assert all(Path(p).is_file() and Path(p).stat().st_size==entry['bytes'] for p,entry in ((s['path'],s) for s in report['verified_mp3']))
    save(report)
    print(json.dumps(dict(verified_mp3=len(verified),deleted=len(report['deleted']),skipped=skipped,reclaimed_bytes=report['reclaimed_bytes'])),flush=True)

if __name__=='__main__':main()
