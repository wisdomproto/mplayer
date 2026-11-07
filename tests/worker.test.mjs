import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../dist/server/index.js';
class Bucket {
 constructor(){this.files=new Map();this.version=0;}
 async put(key,value,options={}){const old=this.files.get(key);if(options.onlyIf?.etagMatches&&old?.etag!==options.onlyIf.etagMatches)return null;if(options.onlyIf?.etagDoesNotMatch==='*'&&old)return null;const bytes=typeof value==='string'?new TextEncoder().encode(value):new Uint8Array(await new Response(value).arrayBuffer());const etag=String(++this.version);const obj={key,size:bytes.length,etag,httpEtag:'"'+etag+'"',customMetadata:options.customMetadata,bytes,json:async()=>JSON.parse(new TextDecoder().decode(bytes))};this.files.set(key,obj);return obj;}
 async head(key){return this.files.get(key)||null;}
 async get(key,options={}){const file=this.files.get(key);if(!file)return null;const {offset=0,length=file.size}=options.range||{};return {...file,body:file.bytes.slice(offset,offset+length)};}
 async list({prefix}){return {objects:[...this.files.values()].filter(o=>o.key.startsWith(prefix)),truncated:false};}
}
const req=(path,options={})=>new Request('https://example.test'+path,options);
test('R2 media supports prefix, suffix, end clamping and invalid ranges',async()=>{
 const BUCKET=new Bucket(),id='a'.repeat(32);await BUCKET.put('audio/'+id+'.mp3','0123456789');
 for(const [range,status,expected] of [['bytes=0-3',206,'0123'],['bytes=-3',206,'789'],['bytes=8-99',206,'89'],['bytes=10-',416,''],['bytes=-0',416,'']]){
  const r=await worker.fetch(req('/media/'+id,{headers:{Range:range}}),{BUCKET});assert.equal(r.status,status);assert.equal(await r.text(),expected);
 }
 const head=await worker.fetch(req('/media/'+id,{method:'HEAD'}),{BUCKET});assert.equal(head.headers.get('Content-Length'),'10');assert.equal(await head.text(),'');
});
test('library seeded playlists survive edits and cross-origin writes are rejected',async()=>{
 const BUCKET=new Bucket();let r=await worker.fetch(req('/api/library'),{BUCKET});const initial=await r.json();assert.equal(initial.tracks.length,854);assert.deepEqual(initial.playlists.map(p=>p.tracks.length),[40,100,100,100,100,100,314]);
 r=await worker.fetch(req('/api/like',{method:'POST',headers:{Origin:'https://evil.test'},body:'{}'}),{BUCKET});assert.equal(r.status,403);
 const id=initial.tracks[0].id;
 r=await worker.fetch(req('/api/like',{method:'POST',body:JSON.stringify({id,liked:true})}),{BUCKET});assert.equal(r.status,200);
 r=await worker.fetch(req('/api/library'),{BUCKET});assert.equal((await r.json()).tracks.find(t=>t.id===id).liked,true);
 r=await worker.fetch(req('/api/playlists',{method:'POST',body:JSON.stringify({playlists:[{id:'test',name:'My collection',tracks:[id,id]}]})}),{BUCKET});assert.equal(r.status,200);
 r=await worker.fetch(req('/api/library'),{BUCKET});assert.deepEqual((await r.json()).playlists,[{id:'test',name:'My collection',tracks:[id]}]);
});
