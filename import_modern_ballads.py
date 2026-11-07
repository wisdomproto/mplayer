"""Reviewed 2010s and 2020s ballads, 50 per decade. Search, then import."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import app
from expand_ballads import ALIASES, key, search
from import_collection import import_source

SELECTION = {
 '2010년대': '''박효신|야생화|2014
박효신|숨|2016
박효신|Goodbye|2019
성시경|너의 모든 순간|2014
성시경|너는 나의 봄이다|2011
김범수|끝사랑|2011
허각|Hello|2011
허각|나를 사랑했던 사람아|2012
아이유|밤편지|2017
임창정|내가 저지른 사랑|2016
임창정|또 다시 사랑|2015
임창정|나란 놈이란|2013
임창정|하루도 그대를 사랑하지 않은 적이 없었다|2018
엠씨더맥스|어디에도|2016
엠씨더맥스|그대가 분다|2014
엠씨더맥스|넘쳐흘러|2019
정승환|너였다면|2016
정승환|이 바보야|2016
정승환|눈사람|2018
폴킴|모든 날 모든 순간|2018
폴킴|너를 만나|2018
폴킴|안녕|2019
멜로망스|선물|2017
멜로망스|동화|2018
김동률|그게 나야|2014
아이유|Love poem|2019
김동률|Replay|2011
박원|all of my life|2017
박원|노력|2016
한동근|이 소설의 끝을 다시 써보려 해|2014
한동근|그대라는 사치|2016
정준일|안아줘|2011
이하이|한숨|2016
에일리|첫눈처럼 너에게 가겠다|2017
에일리|저녁 하늘|2012
벤|열애중|2018
벤|180도|2018
다비치|안녕이라고 말하지마|2011
다비치|이 사랑|2016
태연|그대라는 시|2019
거미|You Are My Everything|2016
백지영|그 여자|2010
이적|걱정말아요 그대|2015
로이킴|그때 헤어지면 돼|2018
윤종신|좋니|2017
김나영|솔직하게 말해서 나|2019
양다일|미안해|2017
신용재|가수가 된 이유|2012
포맨|못해|2010
규현|광화문에서|2014''',
 '2020년대': '''아이유|마음을 드려요|2020
아이유|Love wins all|2024
아이유|겨울잠|2021
성시경|안녕 나의 사랑|2021
박효신|HERO|2024
임영웅|사랑은 늘 도망가|2021
임영웅|우리들의 블루스|2022
임영웅|다시 만날 수 있을까|2022
임영웅|이제 나만 믿어요|2020
임영웅|모래 알갱이|2023
임영웅|온기|2024
이무진|에피소드|2023
이무진|눈이 오잖아|2021
멜로망스|사랑인가 봐|2022
김민석|취중고백|2021
폴킴|우리 만남이|2020
폴킴|한강에서|2023
정승환|언제라도 어디에서라도|2020
정승환|친구 그 오랜시간|2020
규현|내 마음이 움찔했던 순간|2020
규현|내 마음을 누르는 일|2020
규현|마지막 날에|2021
10CM|서랍|2021
10CM|봄눈|2024
적재|나랑 같이 걸을래|2020
잔나비|가을밤에 든 생각|2020
헤이즈|헤픈 우연|2021
경서|밤하늘의 별을|2020
경서|나의 X에게|2022
경서예지|다정히 내 이름을 부르면|2021
경서예지|사실 나는|2020
순순희|서면역에서|2020
신예영|네가 보고 싶은 건 자연스러운 거겠지|2023
신예영|미안하다고 말하지 말아줘|2020
이예준|미친 소리|2020
이예준|안녕과 안녕으로|2021
이예준|그날에 나는 맘이 편했을까|2021
허각|우린 어쩌다 헤어진 걸까|2020
허각|물론|2023
지아|사랑하기 싫어|2023
WSG워너비(가야G)|그때 그 순간 그대로|2022
박재정|헤어지자 말해요|2023
박재정|너의 그 사람|2021
박재정|좋았는데|2021
임한별|사랑하지 않아서 그랬어|2023
임한별|떠나보낼 준비해 둘걸 그랬어|2022
한동근|새벽에 걸려온 너의 전화는|2020
신용재|첫 줄|2020
김필|그때 그 아인|2020
Crush|미안해 미워해 사랑해|2024'''
}

ALIASES.update({
 '허각':['huhgak','hugak'],'엠씨더맥스':['mcthemax','mcthemaxofficial','엠씨더맥스'],
 '정승환':['jungseunghwan'],'폴킴':['paulkim'],'멜로망스':['melomance'],
 '박원':['parkwon'],'한동근':['handonggeun'],'정준일':['jungjoonil'],
 '이하이':['leehi'],'에일리':['ailee'],'벤':['ben'], '다비치':['davichi'],
 '태연':['taeyeon'],'로이킴':['roykim'],'김나영':['kimnayoung'],'양다일':['yangdail'],
 '신용재':['shinyongjae'],'포맨':['4men','fourmen'],'규현':['kyuhyun'],
 '아이유':['iu'],'임영웅':['limyoungwoong','imyoungwoong'],'이무진':['leemujin'],
 '김민석':['kimminseok'],'10CM':['10cm','십센치'],'적재':['jukjae'],
 '잔나비':['jannabi'],'헤이즈':['heize'],'경서':['kyoungseo','gyeongseo','kyungseo'],
 '경서예지':['경서','gyeongseo','kyoungseo','전건호','jeongeonho'],
 '순순희':['soonsoonhee','sunsunhee'],'신예영':['shinyeyoung'],'이예준':['leeyejoon','leeyejun'],
 '지아':['zia'],'박재정':['parcjaejung','parkjaejung'],'임한별':['onestar','limhanbyul'],
 '김필':['kimfeel'],'Crush':['crush','크러쉬']
})

PLAN=app.DATA/'modern-ballads-plan.json'
REPORT=app.DATA/'modern-ballads-import.json'

def songs():
    out=[]
    for decade,block in SELECTION.items():
        lines=block.strip().splitlines()
        assert len(lines)==50,(decade,len(lines))
        for line in lines:
            artist,title,year=line.split('|')
            out.append(dict(artist=artist,title=title,year=int(year),decade=decade,album=decade+' 인기 발라드'))
    assert len({key(s['artist'],s['title']) for s in out})==100
    return out

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if '--search' in sys.argv:
        with app.db() as c:
            baseline=[dict(r) for r in c.execute('SELECT * FROM tracks')]
        assert len(baseline)==190,len(baseline)
        oldkeys={key(t['artist'],t['title']) for t in baseline}
        assert not oldkeys.intersection(key(s['artist'],s['title']) for s in songs())
        (app.DATA/'modern-ballads-baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2),encoding='utf-8')
        results=[]
        with ThreadPoolExecutor(4) as pool:
            fs={pool.submit(search,s):s for s in songs()}
            for f in as_completed(fs):
                s=fs[f]
                try:r=f.result()
                except Exception as e:r=dict(s,error=str(e))
                results.append(r)
                PLAN.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
                print('FOUND '+s['artist']+' '+s['title'],flush=True)
        return
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    assert len(plan)==100 and all(s.get('id') for s in plan)
    assert len({s['id'] for s in plan})==100
    results=[];errors=[]
    def perform(s):
        with app.db() as c:
            existing=[dict(r) for r in c.execute('SELECT * FROM tracks WHERE artist=?',(s['artist'],)) if key(r['artist'],r['title'])==key(s['artist'],s['title'])]
        if existing:
            assert len(existing)==1 and (app.MEDIA/existing[0]['filename']).is_file()
            return dict(video_id=s['id'],count=1,tracks=[{'id':existing[0]['id'],'title':s['title']}],reused=True)
        return import_source(s)
    with ThreadPoolExecutor(4) as pool:
        fs={pool.submit(perform,s):s for s in plan}
        for f in as_completed(fs):
            s=fs[f]
            try:
                r=f.result();r['decade']=s['decade'];results.append(r)
            except Exception as e:errors.append(dict(s,error=str(e)))
            REPORT.write_text(json.dumps({'sources':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    if not errors:
        old=json.loads((app.ROOT/'ballads_catalog.json').read_text(encoding='utf-8'))
        merged={key(s['artist'],s['title']):s for s in old}
        merged.update({key(s['artist'],s['title']):{k:s[k] for k in ['artist','title','year','decade','album','id']} for s in plan})
        (app.ROOT/'ballads_catalog.json').write_text(json.dumps(list(merged.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    print('COMPLETE '+json.dumps({'tracks':len(results),'errors':len(errors)}),flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
