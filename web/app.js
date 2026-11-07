const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const audio = $('#audio');
let tracks = [], current = null, queue = [], view = 'home', shuffle = false, repeat = 0, splitId, editId, playlistTarget;
let playlists;
try { playlists = JSON.parse(localStorage.getItem('mplayer-playlists') || '[]'); if (!Array.isArray(playlists)) playlists = []; } catch { playlists = []; }
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => { n = Math.floor(Number(n) || 0); return (n >= 3600 ? Math.floor(n / 3600) + ':' + String(Math.floor(n % 3600 / 60)).padStart(2,'0') : Math.floor(n / 60)) + ':' + String(n % 60).padStart(2,'0'); };
let toastTimer;
function toast(text) { $('#toast').textContent = text; $('#toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 4200); }
async function api(path, data) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || '요청을 처리하지 못했습니다.');
  return result;
}
function guarded(fn) { return async (...args) => { try { await fn(...args); } catch(e) { toast(e.message); } }; }
function savedPlaylists() { localStorage.setItem('mplayer-playlists', JSON.stringify(playlists)); renderPlaylists(); }
function renderPlaylists() {
  $('#playlists').innerHTML = playlists.map(p => `<button class="playlist-item ${view === p.id ? 'active':''}" data-playlist="${esc(p.id)}"><span>♫</span>${esc(p.name)}</button>`).join('');
  $$('#playlists button').forEach(b => b.onclick = () => setView(b.dataset.playlist));
}
function shownTracks() {
  let list = tracks;
  if (view === 'liked') list = list.filter(t => t.liked);
  const p = playlists.find(p => p.id === view);
  if (p) list = p.tracks.map(id => tracks.find(t => t.id === id)).filter(Boolean);
  const q = $('#filter').value.toLowerCase().trim();
  const filtered = list.filter(t => `${t.title} ${t.artist} ${t.album}`.toLowerCase().includes(q));
  if (filtered.length && filtered.every(t => t.album === '지대넓얕 팟캐스트')) {
    const order = t => [Number(t.title.match(/^\d+/)?.[0] || 9999), /번외/.test(t.title) ? 1 : 0, Number(t.title.match(/(\d+)부/)?.[1] || 0)];
    filtered.sort((a,b) => { const x=order(a),y=order(b); return x[0]-y[0] || x[1]-y[1] || x[2]-y[2] || a.title.localeCompare(b.title,'ko',{numeric:true}); });
  }
  return filtered;
}
function row(t, i) {
  return `<div class="track ${current?.id === t.id ? 'current':''}" data-id="${t.id}"><button class="track-number" data-action="play" aria-label="${esc(t.title)} 재생">${current?.id === t.id && !audio.paused ? '♫' : String(i+1).padStart(2,'0')}</button><div class="track-title"><span class="track-cover">♫</span><button class="track-info" data-action="play"><b>${esc(t.title)}</b><small>${esc(t.artist)}</small></button></div><span class="track-album">${esc(t.album)}</span><span class="track-time">${fmt(t.duration)}</span><div class="track-actions"><button class="${t.liked?'liked':''}" data-action="like" aria-label="좋아요">${t.liked?'♥':'♡'}</button><button class="cut" data-action="split" title="곡별로 자르기" aria-label="곡별로 자르기">✂</button><button data-action="playlist" title="재생목록에 추가" aria-label="재생목록에 추가">＋</button><button data-action="edit" title="곡 정보 수정" aria-label="곡 정보 수정">⋯</button><a href="/media/${t.id}" download="${esc(t.title.replace(/[\\/:*?"<>|]/g,'_'))}.mp3" title="MP3 저장" aria-label="MP3 저장">↓</a></div></div>`;
}
function render() {
  const list = shownTracks();
  $('#tracks').innerHTML = list.map(row).join('');
  $('#nav-count').textContent = tracks.length;
  $('#track-count').textContent = list.length;
  $('#empty').hidden = !!list.length;
  $('#empty h3').textContent = tracks.length ? '아직 이곳에 음악이 없어요' : '첫 번째 음악을 담아보세요';
  $('#now-like').textContent = current?.liked ? '♥' : '♡';
  $$('#tracks .track').forEach(el => {
    const t = tracks.find(t => t.id === el.dataset.id);
    el.querySelectorAll('[data-action]').forEach(b => b.onclick = guarded(async () => {
      const action = b.dataset.action;
      if (action === 'play') await playTrack(t, list);
      if (action === 'like') await like(t);
      if (action === 'split') openSplit(t);
      if (action === 'edit') openEdit(t);
      if (action === 'playlist') openPlaylist(t.id);
    }));
    el.ondblclick = guarded(() => playTrack(t, list));
  });
}
async function refresh() {
  const data = await api('library'); tracks = data.tracks;
  if (current) current = tracks.find(t => t.id === current.id) || current;
  render();
}
function setView(next) {
  view = next; $('#filter').value = '';
  $('#home-view').hidden = next !== 'home'; $('#search-view').hidden = next !== 'search';
  $('#library-section').hidden = next === 'search';
  const title = {home:'내 보관함',library:'내 보관함',liked:'좋아요 표시한 곡',search:'음악 찾기'}[next] || playlists.find(p => p.id === next)?.name || '내 보관함';
  $('#library-title').firstChild.textContent = title + ' ';
  $('#breadcrumb').textContent = next === 'home' ? '지금 듣기' : title;
  $$('.nav').forEach(b => b.classList.toggle('active', b.dataset.view === next));
  renderPlaylists(); render(); window.scrollTo(0,0);
}
async function playTrack(track, list) {
  if (list) queue = list.map(t => t.id);
  if (current?.id !== track.id) {
    current = track; audio.src = '/media/' + track.id;
    $('#now-title').textContent = track.title; $('#now-artist').textContent = track.artist;
    $('#duration').textContent = fmt(track.duration);
    if ('mediaSession' in navigator) navigator.mediaSession.metadata = new MediaMetadata({title:track.title,artist:track.artist,album:track.album});
  }
  await audio.play(); render();
}
async function togglePlay() {
  if (!current) {
    const list = shownTracks();
    if (!list.length) return toast('먼저 음악을 가져와 주세요.');
    return playTrack(list[0], list);
  }
  if (audio.paused) await audio.play(); else audio.pause();
}
async function nextTrack(direction=1, auto=false) {
  if (!queue.length) return;
  let i = queue.indexOf(current?.id);
  if (direction < 0 && audio.currentTime > 3) { audio.currentTime = 0; return; }
  if (auto && repeat === 2) { audio.currentTime = 0; return audio.play(); }
  if (shuffle && queue.length > 1) { const options = queue.filter(id => id !== current?.id); i = queue.indexOf(options[Math.floor(Math.random()*options.length)]); }
  else { i += direction; if (i >= queue.length && auto && repeat === 0) return; i = (i + queue.length) % queue.length; }
  const t = tracks.find(t => t.id === queue[i]); if (t) await playTrack(t);
}
async function like(t) { await api('like',{id:t.id,liked:!t.liked}); t.liked = !t.liked; render(); }
audio.volume = .75;
audio.onplay = () => { $('#play').textContent = 'Ⅱ'; $('#play').setAttribute('aria-label','일시정지'); render(); };
audio.onpause = () => { $('#play').textContent = '▶'; $('#play').setAttribute('aria-label','재생'); render(); };
audio.ontimeupdate = () => { $('#elapsed').textContent = fmt(audio.currentTime); $('#seek').value = audio.duration ? audio.currentTime / audio.duration * 100 : 0; };
audio.onloadedmetadata = () => $('#duration').textContent = fmt(audio.duration);
audio.onended = guarded(() => nextTrack(1,true));
audio.onerror = () => toast('오디오를 재생하지 못했습니다. 파일과 서버 상태를 확인해 주세요.');
$('#play').onclick = guarded(togglePlay);
$('#previous').onclick = guarded(() => nextTrack(-1)); $('#next').onclick = guarded(() => nextTrack());
$('#seek').oninput = e => { if (Number.isFinite(audio.duration)) audio.currentTime = e.target.value / 100 * audio.duration; };
$('#volume').oninput = e => { audio.volume = +e.target.value; audio.muted = false; $('#mute').textContent = '♪'; };
$('#mute').onclick = () => { audio.muted = !audio.muted; $('#mute').textContent = audio.muted ? '×' : '♪'; };
$('#now-like').onclick = guarded(async () => { if (current) await like(current); });
$('#shuffle').onclick = () => { shuffle = !shuffle; $('#shuffle').classList.toggle('on',shuffle); toast(shuffle ? '셔플 재생 켜짐' : '셔플 재생 꺼짐'); };
$('#repeat').onclick = () => { repeat = (repeat+1)%3; $('#repeat').classList.toggle('on',!!repeat); $('#repeat').textContent = repeat === 2 ? '↻¹' : '↻'; $('#repeat').title = ['반복: 꺼짐','반복: 전체','반복: 한 곡'][repeat]; toast($('#repeat').title); };
$('#hero-play').onclick = guarded(async () => { const artistTracks=tracks.filter(t=>t.artist==='이승환'); if (!artistTracks.length) return searchArtist('이승환 official'); await playTrack(artistTracks[0],artistTracks); });
$('#queue-button').onclick = () => {
  $('#queue-list').innerHTML = queue.length ? queue.map((id,i) => { const t = tracks.find(t => t.id === id); return t ? `<button class="queue-item" data-id="${id}">${current?.id === id?'♫':i+1} · ${esc(t.title)}<small>${esc(t.artist)}</small></button>`:''; }).join('') : '<p class="muted">곡을 재생하면 대기열이 표시됩니다.</p>';
  $$('#queue-list button').forEach(b => b.onclick = guarded(async () => { await playTrack(tracks.find(t => t.id === b.dataset.id)); $('#queue-dialog').close(); }));
  $('#queue-dialog').showModal();
};
if ('mediaSession' in navigator) { navigator.mediaSession.setActionHandler('play',guarded(togglePlay)); navigator.mediaSession.setActionHandler('pause',()=>audio.pause()); navigator.mediaSession.setActionHandler('nexttrack',guarded(()=>nextTrack())); navigator.mediaSession.setActionHandler('previoustrack',guarded(()=>nextTrack(-1))); }
document.addEventListener('keydown',e => { if (e.code === 'Space' && !['INPUT','TEXTAREA','BUTTON'].includes(document.activeElement.tagName) && !document.querySelector('dialog[open]')) {e.preventDefault();guarded(togglePlay)();} });
$$('.nav').forEach(b => b.onclick = () => setView(b.dataset.view));
$('#filter').oninput = render;
$('#open-import').onclick = () => $('#import-dialog').showModal();
$$('[data-tab]').forEach(b => b.onclick = () => { $$('[data-tab]').forEach(x => x.classList.toggle('selected',x===b)); $('#youtube-form').hidden = b.dataset.tab !== 'youtube'; $('#local-form').hidden = b.dataset.tab !== 'local'; });
$('#youtube-form').onsubmit = guarded(async e => {
  e.preventDefault(); const b = e.target.querySelector('button[type=submit]'); b.disabled = true;
  try { await api('download',Object.fromEntries(new FormData(e.target))); toast('음원을 가져오는 중입니다. 완료되면 보관함에 추가됩니다.'); await pollJobs(); } finally { b.disabled = false; }
});
async function upload(files) {
  for (const file of files) {
    if (file.size > 512*1024*1024) {toast(file.name + ': 512MB를 초과했습니다.');continue;}
    toast(file.name + ' 가져오는 중…');
    const response = await fetch('/api/upload?name='+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
    const result = await response.json(); if (!response.ok) throw Error(result.error);
  }
  await refresh(); toast('음악을 보관함에 저장했습니다.'); $('#import-dialog').close(); $('#file-input').value = '';
}
$('#file-input').onchange = guarded(e => upload(e.target.files));
$('#drop-zone').ondragover = e => {e.preventDefault();e.currentTarget.style.borderColor='#d5f480';};
$('#drop-zone').ondragleave = e => e.currentTarget.style.borderColor='';
$('#drop-zone').ondrop = guarded(async e => {e.preventDefault();e.currentTarget.style.borderColor='';await upload(e.dataTransfer.files);});
let searchSerial = 0;
async function search() {
  const q = $('#search-query').value.trim(); if (!q) return;
  const serial = ++searchSerial;
  $('#search-results').innerHTML = '<p class="muted">유튜브에서 음악을 찾고 있습니다…</p>';
  try {
    const results = await api('search?q='+encodeURIComponent(q)); if (serial !== searchSerial) return;
    $('#search-results').innerHTML = results.length ? results.map((r,i) => `<article class="result">${/^[\w-]{11}$/.test(r.video_id)?`<img src="https://i.ytimg.com/vi/${r.video_id}/mqdefault.jpg" alt="" loading="lazy">`:''}<div><h3>${esc(r.title)}</h3><p>${esc(r.channel)} · ${fmt(r.duration)}</p><a href="https://www.youtube.com/watch?v=${encodeURIComponent(r.video_id)}" target="_blank" rel="noopener noreferrer">유튜브에서 보기 ↗</a></div><button class="outline" data-index="${i}">↓ 가져오기</button></article>`).join('') : '<p class="muted">검색 결과가 없습니다.</p>';
    $$('#search-results button').forEach(b => b.onclick = () => { const r = results[+b.dataset.index]; $('#youtube-form').elements.url.value=r.url; $('#youtube-form').elements.title.value=r.title; $$('[data-tab]')[0].click(); $('#import-dialog').showModal(); });
  } catch(e) {if(serial === searchSerial) $('#search-results').innerHTML = `<p class="muted">검색하지 못했습니다: ${esc(e.message)}</p>`;}
}
function searchArtist(q) {setView('search'); $('#search-query').value=q; search();}
$('#search-form').onsubmit = e => {e.preventDefault();search();};
$('#artist-search').onclick = $('#empty-search').onclick = () => searchArtist('이승환 official');
$$('.mood').forEach(b => b.onclick = () => searchArtist(b.dataset.query));
function openSplit(t, chapters='') { splitId = t.id; $('#split-source').textContent = `${t.title} · ${fmt(t.duration)}`; $('#chapters').value = chapters; $('#split-dialog').showModal(); }
$('#split-form').onsubmit = guarded(async e => {
  e.preventDefault(); const b = e.target.querySelector('button'); b.disabled = true; b.textContent='MP3로 나누는 중…';
  try {const result = await api('split',{id:splitId,chapters:$('#chapters').value}); await refresh(); $('#split-dialog').close(); toast(result.ids.length+'곡을 개별 MP3로 저장했습니다.');}
  finally {b.disabled=false;b.textContent='✂ 개별 MP3로 저장';}
});
function openEdit(t) { editId=t.id; ['title','artist','album'].forEach(k => $('#edit-form').elements[k].value=t[k]); $('#edit-dialog').showModal(); }
$('#edit-form').onsubmit = guarded(async e => { e.preventDefault();await api('edit',{id:editId,...Object.fromEntries(new FormData(e.target))});await refresh();if(current?.id===editId){$('#now-title').textContent=current.title;$('#now-artist').textContent=current.artist;}$('#edit-dialog').close();toast('곡 정보를 수정했습니다.'); });
function openPlaylist(target=null) {
  playlistTarget=target ? [...new Set(Array.isArray(target)?target:[target])] : [];
  $('#playlist-dialog-title').textContent=playlistTarget.length?`${playlistTarget.length}곡을 재생목록에 추가`:'재생목록 만들기'; $('#playlist-name').value='';
  $('#playlist-choices').innerHTML=playlistTarget.length?playlists.map(p=>`<button data-id="${p.id}">♫ ${esc(p.name)} ${playlistTarget.every(id=>p.tracks.includes(id))?'✓':''}</button>`).join(''):'';
  $$('#playlist-choices button').forEach(b=>b.onclick=()=>{const p=playlists.find(p=>p.id===b.dataset.id);p.tracks=[...new Set([...p.tracks,...playlistTarget])];savedPlaylists();render();$('#playlist-dialog').close();toast(`${playlistTarget.length}곡을 재생목록에 추가했습니다.`);});
  $('#playlist-dialog').showModal();
}
$('#new-playlist').onclick=()=>openPlaylist();
$('#playlist-form').onsubmit=e=>{e.preventDefault();const name=$('#playlist-name').value.trim();if(!name)return;playlists.push({id:'p'+crypto.randomUUID(),name,tracks:[...playlistTarget]});savedPlaylists();$('#playlist-dialog').close();toast('재생목록을 만들었습니다.');};
const bulkButton=document.createElement('button');
bulkButton.className='outline';bulkButton.id='add-visible-playlist';bulkButton.textContent='목록 전체를 재생목록에 추가';
$('#library-section .section-heading').append(bulkButton);
bulkButton.onclick=()=>{const ids=shownTracks().map(t=>t.id);if(ids.length)openPlaylist(ids);else toast('추가할 곡이 없습니다.');};
const completedJobs = new Set();
async function pollJobs() {
  try {
    const jobs = await api('jobs');
    $('#jobs').innerHTML = jobs.map(j=>`<div class="job ${esc(j.status)}">${j.status==='working'?'◌ ':j.status==='done'?'✓ ':'! '}${esc(j.message)}${j.status==='done'?`<button data-job="${j.id}">저장한 음원 곡별로 자르기 ↗</button>`:''}</div>`).join('');
    $$('#jobs [data-job]').forEach(b=>b.onclick=()=>{const j=jobs.find(j=>j.id===b.dataset.job);const t=tracks.find(t=>t.id===j.track_id);if(t){$('#import-dialog').close();openSplit(t,j.chapters.map(c=>`${fmt(c.start_time)} ${c.title}`).join('\n'));}});
    for(const j of jobs) if(j.status!=='working'&&!completedJobs.has(j.id)){completedJobs.add(j.id);if(j.status==='done'){await refresh();toast('MP3를 보관함에 저장했습니다.');}else toast('다운로드 실패 — 가져오기 창에서 내용을 확인해 주세요.');}
  } catch(e) { /* Keep player usable during a transient connection failure. */ }
}
renderPlaylists(); guarded(refresh)(); pollJobs(); setInterval(pollJobs,4000);
