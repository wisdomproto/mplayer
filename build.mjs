import {readFileSync,writeFileSync,mkdirSync,copyFileSync} from 'node:fs';
const assets = Object.fromEntries(['index.html','app.js','style.css'].map(name=>['/'+(name==='index.html'?'':name),readFileSync('web/'+name,'utf8')]));
const seed=JSON.parse(readFileSync('library.json','utf8'));
const code=readFileSync('worker/index.js','utf8').replace("import {assets,seed} from './generated.js';",`const assets=${JSON.stringify(assets)};\nconst seed=${JSON.stringify(seed)};`);
mkdirSync('dist/server',{recursive:true});mkdirSync('dist/.openai',{recursive:true});
writeFileSync('dist/server/index.js',code);copyFileSync('.openai/hosting.json','dist/.openai/hosting.json');
console.log('Built Mplayer Worker; '+seed.tracks.length+' tracks; no audio in artifact.');
