"""Preserve a correction archive while fixing release metadata in new imports."""
import json
import shutil
import app
from collect_ballads_100 import PLAN,save
from import_collection import import_source

if __name__=='__main__':
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    text=(app.ROOT/'ballads_100_selection.txt').read_text(encoding='utf-8')
    spec=next(s for s in plan if s['artist']=='V.O.S' and s['decade']=='2020년대')
    if spec['title']=='잘 살고 있다':
        text=text.replace('V.O.S|잘 살고 있다|2023','V.O.S|안녕이라고 말하지마|2023')
        spec.update(title='안녕이라고 말하지마',id='WT6FJaxawvw',reviewed=True)
        import_source(spec)
    archive=app.DATA/'correction-archive';archive.mkdir(exist_ok=True)
    baseline=json.loads((app.DATA/'ballads-100-baseline.json').read_text(encoding='utf-8'))
    oldids={s['id'] for s in baseline}
    with app.db() as c:
        old=c.execute("SELECT * FROM tracks WHERE artist='V.O.S' AND title='잘 살고 있다' AND album='2020년대 인기 발라드'").fetchone()
    if old:
        old=dict(old);assert old['id'] not in oldids
        source=(app.MEDIA/old['filename']).resolve();dest=(archive/old['filename']).resolve()
        assert source.is_relative_to(app.MEDIA.resolve()) and dest.is_relative_to(archive.resolve())
        save(archive/(old['id']+'.json'),old)
        shutil.move(source,dest)
        try:
            with app.db() as c:c.execute('DELETE FROM tracks WHERE id=?',(old['id'],))
        except Exception:
            shutil.move(dest,source);raise
    for artist,title,year in [('노을','문득',2020),('신예영','마지막 사랑',2023)]:
        s=next(s for s in plan if s['artist']==artist and s['title']==title)
        text=text.replace(f"{artist}|{title}|{s['year']}",f'{artist}|{title}|{year}');s['year']=year
        with app.db() as c:t=dict(c.execute('SELECT * FROM tracks WHERE artist=? AND title=?',(artist,title)).fetchone())
        assert t['id'] not in oldids
        path=app.MEDIA/t['filename'];duration,tags=app.metadata(path)
        if tags.get('date')!=str(year):
            shutil.copy2(path,archive/path.name)
            temp=app.DATA/(t['id']+'-year.mp3')
            app.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(path),'-map','0:a:0','-c','copy','-map_metadata','0','-metadata','date='+str(year),str(temp)])
            temp.replace(path)
    save(PLAN,plan)
    (app.ROOT/'ballads_100_selection.txt').write_text(text,encoding='utf-8')
