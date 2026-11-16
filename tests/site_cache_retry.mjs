// Local HTTP truncation E2E: keep the browser's native media cache enabled (no Playwright routes).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch();
 try{
  for(const mode of ['disconnect','short200']){
   if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(mode))continue;
   const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[],requests=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.env.SITE_E2E_URL);await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
   await page.waitForFunction(()=>v.readyState>=3&&!v.seeking);
   const source=await page.evaluate(()=>new URL(S.src,location.href).href),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'site-retry-'));
   let data;
   try{
    fs.writeFileSync(path.join(scratch,'source.mp4'),Buffer.from(await (await fetch(source)).arrayBuffer()));
    // Keep truncation reproducible across fixtures with different keyframe spacing and B-frames.
    execFileSync('ffmpeg',['-v','error','-stream_loop','-1','-i',path.join(scratch,'source.mp4'),'-t','3','-an','-vf','fps=60','-c:v','libx264','-threads','1','-preset','ultrafast','-g','250','-pix_fmt','yuv420p','-movflags','+faststart',path.join(scratch,'clip.mp4')]);
    data=fs.readFileSync(path.join(scratch,'clip.mp4'));
   }finally{for(const f of fs.readdirSync(scratch))fs.unlinkSync(path.join(scratch,f));fs.rmdirSync(scratch);}
   let first=true,complete=false;
   const server=http.createServer((req,res)=>{
    const probe=req.headers.range==='bytes=0-1',head=req.method==='HEAD',broken=first&&!probe&&!head;
    if(broken)first=false;
    if(!broken&&!probe&&!head)complete=true;
    requests.push({url:req.url,method:req.method,range:req.headers.range,broken});
    const body=probe?data.subarray(0,2):broken?data.subarray(0,Math.floor(data.length/2)):data;
    res.writeHead(probe?206:200,{'Content-Type':'video/mp4','Content-Length':mode==='disconnect'&&broken?data.length:body.length,
     'Cache-Control':'public, max-age=31536000, immutable','Access-Control-Allow-Origin':'*',...(probe?{'Content-Range':`bytes 0-1/${data.length}`}:{})});
    if(head){res.end();return;}
    if(broken&&mode==='disconnect'){res.write(body);setTimeout(()=>res.destroy(),100);}else res.end(body);
   });
   await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
   try{
    const url=`http://127.0.0.1:${server.address().port}/clip.mp4?original=kept`;
    await page.evaluate(url=>{ALL[S.id].src=url;load(S.id,false);toggle();},url);
    let state;
    for(const deadline=Date.now()+35000;Date.now()<deadline;){
     state=await page.evaluate(()=>({failed:!!v.parentElement.querySelector('[data-fail]:not([disabled])'),ready:!v.error&&v.readyState>=3&&!v.seeking&&fullyBuffered(v)}));
     if(state.failed||complete&&state.ready)break;
     await page.waitForTimeout(100);
    }
    assert(state.failed||complete&&state.ready,'必須顯示重試提示或已由完整回應自動恢復');
    const before=requests.length,start=Date.now(),manual=await page.evaluate(()=>!!v.parentElement.querySelector('[data-fail]'));
    if(manual)await page.locator('#stage .vid-msg').click();
    await page.waitForFunction(()=>v.readyState>=3&&!v.error&&!v.seeking&&!v._reloading&&fullyBuffered(v),null,{timeout:7000});
    if(!manual)await page.evaluate(()=>{if(v.paused)toggle();});
    await page.waitForFunction(()=>!v.paused,null,{timeout:3000});
    await page.evaluate(()=>{v.playbackRate=1;});
    const t=await page.evaluate(()=>v.currentTime);await page.waitForTimeout(250);
    assert(await page.evaluate(t=>v.currentTime>t+.05,t),'重試後必須實際播放');
    assert.equal(await page.evaluate(()=>new URL(v.src).searchParams.get('original')),'kept','保留來源查詢參數');
    assert.equal(requests.filter(r=>r.broken).length,1,'第一次回應確實截斷');
    assert(requests.some(r=>r.method==='GET'&&!r.broken&&r.range!=='bytes=0-1'),'恢復後確實取得完整影片');
    assert.deepEqual(errors,[]);
    results.push({engine,mode,pass:true,manualRetries:Number(manual),retryMs:Date.now()-start,requests:requests.length,retryRequests:requests.length-before});
   }catch(e){results.push({engine,mode,pass:false,error:e.message,errors,requests});}
   finally{await context.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
   console.log(JSON.stringify(results.at(-1)));
  }
 }finally{await browser.close();}
}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
