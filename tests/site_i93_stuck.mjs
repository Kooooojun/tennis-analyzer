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
     await page.waitForFunction(()=>!!S.frames,null,{timeout:10500});
     assert.equal(requests.length,2);assert(new URL(requests[1]).searchParams.has('_retry'));
    },
    async poseFailure(page){
     let count=0;await page.route('**/pose/4.js*',()=>{count++;});
     await page.evaluate(()=>load(4,false));await page.waitForFunction(()=>S._poseErr,null,{timeout:18000});
     assert.equal(count,2);assert.match(await page.locator('#stage .pose-msg').textContent(),/骨架載不到/);
    },
    async poseVisibleTime(page){
     let count=0;await page.route('**/pose/4.js*',route=>{count++;if(count>1)return route.continue();});
     await page.evaluate(()=>load(4,false));await page.clock.runFor(4000);
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
     await page.clock.runFor(20000);assert.equal(count,1);
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
     await page.clock.runFor(5000);await page.waitForFunction(()=>!!S.frames,null,{timeout:1500});assert.equal(count,2);
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
     if(['poseVisibleTime','noSource'].includes(name))await page.clock.install();
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
 await page.evaluate(()=>{cancelPrefetch();CLIPS.clear();for(const s of ALL){delete s.frames;delete s.world;delete s._poseErr;}load(0,false);});
 await page.waitForFunction(()=>S.id===0&&v.readyState>=3);await page.waitForTimeout(700);
 await page.evaluate(()=>{cancelPrefetch();const first=ALL[24],entry=CLIPS.get(first.src);if(entry?.url)URL.revokeObjectURL(entry.url);CLIPS.delete(first.src);delete first.frames;});
 const requests=[],inflight=new Set(),cancelled=[];
 page.on('request',r=>{if(/\/(clips|pose)\/\d+\.(mp4|js)/.test(r.url())){requests.push({url:r.url(),time:performance.now()});inflight.add(r);}});
 for(const event of ['requestfinished','requestfailed'])page.on(event,r=>inflight.delete(r));
 page.on('requestfailed',r=>{if(/\/(clips|pose)\/24\./.test(r.url()))cancelled.push(new URL(r.url()).pathname.includes('/pose/')?'pose':'clip');});
 if(slow)await page.route('**/sessions/synthetic/**',async route=>{if(/\/(clips|pose)\//.test(route.request().url()))await new Promise(r=>setTimeout(r,1200));await route.continue().catch(()=>{});});
 // 固定 300 ms 間隔在瀏覽器內執行，避免工具往返時間改變輸入。
 await page.evaluate(async()=>{window.rapidTitles=[];for(let i=0;i<18;i++){step(-1);rapidTitles.push({id:S.id,title:$('nowTitle').textContent,knee:$('mKnee').textContent});if(i<17)await new Promise(r=>setTimeout(r,300));}window.rapidStop=performance.now();});
 await page.waitForFunction(()=>S.id===7&&v.readyState>=3&&S.frames&&[ALL[6],ALL[8]].every(s=>CLIPS.get(s.src)?.url),null,{timeout:10000});
 await page.waitForTimeout(200);
 const counts={};for(const r of requests){const match=/\/(clips|pose)\/(\d+)\./.exec(r.url);const k=match[2];counts[k]??={clip:0,pose:0};counts[k][match[1]==='clips'?'clip':'pose']++;}
 const state=await page.evaluate(()=>({id:S.id,ready:v.readyState,pose:!!S.frames,titles:rapidTitles,settleMs:performance.getEntriesByType('resource').find(e=>e.name.includes('/clips/7.mp4')&&e.startTime>=rapidStop)?.startTime-rapidStop}));
 const details={counts,inflight:inflight.size,pending:[...inflight].map(r=>({type:r.resourceType(),file:new URL(r.url()).pathname})),cancelled,final:state.id,ready:state.ready,pose:state.pose,settleMs:state.settleMs};console.log(JSON.stringify({measurement:details}));
 assert(state.titles.every(s=>s.title.includes('#'+String(s.id+1).padStart(2,'0'))&&s.knee.includes(String(110+s.id))),'標題與數據立即更新');
 assert.equal(state.id,7);assert(state.ready>=2&&state.pose);
 const allowed=new Set([24,7,6,8]);assert(Object.keys(counts).every(id=>allowed.has(+id)),'只允許第一拍、最後一拍與最後鄰居');
 assert(state.settleMs>=300&&state.settleMs<750,'停下約 350 ms 才載入最後一拍');
 assert(Object.values(counts).every(c=>c.pose<=1&&c.clip<=2),'骨架最多一次、影片最多兩次原生 Range 探測');
 assert.equal(inflight.size,0);
 if(slow)assert.deepEqual([...new Set(cancelled)].sort(),['clip','pose'],'已發出的第一拍影片與骨架都必須真的取消');
 return details;
}
