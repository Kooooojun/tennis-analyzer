// Local HTTP truncation E2E: keep the browser's native media cache enabled (no Playwright routes).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch();
 try{
  for(const [mode,id] of [['disconnect','v'],['short200','v'],['short200','vA']]){
   if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(mode))continue;
   const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[],requests=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.env.SITE_E2E_URL);await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
   await page.waitForFunction(()=>v.readyState>=3&&!v.seeking);
   const source=await page.evaluate(()=>new URL(S.src,location.href).href),data=Buffer.from(await (await fetch(source)).arrayBuffer());
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
    if(id==='v')await page.evaluate(url=>{ALL[S.id].src=url;load(S.id,false);toggle();},url);
    else{
     await page.evaluate(()=>go(DAY,'video'));await page.locator('#vA').scrollIntoViewIfNeeded();
     await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking));
     await page.evaluate(url=>{cmpLoad({...ALL[0],src:url},ALL[1]);cmpStart();},url);
    }
    let state;
    for(const deadline=Date.now()+35000;Date.now()<deadline;){
     state=await page.evaluate(id=>{const x=document.getElementById(id);return {failed:!!x.parentElement.querySelector('[data-fail]:not([disabled])'),ready:!x.error&&x.readyState>=3&&!x.seeking&&fullyBuffered(x)};},id);
     if(state.failed||complete&&state.ready)break;
     await page.waitForTimeout(100);
    }
    assert(state.failed||complete&&state.ready,'必須顯示重試提示或已由完整回應自動恢復');
    const before=requests.length,start=Date.now(),manual=await page.evaluate(id=>!!document.getElementById(id).parentElement.querySelector('[data-fail]'),id);
    if(manual)await page.locator(`#${id}`).locator('..').locator('.vid-msg').click();
    await page.waitForFunction(id=>{const x=document.getElementById(id);return x.readyState>=3&&!x.error&&!x.seeking&&!x._reloading&&fullyBuffered(x);},id,{timeout:7000});
    if(id!=='v'){
     if(manual)assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused]),[true,true],'比較區重試仍須等待同步播放');
     await page.evaluate(()=>cmpStart());
    }else if(!manual)await page.evaluate(()=>{if(v.paused)toggle();});
    await page.waitForFunction(id=>!document.getElementById(id).paused,id,{timeout:3000});
    const t=await page.evaluate(id=>document.getElementById(id).currentTime,id);await page.waitForTimeout(250);
    assert(await page.evaluate(({id,t})=>document.getElementById(id).currentTime>t+.05,{id,t}),'重試後必須實際播放');
    assert.equal(await page.evaluate(id=>new URL(document.getElementById(id).src).searchParams.get('original'),id),'kept','保留來源查詢參數');
    assert.equal(requests.filter(r=>r.broken).length,1,'第一次回應確實截斷');
    assert(requests.some(r=>r.method==='GET'&&!r.broken&&r.range!=='bytes=0-1'),'恢復後確實取得完整影片');
    assert.deepEqual(errors,[]);
    results.push({engine,mode,id,pass:true,manualRetries:Number(manual),retryMs:Date.now()-start,requests:requests.length,retryRequests:requests.length-before});
   }catch(e){results.push({engine,mode,id,pass:false,error:e.message,errors,requests,state:await page.evaluate(()=>[v,vA,vB].map(x=>({id:x.id,ready:x.readyState,time:x.currentTime,duration:x.duration,error:x.error?.code,want:x._want,paused:x.paused,seeking:x.seeking,align:!!x._align,near:x._near,reloading:x._reloading,edge:x._edgeWait})))});}
   finally{await context.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
   console.log(JSON.stringify(results.at(-1)));
  }
 }finally{await browser.close();}
}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
