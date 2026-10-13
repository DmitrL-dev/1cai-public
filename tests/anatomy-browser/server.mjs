import http from 'node:http';
import {readFile, realpath} from 'node:fs/promises';
import path from 'node:path';
const root=await realpath(process.env.ATLAS_DIST||'../../tools/anatomy-atlas/dist');
const files=new Set(['index.html','source-texts.json','ANATOMY-LICENSE.txt']);
const server=http.createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://127.0.0.1').pathname;
  const name=pathname==='/'?'index.html':pathname.slice(1);
  if(!files.has(name)||!['GET','HEAD'].includes(req.method)){res.writeHead(404);res.end();return}
  try{const body=await readFile(path.join(root,name));res.writeHead(200,{'Content-Type':name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.json')?'application/json; charset=utf-8':'text/plain','Cache-Control':'no-store'});res.end(req.method==='HEAD'?undefined:body)}catch{res.writeHead(404);res.end()}
});
server.listen(4179,'127.0.0.1');
process.on('SIGTERM',()=>server.close());process.on('SIGINT',()=>server.close());
