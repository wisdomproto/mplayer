import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import app

QUERIES='''조용필 상처 Topic
임병수 약속 Topic
김필 나의 별이 돼주오
2F 너만 너만
김대명 가을 우체국 앞에서
정승환 별
멜로망스 찬란한 하루
첸 사라지고 있어
순순희 그대가 내 안에 박혔다
임재범 사랑 시티헌터
이승철 방황 Topic
김장훈 나와 같다면 Topic
이수영 I Believe Topic
임창정 소주 한잔 Topic
먼데이 키즈 Bye Bye Bye Topic
조성모 피아노 Topic
휘성 다시 만난 날 Topic
휘성 With Me Topic
휘성 불치병 Topic
플라이 투 더 스카이 남자답게 Topic
나얼 같은 시간 속의 너 Topic
성시경 잊지 말기로 해 Topic
벤 꿈처럼 Topic
디오 별 떨어진다 Topic
디오 Somebody Topic'''.splitlines()

def search(q):
    r=json.loads(app.run(['yt-dlp','--flat-playlist','--dump-single-json','--no-warnings','ytsearch5:'+q],timeout=120))
    return {'query':q,'candidates':[{k:s.get(k) for k in ['id','title','channel','duration']} for s in r.get('entries',[])]}

if __name__=='__main__':
    results=[]
    with ThreadPoolExecutor(4) as pool:
        for f in as_completed([pool.submit(search,q) for q in QUERIES]):
            results.append(f.result())
            (app.DATA/'ballads-100-corrections-2.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
