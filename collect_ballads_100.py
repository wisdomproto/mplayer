"""Expand five existing decade collections from 50 to 100, preserving old files."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import sys
import sqlite3
import app
from import_collection import import_source
from import_modern_ballads import ALIASES
from expand_ballads import key, norm

PLAN=app.DATA/'ballads-100-plan.json'
REPORT=app.DATA/'ballads-100-import.json'
ALIASES.update({
 '조하문':['johamoon','johamun'],'유열':['youyeol','yuyeol'],
 '민해경':['minhaekyung'],'해바라기':['sunflower','해바라기'],
 '동물원':['dongmulwon'],'들국화':['deulgukhwa','deulgookhwa'],
 '시인과 촌장':['poetandvillagechief','시인과촌장'],'산울림':['sanullim'],
 '최호섭':['choihoseop','choihosub'],'강승모':['kangseungmo'],
 '김현철':['kimhyunchul'],'김성호':['kimsungho'],'이범학':['leebeomhak'],
 '이덕진':['leedeokjin'],'박준하':['parkjoonha'],'김현성':['kimhyunsung'],
 '부활':['boohwal'],'김경호':['kimkyungho','kimkyungho'],
 '김종서':['kimjongseo'],'박완규':['parkwankyu'],
 '에메랄드 캐슬':['emeraldcastle'],'야다':['yada'],'녹색지대':['greenarea','녹색지대'],
 '뱅크':['bank'],'김장훈':['kimjanghoon'],'윤상':['yoonsang'],'양파':['yangpa'],
 '나얼':['naul'],'씨야':['seeya'],'먼데이 키즈':['mondaykiz','먼데이키즈'],
 'V.O.S':['vos'],'KCM':['kcm'],'케이윌':['kwill'],'이루':['eru'],
 '정재욱':['jungjaewook'],'조장혁':['jojanghyuk'],'포지션':['position'],
 '빅마마':['bigmama'],'이지':['izi'],'김연우':['kimyeonwoo'],
 '박혜원':['hynn','박혜원'],'정인':['jungin'],'디오':['dohkyungsoo','디오','do'],
 '첸':['chen'],'임재범':['yimjaebeum','yimjaebum'],'더원':['theone'],
 '노을':['noel'],'장덕철':['jangdeokcheol'],'닐로':['nilo'],
 '송하예':['songhaye'],'임재현':['limjaehyun'],'펀치':['punch'],
 '장범준':['jangbeomjune'],'볼빨간사춘기':['bol4'],
 '황가람':['hwangkaram','hwanggaram'],'조째즈':['zojazz','jojazz'],
 '우디':['woody'],'이창섭':['leechangsub'],'웬디':['wendy'],
 '백현':['baekhyun'],'김세정':['kimsejeong'],'황인욱':['hwanginwook'],
 '정동하':['jungdongha'],'조정석':['chojungseok','jojeongseok'],'전미도':['jeonmido']
})

def selection():
    result=[];decade=None
    for line in (app.ROOT/'ballads_100_selection.txt').read_text(encoding='utf-8').splitlines():
        if line.startswith('['):decade=line.strip('[]');continue
        if not line.strip():continue
        a,t,y=line.split('|');result.append(dict(artist=a,title=t,year=int(y),decade=decade,album=decade+' 인기 발라드'))
    counts={d:sum(s['decade']==d for s in result) for d in {s['decade'] for s in result}}
    assert all(n==50 for n in counts.values()),counts
    assert len(result)==len({key(s['artist'],s['title']) for s in result})==250
    return result

def search(song):
    q=song.get('query') or song['artist']+' '+song['title']
    info=json.loads(app.run(['yt-dlp','--flat-playlist','--dump-single-json','--no-warnings',
                             '--socket-timeout','20','ytsearch5:'+q],timeout=120))
    aliases=[norm(song['artist'])]+ALIASES.get(song['artist'],[])
    def score(c):
        title=c.get('title') or '';n=norm(title);channel=norm(c.get('channel') or '')
        value=100 if norm(song['title']) in n else -60
        value+=35 if any(a in channel for a in aliases) else 0
        value+=15 if norm(song['artist']) in n else 0
        if re.search(r'\binst\b|\bMR\b|instrumental|karaoke|cover|Originally Perfo|반주|커버|모음|메들리|playlist|interview|질문|1시간|AI\s',title,re.I):value-=500
        if re.search(r'\blive\b|라이브|공연|축가|피아노\s',title,re.I):value-=20
        if not 120<=(c.get('duration') or 0)<=650:value-=500
        return value
    candidates=sorted(info.get('entries') or [],key=score,reverse=True)
    r=dict(song,candidates=[{k:c.get(k) for k in ['id','title','channel','duration']} for c in candidates])
    if candidates and score(candidates[0])>=80:r['id']=candidates[0]['id']
    return r

def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if '--search' in sys.argv:
        chosen=selection()
        with app.db() as c:before=[dict(t) for t in c.execute('SELECT * FROM tracks')]
        assert len(before)==290,len(before)
        old={key(t['artist'],t['title']) for t in before}
        overlap=[s for s in chosen if key(s['artist'],s['title']) in old]
        assert not overlap,overlap
        save(app.DATA/'ballads-100-baseline.json',before)
        with app.db() as source:
            with sqlite3.connect(app.DATA/'library-before-100.db') as target:source.backup(target)
        results=[]
        with ThreadPoolExecutor(4) as pool:
            futures={pool.submit(search,s):s for s in chosen}
            for f in as_completed(futures):
                s=futures[f]
                try:r=f.result()
                except Exception as exc:r=dict(s,error=str(exc))
                results.append(r);save(PLAN,results)
                print('SEARCHED '+str(len(results))+' '+s['artist']+' '+s['title'],flush=True)
        return
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    assert len(plan)==250 and all(s.get('id') for s in plan)
    assert len({s['id'] for s in plan})==250
    results=[];errors=[]
    def perform(s):
        with app.db() as c:
            matching=[dict(t) for t in c.execute('SELECT * FROM tracks') if key(t['artist'],t['title'])==key(s['artist'],s['title'])]
        if matching:
            assert len(matching)==1 and (app.MEDIA/matching[0]['filename']).is_file()
            return dict(video_id=s['id'],count=1,tracks=[{'id':matching[0]['id'],'title':s['title']}],reused=True)
        return import_source(s)
    with ThreadPoolExecutor(4) as pool:
        fs={pool.submit(perform,s):s for s in plan}
        for f in as_completed(fs):
            s=fs[f]
            try:r=f.result();r['decade']=s['decade'];results.append(r)
            except Exception as exc:errors.append(dict(s,error=str(exc)));print('ERROR '+s['title']+' '+str(exc),flush=True)
            save(REPORT,dict(sources=results,errors=errors))
    if not errors:
        old=json.loads((app.ROOT/'ballads_catalog.json').read_text(encoding='utf-8'))
        merged={key(s['artist'],s['title']):s for s in old}
        merged.update({key(s['artist'],s['title']):{k:s[k] for k in ['artist','title','year','decade','album','id']} for s in plan})
        save(app.ROOT/'ballads_catalog.json',list(merged.values()))
    print('COMPLETE '+json.dumps(dict(tracks=len(results),errors=len(errors))),flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
