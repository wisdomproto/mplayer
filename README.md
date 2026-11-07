# Mplayer

유튜브 뮤직에서 영감을 받은 개인용 로컬 MP3 플레이어입니다. 이승환 음악 검색을 기본으로 시작합니다.

이 저장소에는 소스와 선곡 목록만 포함합니다. MP3 등 미디어, 보관함 DB, 다운로드 기록, 캐시와 인증 정보는 Git에서 제외합니다. R2 음원 저장소 연결은 추후 설정할 예정이며 현재는 로컬 파일을 사용합니다.

## 실행

Windows에서 `start.cmd`를 더블 클릭하거나 다음을 실행하세요.

```powershell
python app.py
```

브라우저에서 http://127.0.0.1:8765 를 엽니다. `start.cmd`는 서버가 준비된 후 브라우저를 열며 서버는 백그라운드에서 실행합니다. 이미 실행 중이면 기존 서버에 연결합니다. 터미널에서 `python app.py`를 실행하는 경우 터미널을 열어 두세요.

필요 도구: Python 3.11 이상, FFmpeg(ffprobe 포함), yt-dlp. 별도 Python 패키지는 필요 없습니다.

```powershell
winget install Gyan.FFmpeg
python -m pip install -U yt-dlp
```

## 사용

- **음악 찾기**: 이승환 등 아티스트·노래로 유튜브 검색 → 가져오기 → MP3 저장.
- **음악 가져오기**: 영상 주소 직접 입력 또는 로컬 MP3/오디오/동영상 파일 선택·드래그.
- **곡별 자르기**: 보관함의 가위 버튼에서 `00:00 제목` 형식으로 시간표를 입력. 각 곡이 별도 MP3로 저장됩니다. 유튜브 영상에 챕터가 있으면 가져오기 완료 후 분할 창에 자동 입력됩니다. 챕터 없는 영상의 곡 경계는 직접 입력해야 합니다.
- **재생**: 이전/다음, 시간 이동, 음량, 음소거, 셔플, 전체·한 곡 반복, 대기열. 스페이스로 재생/정지.
- **관리**: 검색, 좋아요, 곡 정보 수정, 재생목록, MP3 파일 저장.
- **재생목록 일괄 추가**: 보관함에서 검색으로 곡을 좁힌 뒤 `목록 전체를 재생목록에 추가`를 누르면 현재 표시된 곡을 기존 또는 새 재생목록에 한 번에 담습니다. 같은 곡 ID는 중복 추가하지 않습니다.

음원과 곡 정보·좋아요는 기본적으로 `D:/codex-data/Mplayer/data/music/`와 `D:/codex-data/Mplayer/data/library.db`에 저장합니다. 임시 파일과 캐시는 같은 데이터 루트의 `tmp/`, `cache/`를 사용합니다. `MPLAYER_DATA` 환경 변수로 데이터 위치를 바꿀 수 있습니다. 아래 `data/` 경로는 이 데이터 폴더를 뜻합니다. 파일 이름은 충돌을 피하는 고유 ID이며 곡 제목·가수는 MP3 태그와 DB에 보관합니다. 재생목록은 같은 브라우저의 localStorage에 저장됩니다. `data` 폴더를 백업하면 음원과 DB를 보존할 수 있습니다. 외부에 공개하지 않고 localhost에만 바인딩합니다.

유튜브 다운로드는 네트워크·사이트 제한으로 실패할 수 있습니다. 실패 메시지를 표시하며 로그인 쿠키나 우회 기능은 자동 사용하지 않습니다. 다운로드 권한이 있는 콘텐츠를 이용하세요. 파일 업로드와 곡 분할은 인터넷 없이 사용할 수 있습니다. 온라인 글꼴을 불러오지 못하면 시스템 글꼴을 사용합니다.

## 이승환 컬렉션 추가

```powershell
python import_collection.py
```

이승환 채널의 24곡 모음, THE K-POP의 LIVE ON UNPLUGGED 10곡 모음, 개별 뮤직비디오 3편을 가져옵니다. 모음 영상은 게시자가 제공한 챕터 시간으로 잘라 개별 MP3로 저장하며 라이브 버전은 제목과 앨범으로 구분합니다. 같은 출처·제목의 파일이 있으면 길이를 확인하고 건너뜁니다.

영상 정보와 곡별 시작·종료 시간은 `data/sources/<영상 ID>/`에 보관합니다. 원본 오디오는 MP3 변환과 전체 디코딩 검사를 통과한 뒤 삭제합니다. 최종 결과는 `data/collection-import.json`에 기록합니다. 추가 후 브라우저를 새로고침하면 보관함에 표시됩니다.

## 시대별 발라드 추가

```powershell
python import_ballads.py
```

`ballads_catalog.json`의 1980년대·1990년대·2000년대·2010년대·2020년대 선곡을 시대별 100곡씩 가져옵니다. 가수·제목·원곡 발표 연도·시대별 앨범 정보를 태그로 저장하고 기존 파일은 재사용합니다. 시대 구분은 해당 가수의 음원 발표 시기 기준입니다. 리메이크는 해당 가수의 리메이크 발표 연대로 분류하며, 재발매·리마스터·라이브 음원이 포함될 수 있습니다. 가져오기 결과와 출처는 `data/ballads-import.json`에 남습니다.

이번 12곡→50곡 확장의 추가 선곡과 출처는 `expand_ballads.py` 및 `data/ballads-expansion-plan.json`, 처리 결과는 `data/ballads-expansion-import.json`에 기록합니다. 확장 도구는 가수·제목을 정규화하여 이미 보관한 곡을 재사용하고, 기존 재생목록에 일괄 추가할 때는 곡 ID로 중복을 제거합니다.

2010년대·2020년대 100곡의 선곡과 수집은 `import_modern_ballads.py`, 검토한 출처는 `data/modern-ballads-plan.json`, 처리 결과는 `data/modern-ballads-import.json`에 보관합니다. 다운로드 전 기존 190곡의 정보를 `data/modern-ballads-baseline.json`에 저장해 기존 파일과 비교합니다.

50곡→100곡 확장의 선곡은 `ballads_100_selection.txt`, 수집 도구는 `collect_ballads_100.py`입니다. 검토한 영상 출처는 `data/ballads-100-plan.json`, 수집 결과는 `data/ballads-100-import.json`에 보관합니다. 확장 전 290곡은 `data/ballads-100-baseline.json`과 `data/library-before-100.db`로 보존합니다.

## 지대넓얕 팟캐스트

`import_podcasts.py`는 지대넓얕애청자 채널의 방송을 한국어 제목으로 확인한 뒤 회차·부 순서대로 정리합니다. 음악 파일과 별도로 `data/podcasts/`에 출처와 처리 기록을 보관하며, 플레이어용 MP3는 기존 `data/music/`에 저장합니다. 음성은 96kbps 모노 MP3로 저장하고 Podcast 태그와 회차 정보를 붙입니다.

```powershell
python import_podcasts.py --plan --limit 20
python import_podcasts.py --workers 8
```

전체 방송은 채널 목록을 갱신한 뒤 `python import_podcasts.py --plan --all`로 계획하고 가져옵니다. MP3는 전체 디코딩 검사를 통과한 뒤 보관함에 등록하고 원본 오디오는 자동 삭제합니다.

`--limit`은 가져올 방송 파일 수입니다. 한 회가 1부·2부로 나뉘면 각각 한 파일로 셉니다. 다운로드 결과는 `data/podcasts/jidaenulbyat-import.json`에 기록하며, 재실행하면 이미 가져온 출처를 건너뜁니다. 보관함에서 `지대넓얕 팟캐스트`로 검색한 뒤 목록 전체를 같은 이름의 새 재생목록에 추가하면 됩니다.

## 확인

```powershell
python -m unittest discover -s tests -v
node --check web/app.js
```
