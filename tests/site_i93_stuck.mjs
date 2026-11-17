// 每案使用乾淨 context；可用 SITE_REF=origin/main 對同一測試做紅綠對照。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(),results=[];
const engines=process.env.SITE_ENGINES?.split(',')||['chromium','chrome','webkit'];
const h2=await f.h2();
try{
 for(const engine of engines){
  const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,...(engine==='chrome'?{channel:'chrome'}:{})});
  try{
   for(const [name,test] of Object.entries({
    async poseTimeout(page){
     const requests=[];await page.route('**/pose/4.js*',route=>{requests.push(route.request().url());if(requests.length===1)return;return route.continue();});
     await page.evaluate(()=>load(4,false));await page.waitForFunction(()=>S.id===4);
     await page.waitForFunction(()=>!!S.frames,null,{timeout:15500});
     assert.equal(requests.length,2);assert(new URL(requests[1]).searchParams.has('_retry'));
    },
    async poseLongRetryStatus(page){
     let allow=false,count=0;await page.route('**/pose/4.js*',route=>{count++;if(allow)return route.continue();});
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>{
      window.poseDraws=0;const ctx=$('cv').getContext('2d'),stroke=ctx.stroke.bind(ctx);ctx.stroke=()=>{if(S.id===4&&S.frames)poseDraws++;stroke();};load(4,false);
     });await started;
     await page.clock.runFor(8500);
     assert.equal(await page.locator('#stage .pose-msg').isVisible(),true);
     const text=await page.locator('#stage .pose-msg').textContent();assert.match(text,/骨架載不到，重試中（1\/3）/);
     const live=page.locator('#stage .pose-live');assert.equal(await live.textContent(),text);assert.equal(await live.getAttribute('role'),'status');assert.equal(await live.getAttribute('aria-live'),'polite');
     await page.clock.runFor(27000);allow=true;await page.clock.runFor(5500);
     await page.waitForFunction(()=>!!S.frames&&poseDraws>0,null,{timeout:1500});
     assert.equal(count,4);assert.equal(await page.locator('#stage .pose-msg').isVisible(),false);assert.equal(await live.textContent(),'');
     return {firstRetryStatusMs:8500,recoveredByMs:41000,requests:count};
    },
    async probeSuspendNoRestart(page){
     await replacing(page,20);
     const state=await page.evaluate(async()=>{
      window.suspendedLoads=0;const native=v.load.bind(v);v.load=()=>{suspendedLoads++;native();};
      Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));
      await new Promise(r=>setTimeout(r,600));return {loads:suspendedLoads,source:v.src,fetching:!!v._fetching};
     });
     console.log(JSON.stringify({measurement:{engine,case:'probeSuspendNoRestart',...state}}));
     assert.equal(state.loads,0,'隱藏時不得重新 load 原生影片');
    },
    async probeFailureFreshAttempt(page){
     const started=performance.now(),before=f.events.length;
     await replacing(page,45);
     await page.waitForTimeout(Math.max(0,26000-(performance.now()-started)));
     await page.evaluate(()=>CLIPS.get(v._clipKey).controller.abort());
     await page.waitForTimeout(7000);
     const state=await page.evaluate(()=>({source:v.src,failed:!!v.parentElement.querySelector('.vid-msg[data-fail]')}));
     const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4'));
     console.log(JSON.stringify({measurement:{engine,case:'probeFailureFreshAttempt',...state,requests}}));
     assert(requests.some(e=>e.query.includes('_retry')),'下載失敗後的新來源必須繞過壞快取');
     assert.equal(state.failed,false,'新來源不能繼承舊的三十秒期限');
    },
    async probeBlobNativePause(page){
     await replacing(page,4);await page.locator('#play').click();
     await page.waitForFunction(()=>v.src.startsWith('blob:')&&v.readyState>=3&&!v.seeking&&!v.paused,null,{timeout:6500});
     await page.evaluate(()=>v.pause());await page.waitForTimeout(150);
     const state=await page.evaluate(()=>({want:!!v._want,resume:!!v._resume,reloading:!!v._reloading,button:$('play').textContent}));
     console.log(JSON.stringify({measurement:{engine,case:'probeBlobNativePause',...state}}));
     assert.equal(state.reloading,false,'blob 可播後必須離開重載狀態');
     assert.equal(state.want,false,'原生 pause 必須清除播放意圖');assert(state.button.includes('▶'));
    },
    async probeBlocksPrefetch(page){
     await replacing(page,20);
     const calls=await page.evaluate(async()=>{
      cancelPrefetch();prefetchFor=null;const calls=[],native=clipFetch;
      clipFetch=(key,background)=>{if(background)calls.push(key);return native(key,background);};
      try{await preloadNeighbors(S);return calls;}finally{clipFetch=native;}
     });
     console.log(JSON.stringify({measurement:{engine,case:'probeBlocksPrefetch',calls}}));
     assert.deepEqual(calls,[],'前景替代下載中不得啟動鄰拍預載');
    },
    async probeKeepsRetryUrl(page){
     const probes=[];
     page.on('request',r=>{if(r.resourceType()==='fetch'&&r.url().includes('nativeHang=always'))probes.push(r.url());});
     await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=always&hang=once&drip=4&case='+Date.now();load(4,false);},f.url);
     await page.waitForFunction(()=>v.src.includes('_retry'),null,{timeout:13500});
     const deadline=Date.now()+6000;while(probes.length<2&&Date.now()<deadline)await page.waitForTimeout(100);
     console.log(JSON.stringify({measurement:{engine,case:'probeKeepsRetryUrl',probes}}));
     assert(probes.length>=2,'必須走過重試後的替代下載');
     assert(new URL(probes[1]).searchParams.has('_retry'),'第二次替代 GET 必須保留原生重試的 URL');
    },
    async nativeConnectionStuck(page){
     const before=f.events.length,start=performance.now();
     await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=1&drip=4&perRequest=1&case='+Date.now();load(4,false);},f.url);
     await page.waitForFunction(()=>v._fetching,null,{timeout:6500});
     await page.locator('#play').click();
     await page.waitForFunction(()=>v.readyState>=3&&!v.seeking&&!v.paused,null,{timeout:6500});
     const frame=await page.evaluate(()=>v.currentTime);
     await page.waitForFunction(t=>v.currentTime>t+.05,frame,{timeout:2500});
     const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4'));
     assert(requests.some(e=>e.range&&e.hang),'必須真的卡住原生 Range 連線');
     assert(requests.some(e=>!e.range&&!e.hang&&e.chunks>0),'獨立 GET 必須正常傳送資料');
     assert(performance.now()-start<11000,'十一秒內必須恢復實際播放');
     assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0);
     return {elapsedMs:Math.round(performance.now()-start),source:await page.evaluate(()=>v.src.startsWith('blob:')?'blob':'native'),requests};
    },
    async byteFallbackShared(page){
     const before=f.events.length;
     await page.evaluate(url=>{
      ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=1&drip=8&case='+Date.now();
      go(DAY_KEYS[0],'video');cmpLoad(ALL[4],ALL[4]);
     },f.url);
     await page.locator('#vA').scrollIntoViewIfNeeded();
     await page.waitForFunction(()=>vA._fetching&&vB._fetching&&CLIPS.get(vB._clipKey)?.bytes>0,null,{timeout:6500});
     await page.evaluate(()=>{resetClip(vA,clipSrc(ALL[8]));setClip(vA,ALL[8],()=>vA.pause());});
     await page.waitForFunction(()=>vB.readyState>=3&&!vB.seeking&&vB.src.startsWith('blob:'),null,{timeout:10000});
     const state=await page.evaluate(()=>{const e=CLIPS.get(vB._clipKey);return {cached:e?.url===vB.src,bytes:e?.size,limit:CLIP_LIMIT};});
     assert(state.cached&&state.bytes>0&&state.bytes<=state.limit,'離開一側不能取消另一側共用的有界快取下載');
     const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4'));
     assert.equal(requests.filter(e=>!e.range).length,1,'兩側應共用一條替代 GET');
     return state;
    },
    async byteFallbackRejected(page){
     let fetches=0;
     await page.route('**/*nativeHang*',route=>{
      if(route.request().resourceType()!=='fetch')return route.continue();
      fetches++;return route.fulfill({status:200,contentType:'text/html',body:'<html>unavailable</html>'});
     });
     const before=f.events.length,start=performance.now();
     await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=1&drip=4&perRequest=1&case='+Date.now();load(4,false);},f.url);
     await page.waitForFunction(()=>v.src.includes('_retry'),null,{timeout:13000});
     const fetchesBeforeRetry=fetches;
     await page.waitForFunction(()=>v.readyState>=3&&!v.seeking,null,{timeout:6000});
     const retry=f.events.slice(before).find(e=>e.file.endsWith('/4.mp4')&&e.query.includes('_retry'));
     assert.equal(fetchesBeforeRetry,1,'同一次載入遇到無效回應不能重複探測');
     assert(retry&&retry.time-start<13000,'替代下載失敗仍須約十秒原生重試');
     assert.equal(await page.evaluate(()=>v._fetching),false);
     return {fetches,fetchesBeforeRetry,retryMs:Math.round(retry.time-start)};
    },
    async slowByteProgress(page){
     const before=f.events.length;
     await page.evaluate(url=>{
      window.slowProgress=0;window.slowMetadataMs=0;window.slowStates=[];const started=performance.now();
      const sample=type=>slowStates.push({ms:Math.round(performance.now()-started),type,readyState:v.readyState,buffered:v.buffered.length?v.buffered.end(v.buffered.length-1):0});
      const timer=setInterval(()=>sample('sample'),500);
      v.addEventListener('progress',e=>{sample(e.isTrusted?'trusted':'untrusted');if(e.isTrusted)slowProgress++;});
      v.addEventListener('loadedmetadata',()=>{slowMetadataMs=performance.now()-started;clearInterval(timer);},{once:true});
      ALL[4].src=url+'sessions/synthetic/clips/4.mp4?drip=20&case='+Date.now();load(4,false);
     },f.url);
     await page.waitForFunction(()=>v.readyState>=3&&!v.seeking,null,{timeout:27500});
     const state=await page.evaluate(()=>({metadataMs:Math.round(slowMetadataMs),progress:slowProgress,states:slowStates,blob:v.src.startsWith('blob:'),cached:CLIPS.get(v._clipKey)?.url===v.src}));
     const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4')),retries=requests.filter(e=>e.query.includes('_retry')).length;
     assert(state.metadataMs>=18000,`metadata 過早：${state.metadataMs}`);assert(requests.reduce((n,e)=>n+e.chunks,0)>=40);
     if(engine!=='webkit')assert(state.progress>0,'Chromium 必須有可信任下載進度');
     const byteRatio=requests.reduce((n,e)=>n+e.bytes,0)/f.media.length;
     assert(byteRatio<1.35,`不得維持雙倍下載：${byteRatio.toFixed(2)} 倍`);
     if(engine==='webkit')assert(state.blob&&state.cached,'替代下載必須實際成為有容量上限的快取影片');
     else assert.equal(state.blob,false,'原生有進度時保留串流');
     assert.equal(await page.locator('#stage .vid-msg[data-fail]').count(),0,'滴流完成不得留下失敗提示');
     console.log(JSON.stringify({measurement:{...state,retries,requests:requests.length,chunks:requests.map(e=>e.chunks)}}));
     assert.equal(retries,0,'持續下載時不得重載');return {...state,retries,byteRatio,requests:requests.length,chunks:requests.reduce((n,e)=>n+e.chunks,0)};
    },
    async slowByteCeiling(page){
     const before=f.events.length,start=performance.now();
     await page.evaluate(url=>{
      window.ceilingProgress=0;v.addEventListener('progress',e=>{if(e.isTrusted)ceilingProgress++;});
      ALL[4].src=url+'sessions/synthetic/clips/4.mp4?drip=45&case='+Date.now();load(4,false);
     },f.url);
     await page.waitForTimeout(22000);
     const failed=()=>page.locator('#stage .vid-msg[data-fail]:not([disabled])');
     assert.equal(await failed().count(),0,'持續下載不得在 30 秒前失敗');
     assert.equal(f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4')&&e.query.includes('_retry')).length,0,'持續下載不得重載');
     await page.waitForFunction(()=>!!v.parentElement.querySelector('.vid-msg[data-fail]:not([disabled])'),null,{timeout:12000});
     const elapsedMs=Math.round(performance.now()-start),progress=await page.evaluate(()=>ceilingProgress);
     const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4')),retries=requests.filter(e=>e.query.includes('_retry')).length;
     assert(elapsedMs>=29500&&elapsedMs<=34000,`媒體上限應約 30 秒，實際 ${elapsedMs} ms`);
     if(engine!=='webkit')assert(progress>=20,'Chromium 必須持續有可信任下載進度');
     assert(requests.some(e=>e.chunks>=100),'伺服器必須持續傳送真實資料');assert.equal(retries,0);
     await failed().click();
     assert.equal(await page.evaluate(()=>v.src.includes('_retry')),true,'上限後手動重試仍須使用 cache-buster');
     return {elapsedMs,progress,retries,manualRetry:true,chunks:requests.reduce((n,e)=>n+e.chunks,0)};
    },
    async slowByteStops(page){
     const before=f.events.length;
     await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?drip=45&dripStop=4000&case='+Date.now();load(4,false);},f.url);
     await page.waitForFunction(()=>v.readyState>=3&&!v.seeking&&v.src.includes('_retry'),null,{timeout:22000});
     const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4'));
     const lastByte=Math.max(...requests.filter(e=>!e.query.includes('_retry')).map(e=>e.lastByte||0));
     const retry=requests.find(e=>e.query.includes('_retry')),inactivityMs=Math.round(retry.time-lastByte);
     console.log(JSON.stringify({measurement:{engine,case:'slowByteStops',inactivityMs,requests}}));
     assert(requests.reduce((n,e)=>n+e.chunks,0)>=6,'必須先傳真實資料再停流');
     assert(inactivityMs>=9000&&inactivityMs<=13000,`停止下載後應約 10 秒重試，實際 ${inactivityMs} ms`);
     return {inactivityMs,retries:requests.filter(e=>e.query.includes('_retry')).length};
    },
    async byteProbeCancelled(page){
     const requests=[],finished=new Set();
     page.on('request',r=>{if(r.resourceType()==='fetch'&&r.url().includes('drip=45'))requests.push(r);});
     for(const event of ['requestfinished','requestfailed'])page.on(event,r=>finished.add(r));
     await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?drip=45&case='+Date.now();load(4,false);},f.url);
     await page.waitForTimeout(5500);
     assert.equal(requests.length,engine==='webkit'?1:0,'只有進度不可見時才探測');
     await page.evaluate(()=>load(8,false));await page.waitForFunction(()=>S.id===8&&v.readyState>=3&&!v.seeking);
     await page.waitForFunction(()=>S.id===8&&!!S.frames);
     assert(requests.every(r=>finished.has(r)),'換拍必須取消探測請求');
     await page.evaluate(url=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?drip=45&case='+Date.now();load(4,false);},f.url);
     await page.waitForTimeout(5500);
     const cancelled=Promise.all(requests.filter(r=>!finished.has(r)).map(request=>page.waitForEvent('requestfailed',{predicate:r=>r===request,timeout:1500})));
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
     await cancelled;
     assert.equal(requests.length,engine==='webkit'?2:0);
     assert(requests.every(r=>finished.has(r)),'隱藏分頁必須取消探測請求');
     return {probes:requests.length,cancelled:requests.filter(r=>!!r.failure()).length};
    },
    async poseFailure(page){
     let count=0;await page.route('**/pose/4.js*',()=>{count++;});
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>load(4,false));await started;
     for(let n=1;n<=4;n++){await page.clock.runFor(8500);assert.equal(await page.evaluate(()=>S._poseFails),n);if(n<4)await page.clock.runFor(5000);}
     assert.equal(count,4);assert.match(await page.locator('#stage .pose-msg').textContent(),/骨架載不到/);
    },
    async poseVisibleTime(page){
     let count=0;await page.route('**/pose/4.js*',route=>{count++;if(count>1)return route.continue();});
     await page.evaluate(()=>load(4,false));await page.clock.runFor(4000);
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
     await page.clock.runFor(20000);assert.equal(count,1);
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
     await page.clock.runFor(10000);await page.waitForFunction(()=>!!S.frames,null,{timeout:1500});assert.equal(count,2);
    },
    async stall(page){return stalled(page,false,'once');},
    async missedVisibility(page){return stalled(page,true,'once');},
    async stallFailure(page){return stalled(page,false,'always');},
    async progressWithoutMedia(page){await page.evaluate(()=>setInterval(()=>v.dispatchEvent(new Event('progress')),2000));return stalled(page,false,'once');},
    async noSource(page){
     await page.evaluate(()=>load(4,false));await page.waitForFunction(()=>v.readyState>=3&&!v.seeking);
     await page.evaluate(()=>{resetClip(v,'');Object.defineProperty(v,'currentSrc',{configurable:true,value:''});});await page.waitForTimeout(100);
     await page.evaluate(()=>{const m=v.parentElement.querySelector('.vid-msg');m.hidden=false;m.textContent='影片下載中…';});
     await page.clock.runFor(12000);await page.waitForFunction(()=>!!v.src||v.parentElement.querySelector('.vid-msg').hidden,null,{timeout:1000});
    },
    async rapid(page){return rapid(page,false);},
    async rapidH2(page){await page.goto(h2);assert.equal(await page.evaluate(()=>performance.getEntriesByType('navigation')[0].nextHopProtocol),'h2');await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>S&&v.readyState>=3);return rapid(page,false);},
    async rapidSlow(page){return rapid(page,true);},
    async single(page){
     await page.evaluate(()=>{cancelPrefetch();const list=visible(),i=list.indexOf(S);list[(i-1+list.length)%list.length].src+='?single';window.singleAt=performance.now();step(-1);});
     await page.waitForFunction(()=>performance.getEntriesByType('resource').some(e=>e.name.includes('?single')));const ms=await page.evaluate(()=>performance.getEntriesByType('resource').find(e=>e.name.includes('?single')).startTime-singleAt);
     assert(ms<50,`單按請求耗時 ${ms} ms`);return {requestMs:ms};
    },
    async neighborPose(page){
     await page.evaluate(()=>load(12,false));await page.waitForFunction(()=>[ALL[11],ALL[13]].every(s=>!!s.frames),null,{timeout:5000});
     await page.evaluate(()=>step(1));assert.equal(await page.locator('#stage .pose-msg').isVisible(),false);
    },
    async neighborPoseRecovery(page){
     let allow=false,count=0;await page.route('**/pose/13.js*',route=>{count++;return allow?route.continue():route.fulfill({status:503,body:''});});
     await page.evaluate(()=>load(12,false));await page.waitForFunction(()=>ALL[13]._poseErrAt,null,{timeout:5000});assert.equal(count,1);
     allow=true;await page.evaluate(()=>go(DAY,'video'));await page.waitForFunction(()=>TAB==='video');
     await page.locator('#vA').scrollIntoViewIfNeeded();await page.evaluate(()=>cmpLoad(ALL[13],ALL[14]));
     await page.waitForFunction(()=>!!A.frames,null,{timeout:6500});assert.equal(count,2);
    },
    async poseLeaveOverview(page){return leavePose(page,'overview');},
    async poseLeaveHome(page){return leavePose(page,'home');},
    async poseRouteRecovery(page){
     let allow=false;await page.route('**/pose/4.js*',route=>allow?route.continue():route.fulfill({status:503,body:''}));
     await page.evaluate(()=>load(4,false));await page.waitForFunction(()=>S._poseErrAt);allow=true;
     await page.evaluate(()=>go(DAY,'overview'));await page.waitForFunction(()=>TAB==='overview');
     await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>!!S.frames,null,{timeout:6500});
    },
    async poseCompareVisibleTime(page){
     await page.setViewportSize({width:390,height:500});
     let count=0;await page.route('**/pose/4.js*',route=>{count++;if(count>1)return route.continue();});
     await page.evaluate(()=>go(DAY,'video'));await page.waitForFunction(()=>TAB==='video');await page.locator('#vA').scrollIntoViewIfNeeded();
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>cmpLoad(ALL[4],ALL[6]));await started;
     await page.evaluate(()=>scrollTo(0,0));await page.waitForFunction(()=>!shown(vA));
     await page.clock.runFor(20000);assert.equal(count,1);assert.equal(await page.evaluate(()=>!!A._poseErrAt),false);
     await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>shown(vA));
     await page.clock.runFor(13500);await page.waitForFunction(()=>!!A.frames,null,{timeout:1500});assert.equal(count,2);
    },
    async poseCompareRouteRetry(page){
     let allow=false,count=0;await page.route('**/pose/4.js*',route=>{count++;return allow?route.continue():route.fulfill({status:503,body:''});});
     await page.evaluate(()=>go(DAY,'video'));await page.waitForFunction(()=>TAB==='video');await page.locator('#vA').scrollIntoViewIfNeeded();
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>cmpLoad(ALL[4],ALL[6]));await started;await page.waitForFunction(()=>!POSE_WAIT.has(A));
     await page.evaluate(()=>{window.compareScroll=scrollY;addEventListener('hashchange',()=>{if(TAB==='video')scrollTo(0,compareScroll);});go(DAY,'overview');});
     await page.waitForFunction(()=>TAB==='overview'&&vA._near===false);await page.clock.runFor(5500);allow=true;
     const before=count;await page.evaluate(()=>go(DAY,'video'));await page.waitForFunction(()=>shown(vA));
     await page.waitForFunction(()=>!!A.frames,null,{timeout:1500});assert.equal(count,before+1);assert.equal(await page.locator('#vA').locator('..').locator('.pose-msg').isVisible(),false);
    },
    async poseScrollRetry(page){
     await page.setViewportSize({width:390,height:500});
     let allow=false,count=0;await page.route('**/pose/4.js*',route=>{count++;return allow?route.continue():route.fulfill({status:503,body:''});});
     await page.evaluate(()=>go(DAY,'video'));await page.waitForFunction(()=>TAB==='video');await page.evaluate(()=>scrollTo(0,0));await page.waitForFunction(()=>!shown(vA));
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>{cmpLoad(ALL[4],ALL[6]);load(3,false);});await started;
     await page.waitForTimeout(500);await page.waitForFunction(()=>!POSE_WAIT.has(ALL[4]));await page.clock.runFor(5500);allow=true;
     const before=count;await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>!!A.frames,null,{timeout:1500});assert.equal(count,before+1);
    },
    async poseRetryBudget(page){
     let allow=false,count=0;await page.route('**/pose/4.js*',route=>{count++;return allow?route.continue():route.fulfill({status:503,body:''});});
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>load(4,false));await started;await page.waitForFunction(()=>!POSE_WAIT.has(S));
     assert.equal(count,1);
     for(let n=2;n<=4;n++){await page.clock.runFor(4500);assert.equal(count,n-1);await page.clock.runFor(1000);await page.waitForFunction(()=>!POSE_WAIT.has(S));assert.equal(count,n);}
     assert.match(await page.locator('#stage .pose-msg').textContent(),/骨架載不到/);await page.clock.runFor(30000);assert.equal(count,4);assert.equal(await page.evaluate(()=>POSE_WAIT.has(S)),false);
     allow=true;await page.evaluate(()=>go(DAY,'overview'));await page.waitForFunction(()=>TAB==='overview');await page.clock.runFor(5500);
     await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>!!S.frames,null,{timeout:1500});assert.equal(count,5);return {failedRequests:4,reentryRequests:1};
    },
    async poseBackgroundTimeout(page){
     let count=0;const inflight=new Set();page.on('request',r=>{if(r.url().includes('/pose/4.js'))inflight.add(r);});
     for(const event of ['requestfinished','requestfailed'])page.on(event,r=>inflight.delete(r));
     await page.route('**/pose/4.js*',()=>{count++;});const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>load(3,false));await started;
     await page.clock.runFor(14000);assert.equal(inflight.size,1);
     const failed=page.waitForEvent('requestfailed',{predicate:r=>r.url().includes('/pose/4.js'),timeout:1500});await page.clock.runFor(1500);await failed;
     assert.equal(await page.evaluate(()=>POSE_WAIT.has(ALL[4])),false);assert.equal(inflight.size,0);await page.clock.runFor(20000);assert.equal(count,1);return {requests:count,inflight:inflight.size};
    },
    async deferredPlayGesture(page){
     await page.evaluate(()=>{
      window.gesturePlays=[];window.playErrors=[];window.inPlayGesture=false;
      const click=$('play').onclick;$('play').onclick=e=>{window.inPlayGesture=e.isTrusted;try{return click(e);}finally{window.inPlayGesture=false;}};
      const native=v.play.bind(v);v.play=()=>{gesturePlays.push({gesture:inPlayGesture,src:v.src});const task=native();task?.catch(e=>playErrors.push(e.name));return task;};
      const list=visible(),target=list[(list.indexOf(S)-2+list.length)%list.length];target.src+='?gesture';step(-1);step(-1);
     });
     await page.locator('#play').click();
     const state=await page.evaluate(()=>({pending:!!mainLoadTimer,plays:gesturePlays}));
     assert.equal(state.pending,false);assert(state.plays.some(p=>p.gesture&&p.src),'可信任播放手勢中必須設定 src 並 play');
     await page.waitForFunction(()=>!v.paused&&v.readyState>=3&&!v.seeking);
     const before=await page.evaluate(()=>v.currentTime);await page.waitForFunction(t=>v.currentTime>t+.05,before,{timeout:2500});
     assert.deepEqual(await page.evaluate(()=>playErrors.filter(e=>e==='NotAllowedError')),[]);
     return {advanceSeconds:await page.evaluate(t=>v.currentTime-t,before),gesturePlays:state.plays.filter(p=>p.gesture).length};
    },
    async latePose(page){
     let release;const gate=new Promise(r=>release=r);await page.route('**/pose/4.js*',async route=>{await gate;await route.continue().catch(()=>{});});
     await page.evaluate(()=>load(4,false));await page.waitForTimeout(100);await page.evaluate(()=>load(8,false));release();
     await page.waitForFunction(()=>S.id===8&&!!S.frames);assert.equal(await page.evaluate(()=>cur),42);assert.match(await page.locator('#nowTitle').textContent(),/#09/);
    },
    async cancelPoseRequest(page){
     await page.route('**/pose/4.js*',()=>{});
     const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>load(4,false));await started;
     const failed=page.waitForEvent('requestfailed',{predicate:r=>r.url().includes('/pose/4.js'),timeout:2500});
     await page.evaluate(()=>load(8,false));await failed;
    },
   })){
    if(name==='rapidH2'&&engine==='webkit')continue;
    if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(name))continue;
    const context=await browser.newContext({ignoreHTTPSErrors:true,...(engine==='webkit'?devices['iPhone 13']:{})}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    try{
     if(['poseLongRetryStatus','poseFailure','poseVisibleTime','noSource','poseLeaveOverview','poseLeaveHome','poseCompareVisibleTime','poseCompareRouteRetry','poseScrollRetry','poseRetryBudget','poseBackgroundTimeout'].includes(name))await page.clock.install();
     await page.goto(f.url);await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>S&&v.readyState>=3&&!v.seeking);
     await page.waitForTimeout(650);const details=await test(page);assert.deepEqual(errors,[]);results.push({engine,case:name,pass:true,...details});
    }catch(e){results.push({engine,case:name,pass:false,error:e.message,errors});}
    finally{await context.close();}
    console.log(JSON.stringify(results.at(-1)));
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;

async function replacing(page,seconds){
 // Keep a measurable buffering window for pause/suspend injection, even when the probe starts late.
 await page.evaluate(({url,seconds})=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?nativeHang=1&drip='+seconds+'&perRequest=1&case='+Date.now();load(4,false);},{url:f.url,seconds});
 await page.waitForFunction(()=>v._fetching,null,{timeout:6500});
}

async function leavePose(page,tab){
 let allow=false,count=0;await page.route('**/pose/4.js*',route=>{count++;if(allow)return route.continue();});
 const started=page.waitForRequest('**/pose/4.js*');await page.evaluate(()=>load(4,false));await started;
 await page.evaluate(tab=>{if(tab==='home')location.hash='#home';else go(DAY,tab);},tab);
 await page.waitForFunction(tab=>tab==='home'?!$('home').hidden:TAB===tab,tab);
 await page.clock.runFor(20000);assert.equal(await page.evaluate(()=>POSE_WAIT.has(S)||!!S._poseErrAt),false);allow=true;
 await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>!!S.frames,null,{timeout:2000});
 assert.equal(count,2);assert.equal(await page.locator('#stage .pose-msg').isVisible(),false);
}

async function stalled(page,missed,mode){
 if(missed)await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
 const start=performance.now(),before=f.events.length;
 await page.evaluate(({url,mode})=>{ALL[4].src=url+'sessions/synthetic/clips/4.mp4?hang='+mode;load(4,false);}, {url:f.url,mode});
 if(missed)await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
 if(mode==='always')await page.waitForFunction(()=>!!v.parentElement.querySelector('[data-fail]:not([disabled])'),null,{timeout:24500});
 else await page.waitForFunction(()=>v.readyState>=3&&!v.error&&!v.seeking&&v.src.includes('_retry'),null,{timeout:14000});
 const requests=f.events.slice(before).filter(e=>e.file.endsWith('/4.mp4'));
 assert(requests.some(e=>e.query.includes('_retry')),'必須有實際 cache-buster GET');
 assert(requests.filter(e=>e.query.includes('_retry')).some(e=>e.time-start>=8500&&e.time-start<=13000),'約 10 秒重試');
 return {elapsedMs:Math.round(performance.now()-start),requests:requests.length};
}
async function rapid(page,slow){
 await page.evaluate(()=>{go(DAY_KEYS[0],'video');scrollTo(0,0);});await page.waitForFunction(()=>TAB==='video');
 await page.evaluate(()=>{cancelPrefetch();CLIPS.clear();for(const s of ALL){delete s.frames;delete s.world;delete s._poseErrAt;delete s._poseFails;}load(0,false);});
 await page.waitForFunction(()=>S.id===0&&v.readyState>=3);await page.waitForTimeout(700);
 await page.evaluate(()=>{cancelPrefetch();const first=ALL[24],entry=CLIPS.get(first.src);if(entry?.url)URL.revokeObjectURL(entry.url);CLIPS.delete(first.src);delete first.frames;});
 const requests=[],inflight=new Set(),cancelled=[];
 page.on('request',r=>{if(/\/(clips|pose)\/\d+\.(mp4|js)/.test(r.url())){requests.push({url:r.url(),time:Date.now()});inflight.add(r);}});
 for(const event of ['requestfinished','requestfailed'])page.on(event,r=>inflight.delete(r));
 page.on('requestfailed',r=>{if(/\/(clips|pose)\/24\./.test(r.url()))cancelled.push(new URL(r.url()).pathname.includes('/pose/')?'pose':'clip');});
 if(slow)await page.route('**/sessions/synthetic/**',async route=>{if(/\/(clips|pose)\//.test(route.request().url()))await new Promise(r=>setTimeout(r,1200));await route.continue().catch(()=>{});});
 // 固定 300 ms 間隔在瀏覽器內執行，避免工具往返時間改變輸入。
 await page.evaluate(async()=>{window.rapidTitles=[];for(let i=0;i<18;i++){step(-1);rapidTitles.push({id:S.id,title:$('nowTitle').textContent,knee:$('mKnee').textContent});if(i<17)await new Promise(r=>setTimeout(r,300));}window.rapidStop=Date.now();});
 await page.waitForFunction(()=>S.id===7&&v.readyState>=3&&S.frames&&[ALL[6],ALL[8]].every(s=>CLIPS.get(s.src)?.url),null,{timeout:10000});
 await page.waitForTimeout(200);
 const counts={};for(const r of requests){const match=/\/(clips|pose)\/(\d+)\./.exec(r.url);const k=match[2];counts[k]??={clip:0,pose:0};counts[k][match[1]==='clips'?'clip':'pose']++;}
 const state=await page.evaluate(()=>({id:S.id,ready:v.readyState,pose:!!S.frames,titles:rapidTitles,stoppedAt:rapidStop}));
 const settleMs=requests.find(r=>r.url.includes('/clips/7.mp4')&&r.time>=state.stoppedAt)?.time-state.stoppedAt;
 const details={counts,inflight:inflight.size,pending:[...inflight].map(r=>({type:r.resourceType(),file:new URL(r.url()).pathname})),cancelled,final:state.id,ready:state.ready,pose:state.pose,settleMs};console.log(JSON.stringify({measurement:details}));
 assert(state.titles.every(s=>s.title.includes('#'+String(s.id+1).padStart(2,'0'))&&s.knee.includes(String(110+s.id))),'標題與數據立即更新');
 assert.equal(state.id,7);assert(state.ready>=2&&state.pose);
 const allowed=new Set([24,7,6,8]);assert(Object.keys(counts).every(id=>allowed.has(+id)),'只允許第一拍、最後一拍與最後鄰居');
 assert(settleMs>=300&&settleMs<750,'停下約 350 ms 才載入最後一拍');
 assert(Object.values(counts).every(c=>c.pose<=1&&c.clip<=2),'骨架最多一次、影片最多兩次原生 Range 探測');
 assert.equal(inflight.size,0);
 if(slow)assert.deepEqual([...new Set(cancelled)].sort(),['clip','pose'],'已發出的第一拍影片與骨架都必須真的取消');
 return details;
}
