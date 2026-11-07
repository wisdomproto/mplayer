"""Apply reviewed source and release-era corrections before importing."""
import json
import app
from collect_ballads_100 import PLAN, save, selection
from expand_ballads import key

REPLACE={
 ('이문세','이 밤에 머물 수 있는 건'):('조용필','상처',1985,'fK6kSIMscRc'),
 ('변진섭','너의 마음이 슬픔으로 느껴질 때'):('임병수','약속',1984,'_YxIm3-VTxo'),
 ('강승모','무정블루스'):('강승모','무정 부르스',1984,'jerTNNW5X7A'),
 ('김민종','영원한 사랑'):('김민종','하얀 그리움',1993,'rOaAZ903KOE'),
 ('김성호','회상'):('장혜진','1994년 어느 늦은 밤',1994,'LZEggT36REM'),
 ('김필','그대 없는 밤에'):('김필','나의 별이 돼주오',2023,'QJFLF1qRbR4'),
 ('신용재','너만 있으면'):('2F','너만, 너만',2022,'J37dJ6yc-gU'),
 ('경서예지','너도 나만큼 아팠으면 좋겠어'):('김대명','가을 우체국 앞에서',2021,'cCyJNklLauw'),
 ('경서예지','다시 그대를 사랑한다면'):('정승환','별',2021,'mtFi1dDelCs'),
 ('김민석','사랑동화'):('멜로망스','찬란한 하루',2023,'p_dbjlEe83Y'),
 ('첸','안녕'):('첸','사라지고 있어',2022,'tUEraaV5inc'),
 ('순순희','참 많이 사랑했다'):('순순희(기태)','그대가 내 안에 박혔다',2023,'yFu2sJQgOas'),
}
SOURCES={
 ('산울림','회상'):'0bG8lTKuRGU',('김현식','우리 이제'):'vcqx__ggqL4',
 ('김현식','골목길'):'izilbKMRoYQ',('김현철','그대 안의 블루'):'reoXV8SRiuU',
 ('신승훈','오랜 이별뒤에'):'AeoXacl2Q44',('이승철','방황'):'PmhsD15xLFU',
 ('김장훈','나와 같다면'):'KrJmJ_zT5ak',('이수영','I Believe'):'qDUW-4e7qQE',
 ('임창정','소주 한잔'):'sF9sv9lT83A',('먼데이 키즈','Bye Bye Bye'):'X0I_4cQhN0Q',
 ('조성모','피아노'):'0bKFp7J4osU',('휘성','다시 만난 날'):'1pQG5WXZjhg',
 ('휘성','With Me'):'O0z7yy2XGdU',('휘성','불치병'):'IVq4eRmynMk',
 ('플라이 투 더 스카이','남자답게'):'jdNceSXJTZA',
 ('나얼','같은 시간 속의 너'):'uNPWcM0yevw',('성시경','잊지 말기로 해'):'yDR00abqT2E',
 ('벤','꿈처럼'):'ztOFvSDXQU0',('장범준','노래방에서'):'BUzI-awsi1s',
 ('임재범','사랑'):'xsOHwAS8VZs',('디오','별 떨어진다'):'5vmJ_wq2NeA',
}

if __name__=='__main__':
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    replacements={key(*k):v for k,v in REPLACE.items()}
    sources={key(*k):v for k,v in SOURCES.items()}
    text=(app.ROOT/'ballads_100_selection.txt').read_text(encoding='utf-8')
    for s in plan:
        k=key(s['artist'],s['title'])
        if k in replacements:
            a,t,y,vid=replacements[k]
            text=text.replace(f"{s['artist']}|{s['title']}|{s['year']}",f'{a}|{t}|{y}')
            s.update(artist=a,title=t,year=y,id=vid,reviewed=True)
        elif k in sources:s.update(id=sources[k],reviewed=True)
        if s['artist']=='태연' and s['title']=='어른아이':
            text=text.replace('태연|어른아이|2020','태연|어른아이|2022');s['year']=2022
    assert len(plan)==250 and all(s.get('id') for s in plan)
    assert len({s['id'] for s in plan})==250
    assert len({key(s['artist'],s['title']) for s in plan})==250
    baseline=json.loads((app.DATA/'ballads-100-baseline.json').read_text(encoding='utf-8'))
    assert not {key(s['artist'],s['title']) for s in plan}&{key(s['artist'],s['title']) for s in baseline}
    save(PLAN,plan)
    (app.ROOT/'ballads_100_selection.txt').write_text(text,encoding='utf-8')
    assert len(selection())==250
    print('Reviewed 250 unique new tracks')
