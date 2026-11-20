// 真實 HTTP／影片 E2E；同一檔可用 SITE_REF 固定 main 做三次對照。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {fixture,watchPlay,playMismatch} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(),results=[],repeats=Number(process.env.SITE_REPEATS||1);
const ready=page=>page.waitForFunction(()=>v.readyState>=3&&!v.seeking&&!v.error);
const select=(page,query)=>page.evaluate(({url,query})=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?case='+Date.now()+'&'+query;load(4,false);},{url:f.url,query});
const replacing=page=>page.waitForFunction(()=>v._fetching,null,{timeout:6500});
const hidden=(page,value)=>page.evaluate(value=>{Object.defineProperty(document,'hidden',{configurable:true,value});document.dispatchEvent(new Event('visibilitychange'));},value);
const cases={
 async S8(page){
  await select(page,'drip=20');await ready(page);
  assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0);
 },
 async S9(page){
  const started=performance.now();await select(page,'nativeHang=always&drip=4&perRequest=1');
  await page.locator('#play').click();
  await page.waitForFunction(()=>v.readyState>=3&&!v.seeking&&!v.paused,null,{timeout:10500});
  const frame=await page.evaluate(()=>v.currentTime);await page.waitForFunction(t=>v.currentTime>t+.05,frame,{timeout:500});
  assert(performance.now()-started<11000,'新 GET 必須十一秒內實際播放');
 },
 async splitPrefix(page){
  const started=performance.now();await select(page,'hang=once&split=1');
  await page.waitForFunction(()=>v.src.includes('_retry')&&v.readyState>=3&&!v.seeking,null,{timeout:14000});
  return {elapsedMs:Math.round(performance.now()-started)};
 },
 async earlyStop(page){
  const started=performance.now();await select(page,'drip=45&dripStop=2000');
  await page.waitForFunction(()=>v.src.includes('_retry')&&v.readyState>=3&&!v.seeking,null,{timeout:16000});
  return {elapsedMs:Math.round(performance.now()-started)};
 },
 async blocked(page){
  await page.evaluate(()=>{v.play=()=>Promise.reject(new DOMException('blocked','NotAllowedError'));});
  await select(page,'hang=always');await page.waitForTimeout(100);await page.clock.runFor(35000);
  assert.equal(await page.locator('#badge').textContent(),'點畫面載入影片');
  assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0);
 },
 async canplayRecoversFailure(page){return recoverFailure(page,'canplay');},
 async seekedRecoversFailure(page){return recoverFailure(page,'seeked');},
 async renewedBufferWait(page){
  const source=await page.evaluate(()=>{cancelPrefetch();window.testReady=2;v._want=v._resume=true;Object.defineProperty(v,'readyState',{configurable:true,get:()=>testReady});return v.src;});
  await page.clock.runFor(600);await page.evaluate(()=>{testReady=4;v.dispatchEvent(new Event('canplay'));});
  await page.clock.runFor(12000);await page.evaluate(()=>{testReady=2;v.dispatchEvent(new Event('waiting'));});
  await page.clock.runFor(1000);
  assert.equal(await page.evaluate(()=>v.src),source,'再次緩衝必須有新的十秒等待時段');
  await page.clock.runFor(9500);
  assert.equal(await page.evaluate(()=>v.src.includes('_retry')),true,'新的等待時段仍必須有停流上限');
 },
 async probingResume(page){
  await select(page,'nativeHang=always&probeOnce=1&drip=4&perRequest=1');
  await page.waitForFunction(()=>v._loader.state==='probing',null,{timeout:6500});
  await hidden(page,true);await page.waitForTimeout(400);await hidden(page,false);
  assert.equal(await page.evaluate(()=>v._loader.state),'loading','已取消探測不能恢復成 probing');
  await page.waitForFunction(()=>v.readyState>=3&&!v.seeking,null,{timeout:9000});
  assert.equal(await page.evaluate(()=>v.src.startsWith('blob:')),true);
 },
 async unknownLengthLimit(page){return capacity(page,true);},
 async knownLengthLimit(page){return capacity(page,false);},
 async metadataSeekStall(page){
  const seen=[];
  await page.evaluate(()=>{window.seekStates=[];for(const type of ['loadedmetadata','seeking'])v.addEventListener(type,()=>seekStates.push({type,ready:v.readyState,seeking:v.seeking}));});
  await select(page,'hang=always&hangBytes=131072&fast=1&drip=1');
  await page.waitForFunction(()=>!!v.parentElement.querySelector('.vid-msg[data-fail]:not([disabled])'),null,{timeout:24500});
  seen.push(...await page.evaluate(()=>seekStates));assert(seen.some(x=>x.type==='loadedmetadata'),'必須真的到 metadata');
  assert(seen.some(x=>x.seeking),'必須真的卡在目標 seek');return {states:seen};
 },
 async lateBlob(page){
  await select(page,'nativeHang=always&drip=29');await replacing(page);
  await page.evaluate(()=>{const native=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'readyState');const until=performance.now()+28000;Object.defineProperty(v,'readyState',{configurable:true,get(){return v.src.startsWith('blob:')&&performance.now()<until?0:native.get.call(v);}});});
  await ready(page);assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0);
 },
 async hiddenNative(page){
  await select(page,'hang=once');await page.waitForTimeout(500);await hidden(page,true);await page.waitForTimeout(800);await hidden(page,false);await page.waitForTimeout(600);
 },
 async hiddenResume(page){
  await select(page,'nativeHang=always&drip=8');await replacing(page);
  await hidden(page,true);await page.waitForTimeout(600);await hidden(page,false);await ready(page);
 },
 async pauseWhileFetching(page){
  await select(page,'nativeHang=always&drip=8');await replacing(page);await page.locator('#play').click();await page.locator('#play').click();await ready(page);
  assert.equal(await page.evaluate(()=>v.paused&&!v._want&&!v._resume),true);
 },
 async obsoletePlayRejection(page){
  await page.evaluate(()=>{const native=v.play.bind(v);let first=true;v.play=()=>{if(first){first=false;return new Promise((resolve,reject)=>window.oldPlayReject=reject);}return native();};});
  await select(page,'nativeHang=always&drip=4&perRequest=1');await replacing(page);await page.locator('#play').click();
  await page.waitForFunction(()=>v.src.startsWith('blob:')&&v.readyState>=3&&!v.seeking&&!v.paused,null,{timeout:6500});
  await page.evaluate(()=>oldPlayReject(new DOMException('old source','NotAllowedError')));await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>v._want&&!v.paused&&!v._blocked),true,'舊來源的 play 拒絕不得暫停新來源');
 },
 async obsoleteProbePlayRejection(page){
  await page.evaluate(()=>{const native=v.play.bind(v);let first=true;v.play=()=>{if(first){first=false;return new Promise((resolve,reject)=>window.oldPlayReject=reject);}return native();};});
  await select(page,'nativeHang=always&drip=4&perRequest=1');await replacing(page);await page.locator('#play').click();
  await page.evaluate(()=>oldPlayReject(new DOMException('old source','NotAllowedError')));await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>v._want&&v._fetching&&!v._blocked),true,'接管中的舊 play 拒絕不得取消下載');
  await page.waitForFunction(()=>v.src.startsWith('blob:')&&v.readyState>=3&&!v.seeking&&!v.paused,null,{timeout:6500});
 },
 async sharedHiddenResume(page){
  await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=always&drip=8&case='+Date.now();go(DAY,'video');cmpLoad(ALL[4],ALL[4]);},f.url);
  await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA._fetching&&vB._fetching,null,{timeout:6500});
  await page.evaluate(()=>{Object.defineProperty(vA,'offsetParent',{configurable:true,value:null});document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForFunction(()=>vB.readyState>=3&&!vB.seeking&&vB.src.startsWith('blob:'),null,{timeout:10000});
  await page.evaluate(()=>{delete vA.offsetParent;document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForFunction(()=>vA.readyState>=3&&!vA.seeking&&vA.src===vB.src);
 },
 async scrollDoesNotSuspend(page){
  await page.setViewportSize({width:390,height:500});
  await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=always&drip=8&case='+Date.now();go(DAY,'video');cmpLoad(ALL[4],ALL[4]);},f.url);
  await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA._fetching&&vB._fetching,null,{timeout:6500});
  await page.evaluate(()=>scrollTo(0,0));await page.waitForFunction(()=>vA._near===false);
  await page.waitForFunction(()=>vA.readyState>=3&&vB.readyState>=3&&!vA.seeking&&!vB.seeking,null,{timeout:10000});
 },
 async deferredPrefetch(page){
  const calls=await page.evaluate(async()=>{cancelPrefetch();load(4,false,true);const old=clipFetch,calls=[];clipFetch=(key,background)=>{if(background)calls.push(key);return old(key,background);};try{vA.dispatchEvent(new Event('progress'));await preloadNeighbors(S);return calls;}finally{clipFetch=old;}});
  assert.deepEqual(calls,[]);await ready(page);
 },
 async overviewPendingSource(page){return pendingSource(page,false);},
 async deferredPendingSource(page){return pendingSource(page,true);},
 async cachedBlobDecoding(page){
  await page.evaluate(async()=>{cancelPrefetch();ALL[4].src+='?cached-decode='+Date.now();await clipFetch(clipSrc(ALL[4]),true);});
  const source=await page.evaluate(()=>{
   const native=v.load.bind(v);
   window.blobLoads=0;window.decodeProgress=e=>e.stopImmediatePropagation();v.addEventListener('progress',decodeProgress,true);Object.defineProperty(v,'readyState',{configurable:true,get:()=>0});
   v.load=()=>{if(v.src.startsWith('blob:'))blobLoads++;return native();};
   load(4,false);return v.src;
  });
  const initialLoads=await page.evaluate(()=>blobLoads);
  assert(source.startsWith('blob:'),'必須命中已完成的片段快取');await page.waitForTimeout(250);await page.clock.runFor(6500);
  assert.equal(await page.evaluate(()=>blobLoads),initialLoads,'已快取 blob 解碼中不得被探測重載');
  assert.equal(await page.evaluate(()=>v.src),source);await page.evaluate(()=>{v.removeEventListener('progress',decodeProgress,true);delete v.readyState;});await ready(page);
  await page.waitForFunction(()=>!v._align&&(!v._loader||v._loader.state==='ready'));
 },
 async secondRecoveryPosition(page){
  const restored=[];
  for(const target of [.8,1.8]){
   await page.evaluate(target=>{hold(v);v.currentTime=target;},target);await ready(page);
   await page.evaluate(()=>{cancelPrefetch();Object.defineProperty(v,'readyState',{configurable:true,value:1});});
   await page.clock.runFor(11000);await page.evaluate(()=>{delete v.readyState;});await ready(page);
   const position=await page.evaluate(()=>v.currentTime);restored.push(position);
   assert(Math.abs(position-target)<1/60,'每次重載必須保存最新位置：'+target+' → '+position);
  }
  return {restored};
 },
 async recoveredFailurePosition(page){
  await recoverFailure(page,'canplay');
  await page.evaluate(()=>{hold(v);v.currentTime=1.8;});await ready(page);
  await page.evaluate(()=>{Object.defineProperty(v,'readyState',{configurable:true,value:1});});
  await page.clock.runFor(11000);await page.evaluate(()=>{delete v.readyState;});await ready(page);
  assert(Math.abs(await page.evaluate(()=>v.currentTime)-1.8)<1/60,'原生自行恢復後亦須消耗舊失敗快照');
 },
 async pausedCurrentFrame(page){return pausedFrame(page,false);},
 async pausedCompareFrame(page){return pausedFrame(page,true);},
 async S7(page){
  const times=[];for(let i=0;i<10;i++){await page.evaluate(()=>{cancelPrefetch();ALL[(S.id+1)%ALL.length].src+='?single='+Date.now();window.stepAt=performance.now();step(1);});await ready(page);times.push(await page.evaluate(()=>performance.now()-stepAt));await page.waitForTimeout(650);}return {stepMs:times};
 },
};
async function pendingSource(page,deferred){
 const requests=[];page.on('request',r=>{if(r.resourceType()==='media'&&new URL(r.url()).pathname===new URL(page.url()).pathname)requests.push(r.url());});
 await page.evaluate(()=>{
  window.pageMediaLoads=0;window.pageMediaPlays=0;
  const pageSource=()=>v.hasAttribute('src')&&new URL(v.getAttribute('src'),location.href).href.split('#')[0]===location.href.split('#')[0],load=v.load.bind(v),play=v.play.bind(v);
  v.load=()=>{if(pageSource())pageMediaLoads++;return load();};v.play=()=>{if(pageSource())pageMediaPlays++;return play();};
 });
 if(deferred){
  await page.evaluate(()=>{load(4,false,true);Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForTimeout(60);assert(await page.evaluate(()=>!!mainLoadTimer),'必須仍在 350 ms 延後載入窗口');await page.clock.runFor(400);
 }else{
  await page.evaluate(()=>go(DAY,'overview'));await page.waitForFunction(()=>TAB==='overview');
  assert(await page.evaluate(()=>{load(4,false);route();return LATER.has(v)&&(!v._loader||v._loader.state==='suspended');}),'必須真的延後到 LATER');
  await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>TAB==='stroke');
 }
 await ready(page);await page.waitForFunction(()=>!v._align&&(!v._loader||v._loader.state!=='suspended'));
 assert.equal(await page.evaluate(()=>S.id),4);assert.deepEqual(requests,[],'不得對頁面 URL 發出媒體請求');
 assert.deepEqual(await page.evaluate(()=>[pageMediaLoads,pageMediaPlays]),[0,0],'不得把網頁本身當成影片載入或播放');
 return {pageMediaRequests:requests.length};
}
async function pausedFrame(page,compare){
 if(compare){await page.evaluate(()=>{go(DAY,'video');cmpLoad(ALL[4],ALL[5]);});await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking&&!x._align));}
 const sources=await page.evaluate(compare=>{cancelPrefetch();const group=compare?[vA,vB]:[v];for(const x of group){hold(x);Object.defineProperty(x,'readyState',{configurable:true,value:2});}return group.map(x=>x.src);},compare);
 await page.clock.runFor(35000);
 assert.deepEqual(await page.evaluate(compare=>(compare?[vA,vB]:[v]).map(x=>x.src),compare),sources,'已有影格的暫停影片不得重載');
 assert.equal(await page.locator(compare?'.duo .vid-msg[data-fail]':'#stage .vid-msg[data-fail]').count(),0);
 assert(await page.evaluate(compare=>(compare?[vA,vB]:[v]).every(x=>x.paused&&!x._want&&!x.seeking),compare));
}
async function recoverFailure(page,event){
 await page.evaluate(()=>{cancelPrefetch();Object.defineProperty(v,'readyState',{configurable:true,value:1});Object.defineProperty(v,'seeking',{configurable:true,value:true});});
 await page.clock.runFor(24000);
 assert.equal(await page.locator('#stage .vid-msg[data-fail]:not([disabled])').count(),1,'必須真的進入可點失敗狀態');
 await page.evaluate(()=>{window.recoveryMetadata=0;v.addEventListener('loadedmetadata',()=>recoveryMetadata++);});
 const source=await page.evaluate(()=>v.src);
 await page.evaluate(event=>{delete v.readyState;delete v.seeking;v.dispatchEvent(new Event(event));},event);
 await page.waitForTimeout(100);
 assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0,'不重設來源的可播事件必須清除失敗提示');
 assert.equal(await page.locator('#stage .vid-msg').evaluate(m=>m.hidden&&m.disabled&&!m.textContent),true);
 await page.clock.runFor(16000);
 assert.equal(await page.evaluate(()=>v.src),source,'已恢復影片不得在舊失敗期限自動重載');
 assert.equal(await page.evaluate(()=>recoveryMetadata),0,'恢復過程不得依賴另一個 loadedmetadata');
}
async function capacity(page,unknown){
 await page.evaluate(()=>cancelPrefetch());
 // 以真實串流超過既有上限；放大每個收到的 chunk 只用於容量閘門，並不建立大 blob。
 await page.evaluate(unknown=>{const native=fetch;window.capacityFetches=0;window.fetch=async(url,options)=>{const response=await native(url,options);if(String(url).includes('limitCase')){capacityFetches++;if(!unknown)return new Response(response.body,{headers:{'Content-Type':'video/mp4','Content-Length':String(CLIP_LIMIT+1)}});const reader=response.body.getReader();return new Response(new ReadableStream({async pull(c){const {done,value}=await reader.read();if(done){c.close();return;}c.enqueue(value);c.enqueue(new Uint8Array(CLIP_LIMIT));},cancel(){return reader.cancel();}}),{headers:{'Content-Type':'video/mp4'}});}return response;};},unknown);
 await select(page,'nativeHang=1&drip='+(unknown?8:15)+'&limitCase=1');await ready(page);
 assert.equal(await page.evaluate(()=>capacityFetches),1,'容量拒絕後同拍 retry 不得重複 probe');
 assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0);
}
try{
 for(const engine of process.env.SITE_ENGINES?.split(',')||['chromium','webkit']){
  const browser=await (engine==='webkit'?webkit:chromium).launch();
  try{for(const [name,test] of Object.entries(cases)){
   if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(name))continue;
   for(let repeat=1;repeat<=repeats;repeat++){
    const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[];let consoleErrors=0,unhandled=null;
    page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')consoleErrors++;});
    await page.addInitScript(()=>{window.unhandled=0;addEventListener('unhandledrejection',()=>window.unhandled++);});await watchPlay(page);
    let before=0;const started=performance.now();let row={engine,case:name,repeat,pass:false};
    try{
     if(['blocked','canplayRecoversFailure','seekedRecoversFailure','renewedBufferWait','overviewPendingSource','deferredPendingSource','cachedBlobDecoding','secondRecoveryPosition','recoveredFailurePosition','pausedCurrentFrame','pausedCompareFrame'].includes(name))await page.clock.install();
     await page.goto(f.url);await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await ready(page);await page.waitForTimeout(650);before=f.events.length;consoleErrors=0;
     Object.assign(row,await test(page));const requests=f.events.slice(before).filter(e=>e.method==='GET');
     const retries=requests.filter(e=>e.query.includes('_retry'));
     if(['S8','lateBlob','probingResume'].includes(name))assert.equal(retries.length,0,'持續滴流或完成 blob 不得重試');
     if(name==='splitPrefix'){const first=retries[0];assert(first&&first.time-started<14500,'不得延長原有停流時限');}
     if(name==='blocked')assert.equal(requests.filter(e=>!e.range||e.query.includes('_retry')).length,0);
     if(['sharedHiddenResume','scrollDoesNotSuspend'].includes(name))assert.equal(requests.filter(e=>e.file.endsWith('/4.mp4')&&!e.range).length,1);
     if(name==='hiddenNative')assert.equal(requests.filter(e=>e.file.endsWith('/4.mp4')&&(!e.range||!e.range.endsWith('-1'))).length,1);
     unhandled=await page.evaluate(()=>window.unhandled);assert.equal(unhandled,0);assert.deepEqual(errors,[]);
     const play=await playMismatch(page);row.playSamples=play.samples;assert.equal(play.count,0,'播放鈕文字必須等於播放意圖：'+JSON.stringify(play.first));row.pass=true;
    }catch(error){row.error=error.message;}
    finally{unhandled=await page.evaluate(()=>window.unhandled).catch(()=>null);row.elapsedMs=Math.round(performance.now()-started);row.consoleErrors=consoleErrors;row.pageErrors=errors;row.unhandled=unhandled;row.requests=f.events.slice(before).map(e=>({...e}));row.gets=row.requests.filter(e=>e.method==='GET').length;row.bytes=row.requests.reduce((n,e)=>n+e.bytes,0);await context.close();}
    results.push(row);console.log(JSON.stringify(row));if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
   }
  }}finally{await browser.close();}
 }
}finally{await f.close();}
process.exitCode=results.some(r=>!r.pass)?1:0;
