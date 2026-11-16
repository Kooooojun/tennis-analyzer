// 合成場次、Range 串流與本機 HTTP/2 反向代理，完全不讀使用者資料。
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import http2 from 'node:http2';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export async function fixture(ref=process.env.SITE_REF){
 const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'site-i93-'));
 const clip=path.join(scratch,'clip.mp4');
 execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','testsrc2=s=640x360:r=60:d=3','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-movflags','+faststart',clip]);
 const media=fs.readFileSync(clip),html=()=>ref?execFileSync('git',['show',`${ref}:web/index.html`]):fs.readFileSync(new URL('../web/index.html',import.meta.url));
 const strokes=Array.from({length:25},(_,id)=>({id,video:'synthetic',src:`sessions/synthetic/clips/${id}.mp4`,n:180,kind:id%3===0?'BH':'FH',drill:'rally',player:'me',clock:`0:${String(id).padStart(2,'0')}`,contact:90,knee:110+id,prep:.5,size:[640,360],open_min:30,contact_h:50}));
 const session={id:'synthetic',label:'合成場次',date:'2026-01-01',players:['me'],sub:'合成資料',camera:'側面',showOpen:true,findings:[],presets:[],strokes};
 const pose=JSON.stringify({frames:Array.from({length:180},()=>Array.from({length:17},(_,i)=>[.3+(i%3)*.1,.2+i*.025,.99]))});
 const events=[];
 if(process.env.SITE_FIXTURE_ROOT){
  const root=process.env.SITE_FIXTURE_ROOT,day=path.join(root,'sessions','synthetic');fs.mkdirSync(path.join(day,'pose'),{recursive:true});fs.mkdirSync(path.join(day,'clips'),{recursive:true});
  fs.writeFileSync(path.join(root,'index.html'),html());fs.writeFileSync(path.join(root,'sessions','manifest.js'),'window.SESSION_IDS=["synthetic"];window.SESSION_VER={synthetic:"test"};');fs.writeFileSync(path.join(root,'sessions','trend.js'),'window.TREND=[];');fs.writeFileSync(path.join(day,'data.js'),`window.SESSIONS=[${JSON.stringify(session)}];`);
  for(const s of strokes){fs.writeFileSync(path.join(day,'pose',`${s.id}.js`),`POSE("synthetic",${s.id},${pose});`);fs.writeFileSync(path.join(day,'clips',`${s.id}.mp4`),media);}
 }
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://fixture'),file=url.pathname;
  res.setHeader('Cache-Control','no-store');
  if(file.endsWith('.mp4')){
   const range=/bytes=(\d+)-(\d*)/.exec(req.headers.range||''),start=range?+range[1]:0,end=range&&range[2]?Math.min(+range[2],media.length-1):media.length-1;
   const hanging=url.searchParams.get('hang')==='always'||url.searchParams.get('hang')==='once'&&!url.searchParams.has('_retry');
   events.push({file,query:url.search,hang:hanging,time:performance.now(),method:req.method});
   res.writeHead(range?206:200,{'Content-Type':'video/mp4','Content-Length':end-start+1,'Accept-Ranges':'bytes',...(range?{'Content-Range':`bytes ${start}-${end}/${media.length}`}:{})});
   if(req.method==='HEAD')res.end();
   else if(hanging){res.write(media.subarray(start,start+64));res.flushHeaders();}
   else res.end(media.subarray(start,end+1));
   return;
  }
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript; charset=utf-8':'text/html; charset=utf-8');
  if(file==='/sessions/manifest.js')res.end('window.SESSION_IDS=["synthetic"];window.SESSION_VER={synthetic:"test"};');
  else if(file==='/sessions/trend.js')res.end('window.TREND=[];');
  else if(file==='/sessions/synthetic/data.js')res.end(`window.SESSIONS=[${JSON.stringify(session)}];`);
  else if(/\/pose\/\d+\.js$/.test(file))res.end(`POSE("synthetic",${path.basename(file,'.js')},${pose});`);
  else if(file==='/'||file==='/index.html')res.end(html());
  else {res.statusCode=404;res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url=`http://127.0.0.1:${server.address().port}/`;
 let proxy;
 return {url,events,media,async h2(){
  const key=path.join(scratch,'key.pem'),cert=path.join(scratch,'cert.pem');
  execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=localhost'],{stdio:'ignore'});
  proxy=http2.createSecureServer({key:fs.readFileSync(key),cert:fs.readFileSync(cert)});
  proxy.on('stream',(stream,headers)=>{
   const upstream=http.request(new URL(headers[':path'],url),{method:headers[':method'],headers:headers.range?{Range:headers.range}:{}},response=>{
    const h={...response.headers,':status':response.statusCode};for(const k of ['connection','keep-alive','transfer-encoding'])delete h[k];
    if(stream.destroyed){response.destroy();return;}stream.respond(h);response.pipe(stream);
   });
   upstream.on('error',()=>{if(!stream.destroyed)stream.close();});stream.on('error',()=>{});stream.on('close',()=>upstream.destroy());upstream.end();
  });
  await new Promise(resolve=>proxy.listen(0,'127.0.0.1',resolve));return `https://127.0.0.1:${proxy.address().port}/`;
 },async close(){if(proxy)await new Promise(resolve=>proxy.close(resolve));server.closeAllConnections();await new Promise(resolve=>server.close(resolve));for(const f of fs.readdirSync(scratch))fs.unlinkSync(path.join(scratch,f));fs.rmdirSync(scratch);}};
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const f=await fixture();if(process.argv.includes('--write-root'))await f.close();else {console.log(f.url);process.on('SIGTERM',async()=>{await f.close();process.exit();});}
}
