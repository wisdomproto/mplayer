"""Find and import 38 additional, distinct ballads for each decade."""
import concurrent.futures
import json
import re
import subprocess
import sys
import threading
import unicodedata
from pathlib import Path

import app
from import_collection import import_source

SELECTION = {
 '1980년대': '''김현식|사랑했어요|1984
김현식|비처럼 음악처럼|1986
김현식|가리워진 길|1986
김현식|여름밤의 꿈|1988
유재하|그대 내 품에|1987
유재하|지난날|1987
유재하|우울한 편지|1987
유재하|우리들의 사랑|1987
이문세|난 아직 모르잖아요|1985
이문세|이별 이야기|1987
이문세|휘파람|1985
이문세|그녀의 웃음소리뿐|1987
변진섭|숙녀에게|1989
변진섭|너무 늦었잖아요|1988
변진섭|로라|1989
변진섭|우리의 사랑이 필요한 거죠|1989
이선희|영|1986
이선희|나 항상 그대를|1988
조덕배|나의 옛날 이야기|1985
조덕배|그대 내 맘에 들어오면은|1989
조덕배|슬픈 노래는 부르지 않을거야|1985
조용필|허공|1985
조용필|그 겨울의 찻집|1985
조용필|친구여|1983
조용필|창밖의 여자|1980
조용필|촛불|1980
이용|잊혀진 계절|1982
최성수|동행|1987
최성수|해후|1987
이광조|가까이 하기엔 너무 먼 당신|1985
이광조|사랑을 잃어버린 나|1985
김수철|못다 핀 꽃 한 송이|1983
전영록|저녁놀|1987
양수경|사랑은 창밖에 빗물 같아요|1989
양수경|바라볼 수 없는 그대|1988
임지훈|사랑의 썰물|1987
김종찬|사랑이 저만치 가네|1987
나미|슬픈 인연|1985''',
 '1990년대': '''김현식|내 사랑 내 곁에|1991
김광석|사랑했지만|1991
김광석|이등병의 편지|1990
김광석|너무 아픈 사랑은 사랑이 아니었음을|1994
김광석|잊어야 한다는 마음으로|1992
김광석|어느 60대 노부부 이야기|1995
신승훈|널 사랑하니까|1993
신승훈|나보다 조금 더 높은 곳에 니가 있을 뿐|1996
신승훈|그 후로 오랫동안|1994
신승훈|처음 그 느낌처럼|1993
김건모|잠 못 드는 밤 비는 내리고|1992
김건모|혼자만의 사랑|1993
조성모|슬픈 영혼식|1999
조성모|불멸의 사랑|1998
임창정|결혼해줘|1997
임창정|이미 나에게로|1995
김정민|마지막 약속|1995
김정민|애인|1996
박정운|먼 훗날에|1992
이소라|청혼|1996
이소라|처음 느낌 그대로|1995
전람회|이방인|1994
전람회|졸업|1997
김동률|배려|1998
김동률|기적|1998
패닉|기다리다|1995
패닉|달팽이|1995
윤종신|오래전 그날|1993
윤종신|너의 결혼식|1992
윤종신|환생|1996
015B|이젠 안녕|1991
015B|텅 빈 거리에서|1990
이승철|오직 너뿐인 나를|1991
최재훈|널 보낸 후에|1998
김민종|착한 사랑|1998
더 클래식|마법의 성|1994
이원진|시작되는 연인들을 위해|1994
김민우|사랑일뿐야|1990''',
 '2000년대': '''성시경|두 사람|2005
성시경|넌 감동이었어|2002
성시경|희재|2003
성시경|한번 더 이별|2007
박효신|해줄 수 없는 일|2000
박효신|좋은 사람|2002
박효신|동경|2001
박효신|추억은 사랑을 닮아|2007
김범수|하루|2000
브라운 아이즈|점점|2002
브라운 아이즈|가지마 가지마|2008
브라운 아이드 소울|정말 사랑했을까|2003
SG워너비|Timeless|2004
SG워너비|죄와 벌|2005
SG워너비|내 사람|2006
SG워너비|라라라|2008
버즈|가시|2005
버즈|남자를 몰라|2006
버즈|은인|2006
이수영|라라라|2002
이수영|덩그러니|2003
이수영|그리고 사랑해|2001
테이|사랑은 하나다|2005
테이|같은 베개|2007
백지영|총 맞은 것처럼|2008
백지영|잊지 말아요|2009
이승기|내 여자라니까|2004
이승기|하기 힘든 말|2006
김종국|한 남자|2004
김종국|제자리 걸음|2005
김태우|사랑비|2009
이적|다행이다|2007
이은미|애인 있어요|2005
박화요비|그런 일은|2000
박정현|꿈에|2002
거미|기억상실|2004
휘성|안되나요|2002
플라이 투 더 스카이|Missing You|2003'''
}

ALIASES = {
 '김현식':['kimhyunsik','kimhyunsick'],'유재하':['yoojaeha','yujaeha'],
 '이문세':['leemoonsae'],'변진섭':['byeonjinseob','byunjinsub'],
 '이선희':['leesunhee','leesunheui'],'조덕배':['joduckbai','jodeokbae'],
 '조용필':['choyongpil','joyongpil'],'이용':['leeyong'], '최성수':['choisungsoo','choiseongsu'],
 '이광조':['leekwangjo','leegwangjo'],'김수철':['kimsoochul','kimsucheol'],
 '전영록':['jeonyoungrok','jeonyeongrok'],'양수경':['yangsookyung'],
 '임지훈':['limjihoon','imjihoon'],'김종찬':['kimjongchan'],'나미':['nami'],
 '김광석':['kimkwangseok','kimgwangseok'],'신승훈':['shinseunghun'],
 '김건모':['kimgunmo','kimgeonmo'],'조성모':['josungmo','joseongmo'],
 '임창정':['imchangjung','limchangjung'],'김정민':['kimjungmin','kimjeongmin'],
 '박정운':['parkjungwoon','parkjeongun'],'이소라':['leesora'],'전람회':['exhibition'],
 '김동률':['kimdongryul'],'패닉':['panic'],'윤종신':['yoonjongshin','yoonjongshin'],
 '015B':['015b','공일오비'],'이승철':['leeseungchul','leeseungcheol'],
 '최재훈':['choijaehoon'],'김민종':['kimminjong'],'더 클래식':['theclassic','더클래식'],
 '이원진':['leewonjin'],'김민우':['kimminwoo'],
 '성시경':['sungsikyung'],'박효신':['parkhyoshin'],'김범수':['kimbumsoo'],
 '브라운 아이즈':['browneyes'],'브라운 아이드 소울':['browneyedsoul'],
 'SG워너비':['sgwannabe'],'버즈':['buzz'],'이수영':['leesooyoung','leesuyoung'],
 '테이':['tei'],'백지영':['baekzyoung','baekjiyoung'],'이승기':['leeseunggi'],
 '김종국':['kimjongkook'],'김태우':['kimtaewoo'],'이적':['leejuck','leejeok'],
 '이은미':['leeeunmee','leeeunmi'],'박화요비':['parkhwayobi','hwayobi','화요비'],
 '박정현':['lenapark','parkjunghyun'],'거미':['gummy'],'휘성':['wheesung','reesung'],
 '플라이 투 더 스카이':['flytothesky']
}

def norm(text):
    return re.sub(r'[^a-z0-9가-힣]', '', unicodedata.normalize('NFKC', text).lower())

def key(artist,title):
    return norm(artist), norm(re.sub(r'\([^)]*\)', '',title))

def entries():
    existing = json.loads((app.ROOT/'ballads_catalog.json').read_text(encoding='utf-8'))
    with app.db() as c: known = {key(r['artist'],r['title']) for r in c.execute('SELECT artist,title FROM tracks')}
    planned = []
    for decade, block in SELECTION.items():
        lines=block.strip().splitlines()
        assert len(lines)==38,(decade,len(lines))
        for line in lines:
            artist,title,year=line.split('|')
            song={'decade':decade,'artist':artist,'title':title,'year':int(year),'album':decade+' 인기 발라드'}
            if key(artist,title) not in {key(s['artist'],s['title']) for s in existing}:
                planned.append(song)
    return existing,planned,known

def search(song):
    label=song['artist']+' '+song['title']
    p=app.run(['yt-dlp','--flat-playlist','--dump-single-json','--no-warnings',
               '--socket-timeout','20','ytsearch5:'+label+' Topic'],timeout=120)
    candidates=json.loads(p).get('entries',[])
    aliases=[norm(song['artist'])]+ALIASES.get(song['artist'],[])
    def rank(c):
        title=norm(c.get('title','')); channel=norm(c.get('channel',''))
        score=60 if any(a in channel for a in aliases) else 0
        score+=25 if norm(song['title']) in title else 0
        score+=15 if norm(song['artist']) in title else 0
        score+=15 if 'topic' in channel else 0
        if any(w in title for w in ['cover','karaoke','instrumental','노래방','커버','모음','playlist','1시간','1hour','shorts']):score-=150
        duration=c.get('duration') or 0
        if not 120<=duration<=650:score-=150
        return score
    candidates.sort(key=rank,reverse=True)
    result=dict(song,candidates=[{k:c.get(k) for k in ('id','title','channel','duration')} for c in candidates])
    if candidates and rank(candidates[0])>=40:result['id']=candidates[0]['id']
    return result

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    existing,planned,known=entries()
    planfile=app.DATA/'ballads-expansion-plan.json'
    if '--search' in sys.argv:
        if not planned:
            print('The expansion catalog is already complete.',flush=True)
            return
        results=[]
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            fs={pool.submit(search,s):s for s in planned}
            for f in concurrent.futures.as_completed(fs):
                s=fs[f]
                try:r=f.result()
                except Exception as exc:r=dict(s,error=str(exc))
                results.append(r)
                planfile.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({'artist':s['artist'],'title':s['title'],'id':r.get('id'),'top':r.get('candidates',[])[:2],'error':r.get('error')},ensure_ascii=False),flush=True)
        return
    plan=json.loads(planfile.read_text(encoding='utf-8'))
    assert len(plan)==114,len(plan)
    assert all(s.get('id') for s in plan),'Resolve missing sources before importing'
    results=[];errors=[]
    def perform(s):
        with app.db() as c:
            found=[dict(r) for r in c.execute('SELECT * FROM tracks WHERE artist=?',(s['artist'],)) if key(r['artist'],r['title'])==key(s['artist'],s['title'])]
        if found:
            assert len(found)==1,(s,found)
            assert (app.MEDIA/found[0]['filename']).is_file()
            return {'video_id':s['id'],'count':1,'tracks':[{'id':found[0]['id'],'title':s['title']}],'reused':True}
        return import_source(s)
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        fs={pool.submit(perform,s):s for s in plan}
        for f in concurrent.futures.as_completed(fs):
            s=fs[f]
            try:
                result=f.result();result['decade']=s['decade'];results.append(result)
                print('DONE '+s['artist']+' '+s['title'],flush=True)
            except Exception as exc:
                errors.append(dict(s,error=str(exc)));print('ERROR '+s['title']+' '+str(exc),flush=True)
            (app.DATA/'ballads-expansion-import.json').write_text(json.dumps({'sources':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    if not errors:
        clean=[{k:v for k,v in s.items() if k not in ('candidates','error')} for s in plan]
        merged={key(s['artist'],s['title']):s for s in existing}
        merged.update({key(s['artist'],s['title']):s for s in clean})
        (app.ROOT/'ballads_catalog.json').write_text(json.dumps(list(merged.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    print('COMPLETE '+json.dumps({'tracks':len(results),'errors':len(errors)}),flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
