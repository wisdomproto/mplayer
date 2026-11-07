import {assets,seed} from './generated.js';
const json=(data,status=200,headers={})=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',...headers}});
const validId=id=>/^[a-f0-9]{32}$/.test(id);
const error=(message,status=400)=>{throw Object.assign(new Error(message),{status});};
async function listing(bucket,prefix){let out=[],cursor;do{const page=await bucket.list({prefix,cursor,limit:1000});out.push(...page.objects);cursor=page.truncated?page.cursor:undefined;}while(cursor);return out;}
async function state(bucket){const obj=await bucket.get('state/library.json');return {value:obj?await obj.json():{overrides:{},playlists:seed.playlists},etag:obj?.etag};}
async function update(bucket,modify){for(let i=0;i<5;i++){const s=await state(bucket);const result=modify(s.value);const saved=await bucket.put('state/library.json',JSON.stringify(s.value),{httpMetadata:{contentType:'application/json'},onlyIf:s.etag?{etagMatches:s.etag}:{etagDoesNotMatch:'*'}});if(saved)return result;}error('다른 기기에서 변경 중입니다. 다시 시도해 주세요.',409);}
async function library(bucket){const [s,media,custom]=await Promise.all([state(bucket),listing(bucket,'audio/'),listing(bucket,'tracks/')]);const available=new Set(media.map(o=>o.key.slice(6,-4)));const extras=await Promise.all(custom.map(async o=>(await bucket.get(o.key)).json()));return {tracks:[...seed.tracks,...extras].map(t=>({...t,...s.value.overrides[t.id],available:available.has(t.id)})),playlists:s.value.playlists,uploaded:available.size,total:seed.tracks.length+extras.length};}
async function media(request,bucket,id){const key='audio/'+id+'.mp3';const head=await bucket.head(key);if(!head)return json({error:'음원을 업로드하고 있습니다. 잠시 후 다시 재생해 주세요.'},404);const headers=new Headers({'Content-Type':'audio/mpeg','Accept-Ranges':'bytes','ETag':head.httpEtag,'Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff'});let start=0,end=head.size-1,status=200;const range=request.headers.get('Range');if(range){const m=/^bytes=(\d*)-(\d*)$/.exec(range);if(!m||(!m[1]&&!m[2]))return new Response(null,{status:416,headers:{'Content-Range':`bytes */${head.size}`}});if(!m[1])start=Math.max(0,head.size-Number(m[2]));else{start=Number(m[1]);if(m[2])end=Math.min(end,Number(m[2]));}if(start>end||start>=head.size)return new Response(null,{status:416,headers:{'Content-Range':`bytes */${head.size}`}});status=206;headers.set('Content-Range',`bytes ${start}-${end}/${head.size}`);}headers.set('Content-Length',String(end-start+1));if(request.method==='HEAD')return new Response(null,{status,headers});const obj=await bucket.get(key,{range:{offset:start,length:end-start+1}});return new Response(obj.body,{status,headers});}
export default {async fetch(request,env){try{
 const url=new URL(request.url),p=url.pathname;
 if(!['GET','HEAD'].includes(request.method)){const origin=request.headers.get('Origin');if(origin&&origin!==url.origin)return json({error:'다른 사이트에서의 요청은 허용하지 않습니다.'},403);}
 if((request.method==='GET'||request.method==='HEAD')&&Object.hasOwn(assets,p))return new Response(request.method==='HEAD'?null:assets[p],{headers:{'Content-Type':p.endsWith('.js')?'text/javascript; charset=utf-8':p.endsWith('.css')?'text/css; charset=utf-8':'text/html; charset=utf-8','X-Content-Type-Options':'nosniff','Cache-Control':'no-cache'}});
 const bucket=env.BUCKET;if(!bucket)return json({error:'파일 저장소 연결을 확인하고 있습니다.'},503);
 if(p==='/api/library'&&request.method==='GET')return json(await library(bucket));
 if(p==='/api/jobs')return json([]);
 const id=p.split('/').at(-1);
 if(p.startsWith('/media/')&&validId(id)&&['GET','HEAD'].includes(request.method))return media(request,bucket,id);
 if(p.startsWith('/api/import/')&&request.method==='PUT'&&validId(id)){
  const track=seed.tracks.find(t=>t.id===id);if(!track)return json({error:'알 수 없는 곡입니다.'},404);
  const size=Number(request.headers.get('Content-Length'));if(size!==track.bytes)return json({error:'파일 크기가 원본과 다릅니다.'},400);
  const head=await bucket.head('audio/'+id+'.mp3');if(head?.size===size&&head.customMetadata?.sha256===track.sha256)return json({id,reused:true});
  await bucket.put('audio/'+id+'.mp3',request.body,{httpMetadata:{contentType:'audio/mpeg'},customMetadata:{sha256:track.sha256},sha256:track.sha256});return json({id,bytes:size});
 }
 if(p==='/api/migration'&&request.method==='GET'){const objects=await listing(bucket,'audio/');return json({files:objects.map(o=>({id:o.key.slice(6,-4),bytes:o.size})),expected:seed.tracks.length});}
 if(p==='/api/upload'&&request.method==='POST'){
  const name=url.searchParams.get('name')||'';if(!name.toLowerCase().endsWith('.mp3'))error('웹에서는 MP3 파일을 업로드해 주세요.');
  const size=Number(request.headers.get('Content-Length'));if(!size||size>95*1024*1024)error('MP3 파일은 최대 95MB까지 올릴 수 있습니다.');
  const duration=Number(url.searchParams.get('duration'));if(!Number.isFinite(duration)||duration<=0)error('오디오 길이를 확인하지 못했습니다.');
  const id=crypto.randomUUID().replaceAll('-','');await bucket.put('audio/'+id+'.mp3',request.body,{httpMetadata:{contentType:'audio/mpeg'}});
  await bucket.put('tracks/'+id+'.json',JSON.stringify({id,title:name.replace(/\.mp3$/i,'').slice(0,300),artist:'내 음악',album:'업로드한 음악',duration,filename:id+'.mp3',source:'',liked:0,created:new Date().toISOString()}));return json({id});
 }
 if(request.method==='POST'&&['/api/like','/api/edit','/api/playlists'].includes(p)){
  if(Number(request.headers.get('Content-Length')||0)>1024*1024)error('요청이 너무 큽니다.',413);
  const data=await request.json();
  if(p==='/api/playlists'){
   if(!Array.isArray(data.playlists)||data.playlists.length>200)error('재생목록을 확인해 주세요.');
   const list=data.playlists.map(p=>{if(typeof p.id!=='string'||p.id.length>100||typeof p.name!=='string'||!p.name.trim()||p.name.length>100||!Array.isArray(p.tracks)||p.tracks.length>10000||!p.tracks.every(validId))error('재생목록 형식이 올바르지 않습니다.');return {id:p.id,name:p.name,tracks:[...new Set(p.tracks)]};});
   await update(bucket,s=>{s.playlists=list;});return json({ok:true});
  }
  if(!validId(data.id)||(!seed.tracks.some(t=>t.id===data.id)&&!await bucket.head('tracks/'+data.id+'.json')))error('곡을 찾을 수 없습니다.',404);
  const patch=p==='/api/like'?{liked:!!data.liked}:Object.fromEntries(['title','artist','album'].map(k=>[k,String(data[k]||'').trim().slice(0,300)]));
  if(p==='/api/edit'&&!patch.title)error('제목을 입력해 주세요.');
  await update(bucket,s=>{s.overrides[data.id]={...s.overrides[data.id],...patch};});return json({ok:true});
 }
 if(['/api/download','/api/split','/api/search'].includes(p))return json({error:'이 기능은 PC 앱에서 이용해 주세요. 웹에는 MP3를 업로드할 수 있습니다.'},400);
 return json({error:'찾을 수 없습니다.'},404);
}catch(e){console.error('Request failed:',e.status||500,e.message);return json({error:e.status?e.message:'요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'},e.status||500);}}};
