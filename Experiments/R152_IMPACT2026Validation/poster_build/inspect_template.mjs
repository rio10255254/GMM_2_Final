import fs from 'node:fs/promises';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const source='C:/Users/Rio/OneDrive/學業/碩班/論文/投稿/IMPACT2026/4. Poster_Sample_2026 (2).pptx';
const dir=new URL('.',import.meta.url);
const deck=await PresentationFile.importPptx(await FileBlob.load(source));
const snap=await deck.inspect({kind:'slide,textbox,shape,image,layout',maxChars:25000});
await fs.writeFile(new URL('template_inspect.ndjson',dir),snap.ndjson);
console.log(snap.ndjson);
await fs.writeFile(new URL('template_proto.json',dir),JSON.stringify(deck.toProto()));
const s=deck.slides.getItem(0);const l=await s.export({format:'layout'});await fs.writeFile(new URL('template_layout.json',dir),await l.text());
try {const p=await deck.export({slide:s,format:'png',scale:.4});await fs.writeFile(new URL('template_artifact.png',dir),new Uint8Array(await p.arrayBuffer()));}catch(e){console.log('Preview:',e.message)}
console.log(deck.help('*',{search:'delete remove slideSize shape collection',include:['index','notes'],maxChars:5000}));
