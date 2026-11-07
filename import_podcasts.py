"""Import numbered 지대넓얕 episodes as separate, resumable MP3 tracks on D:."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import json
import re
import sqlite3
import uuid
import app

FOLDER=app.DATA/'podcasts'
ALBUM='지대넓얕 팟캐스트'
CHANNEL='UCSBY7p0W5LFGfCLtlnJ8LJg'
PLAN=FOLDER/'jidaenulbyat-plan.json'
REPORT=FOLDER/'jidaenulbyat-import.json'

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def episode_info(info):
    assert info.get('channel_id',CHANNEL)==CHANNEL
    original=info['title']
    match=re.search(r'지대넓얕[_\s]*(\d+)(?:회|화)?[_\s]*(.*)',original)
    if not match:raise ValueError('Episode number not found: '+original)
    episode=int(match[1]);body=re.sub(r'[_\s]+',' ',match[2]).strip()
    part=re.search(r'(\d+)부',body)
    return dict(id=info['id'],title=f'{episode:03d}회 · {body}',original_title=original,
                artist='지대넓얕',album=ALBUM,episode=episode,part=int(part[1]) if part else 0,
                extra='번외' in body,duration=info['duration'],source=info.get('webpage_url') or info['url'],
                channel=info.get('channel') or '지대넓얕애청자')

def metadata(entry):
    dest=FOLDER/'metadata'/(entry['id']+'.json')
    if dest.exists():info=json.loads(dest.read_text(encoding='utf-8'))
    else:
        info=json.loads(app.run(['yt-dlp','--skip-download','--dump-single-json','--no-warnings',
                                '--extractor-args','youtube:lang=ko',entry['url']],timeout=180))
        save(dest,info)
    return episode_info(info)

def make_plan(limit,all_episodes=False):
    inventory=json.loads((FOLDER/('jidaenulbyat-channel-all.json' if all_episodes else 'jidaenulbyat-channel.json')).read_text(encoding='utf-8'))
    assert inventory['id']==CHANNEL
    if all_episodes:
        result=[episode_info(entry) for entry in inventory['entries']]
        limit=len(result)
        result.sort(key=lambda s:(s['episode'],s['extra'],s['part'],s['title']))
        assert len(result)==len({s['id'] for s in result})
        for index,s in enumerate(result,1):s['index']=index
        save(PLAN,result)
        print('PLAN '+json.dumps(dict(files=len(result),hours=sum(s['duration'] for s in result)/3600)),flush=True)
        return
    candidates=[]
    for entry in inventory['entries']:
        number=re.search(r'\d+',entry['title'])
        if number and entry.get('duration',0)>600:candidates.append((int(number[0]),entry))
    candidates.sort(key=lambda value:value[0])
    cutoff=candidates[min(limit,len(candidates))-1][0]
    candidates=[e for n,e in candidates if n<=cutoff]
    result=[]
    with ThreadPoolExecutor(4) as pool:
        futures=[pool.submit(metadata,e) for e in candidates]
        for future in as_completed(futures):
            result.append(future.result());print('METADATA '+str(len(result)),flush=True)
    result.sort(key=lambda s:(s['episode'],s['extra'],s['part'],s['title']))
    result=result[:limit]
    assert len(result)==len({s['id'] for s in result})==limit
    for index,s in enumerate(result,1):s['index']=index
    save(PLAN,result)
    print('PLAN '+json.dumps(dict(files=len(result),hours=sum(s['duration'] for s in result)/3600)),flush=True)

def download(spec):
    with app.db() as connection:
        old=connection.execute('SELECT * FROM tracks WHERE source=? AND album=?',(spec['source'],ALBUM)).fetchone()
    if old and (app.MEDIA/old['filename']).exists():return dict(spec,track_id=old['id'],reused=True)
    source_dir=FOLDER/'sources'/spec['id'];source_dir.mkdir(parents=True,exist_ok=True)
    receipt=source_dir/'import.json'
    if receipt.exists():
        cached=json.loads(receipt.read_text(encoding='utf-8'))
        cached_path=app.MEDIA/cached['filename']
        if cached_path.exists() and cached['title']==spec['title']:
            actual,tags=app.metadata(cached_path)
            if abs(actual-cached['actual_duration'])<.1 and tags.get('title')==spec['title']:
                return dict(spec,filename=cached_path.name,actual_duration=actual)
    app.run(['yt-dlp','--no-playlist','--no-warnings','--no-progress','--extractor-args','youtube:lang=ko',
             '--socket-timeout','25','--retries','2','--max-filesize','500M','-f','bestaudio/best',
             '--write-info-json','-o',str(source_dir/'source.%(ext)s'),spec['source']],timeout=1200)
    originals=[p for p in source_dir.glob('source.*') if p.suffix in ('.m4a','.webm','.opus','.mp3','.mp4')]
    assert len(originals)==1
    duration,_=app.metadata(originals[0])
    target=app.MEDIA/(uuid.uuid4().hex+'.mp3')
    try:
        app.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(originals[0]),'-map','0:a:0',
                 '-map_metadata','-1','-codec:a','libmp3lame','-b:a','96k','-ac','1','-id3v2_version','3',
                 '-metadata','title='+spec['title'],'-metadata','artist='+spec['artist'],
                 '-metadata','album='+ALBUM,'-metadata','genre=Podcast',
                 '-metadata','track='+str(spec['index']),'-metadata','comment='+spec['source'],str(target)],timeout=900)
        actual,tags=app.metadata(target)
        assert abs(actual-duration)<.5 and tags['title']==spec['title'] and tags['album']==ALBUM
        app.run(['ffmpeg','-nostdin','-v','error','-xerror','-threads','1','-i',str(target),'-map','0:a:0','-f','null','-'],timeout=900)
        result=dict(spec,filename=target.name,actual_duration=actual)
        save(receipt,result)
        return result
    except Exception:
        target.unlink(missing_ok=True);raise

def validate():
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    baseline=json.loads((FOLDER/'library-before-podcast.json').read_text(encoding='utf-8'))
    with app.db() as connection:tracks=[dict(t) for t in connection.execute('SELECT * FROM tracks')]
    byid={s['id']:s for s in tracks}
    for old in baseline:
        assert all(byid[old['id']][k]==old[k] for k in ('id','filename','duration','source')),old['id']
    episodes=[s for s in tracks if s['album']==ALBUM]
    assert len(episodes)==len(plan)
    assert len({s['source'] for s in episodes})==len(episodes)
    bysource={s['source']:s for s in episodes}
    def inspect(spec):
        t=bysource[spec['source']];duration,tags=app.metadata(app.MEDIA/t['filename'])
        source_dir=FOLDER/'sources'/spec['id']
        receipt=json.loads((source_dir/'import.json').read_text(encoding='utf-8'))
        video=json.loads((source_dir/'source.info.json').read_text(encoding='utf-8'))
        assert abs(duration-t['duration'])<.1 and abs(duration-receipt['actual_duration'])<.1
        assert abs(duration-video['duration'])<2
        for k in ('title','artist','album'):assert tags[k]==t[k]==spec[k]
        assert tags['genre']=='Podcast'
        return duration
    with ThreadPoolExecutor(8) as pool:total=sum(pool.map(inspect,plan))
    result=dict(episodes=len(episodes),hours=total/3600,baseline_preserved=len(baseline),
                total_tracks=len(tracks),tags_verified=len(episodes),storage=str(app.DATA))
    save(FOLDER/'jidaenulbyat-validation.json',result)
    print(json.dumps(result,ensure_ascii=False))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',action='store_true');parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--validate',action='store_true')
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    if args.validate:validate();return
    if args.plan:make_plan(args.limit,args.all);return
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    with app.db() as c:
        if not (FOLDER/'library-before-podcast.json').exists():
            save(FOLDER/'library-before-podcast.json',[dict(t) for t in c.execute('SELECT * FROM tracks')])
            with sqlite3.connect(FOLDER/'library-before-podcast.db') as target:c.backup(target)
    results=[];errors=[]
    with ThreadPoolExecutor(args.workers) as pool:
        futures={pool.submit(download,s):s for s in plan}
        for f in as_completed(futures):
            s=futures[f]
            try:
                result=f.result()
                if not result.get('track_id'):
                    result['track_id']=app.add_track(app.MEDIA/result['filename'],result['title'],result['artist'],ALBUM,result['source'])
                source_dir=(FOLDER/'sources'/result['id']).resolve()
                assert source_dir.is_relative_to((FOLDER/'sources').resolve())
                for original in source_dir.glob('source.*'):
                    if original.suffix.lower() in {'.m4a','.webm','.opus','.mp3','.mp4','.ogg'}:
                        assert original.resolve().is_relative_to(source_dir)
                        original.unlink()
                results.append(result);print('SAVED '+str(len(results))+' '+s['title'],flush=True)
            except Exception as exc:errors.append(dict(s,error=str(exc)));print('ERROR '+s['title']+' '+str(exc),flush=True)
            save(REPORT,dict(episodes=results,errors=errors))
    results.sort(key=lambda s:s['index'])
    save(REPORT,dict(episodes=results,errors=errors))
    print('COMPLETE '+json.dumps(dict(episodes=len(results),errors=len(errors))),flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8');main()
