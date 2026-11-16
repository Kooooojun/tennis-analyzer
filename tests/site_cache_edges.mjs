// Local real-media E2E; uses the same fixture and browser environment as test_site_smoke.py.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
const ready=page=>page.waitForFunction(()=>v.readyState>=3&&!v.seeking);
async function compare(page){
 await page.evaluate(()=>go(DAY,'video'));await page.locator('#vA').scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking));
}
for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch();
 for(const [name,test] of Object.entries({
  async backgroundReload(page){
   await compare(page);
   await page.evaluate(()=>{toggle();cmpStart();});await page.waitForFunction(()=>[v,vA,vB].every(x=>!x.paused&&x._want));
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
   await page.clock.runFor(25000);
   assert.deepEqual(await page.evaluate(()=>[v,vA,vB].map(x=>!!x._resume)),[true,true,true],'已播放的片段必須保留重載續播意圖');
   await page.evaluate(()=>{
    Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));
    window.reloads=[0,0,0];
    for(const [i,x] of [v,vA,vB].entries()){
     const load=x.load.bind(x);x.load=()=>{reloads[i]++;load();};
     Object.defineProperty(x,'readyState',{configurable:true,value:2});Object.defineProperty(x,'currentTime',{configurable:true,get:()=>.8,set:()=>{}});Object.defineProperty(x,'buffered',{configurable:true,value:{length:0}});
    }
   });
   await page.clock.runFor(11500);
   assert(await page.evaluate(()=>reloads.every(n=>n>0)),'每支卡住的片段都必須實際重載');
   assert.deepEqual(await page.evaluate(()=>[v,vA,vB].map(x=>!!x._want)),[true,true,true]);
   await page.evaluate(()=>{for(const x of [v,vA,vB]){for(const p of ['readyState','currentTime','buffered'])delete x[p];x.dispatchEvent(new Event('canplay'));}});
   await page.waitForFunction(()=>[v,vA,vB].every(x=>!x.paused&&x._want&&!x._reloading));
  },
  async permanentErrors(page){
   for(const broken of ['404','corrupt']){
    await page.route('**/*edge-error*',r=>r.fulfill({status:broken==='404'?404:200,contentType:'video/mp4',body:broken==='404'?'':'broken'}));
    const t=Date.now();await page.evaluate(()=>{ALL[3].src+='?edge-error';load(3,false);});
    await page.waitForFunction(()=>v.parentElement.querySelector('[data-fail]:not([disabled])'));
    assert(Date.now()-t<1800,`${broken}: 確定性錯誤不得等待自動重載`);
    await page.unroute('**/*edge-error*');
   }
  },
  async compareLoading(page){
   await compare(page);
   await page.route('**/*edge-slow*',async r=>{await new Promise(resolve=>setTimeout(resolve,2200));await r.continue().catch(()=>{});});
   await page.evaluate(()=>cmpLoad(ALL[3],{...ALL[4],src:ALL[4].src+'?edge-slow'}));
   await page.waitForFunction(()=>vA.readyState>=2&&!vA.seeking&&vB.readyState===0);
   await page.evaluate(()=>cmpStart());
   const t=await page.evaluate(()=>vA.currentTime);await page.waitForTimeout(800);
   assert(Math.abs(await page.evaluate(()=>vA.currentTime)-t)<1/60,'另一側載入時，已就緒側不得前進');
   await page.waitForFunction(()=>!vA.paused&&!vB.paused);
  },
  async compareUnready(page){
   await compare(page);await page.evaluate(()=>{Object.defineProperty(vB,'readyState',{configurable:true,value:2});cmpStart();});
   const t=await page.evaluate(()=>vA.currentTime);await page.waitForTimeout(300);
   assert(Math.abs(await page.evaluate(()=>vA.currentTime)-t)<1/60,'只有 metadata 仍不足以同步播放');
   await page.evaluate(()=>{delete vB.readyState;vB.dispatchEvent(new Event('canplay'));});
   await page.waitForFunction(()=>!vA.paused&&!vB.paused);
   await page.evaluate(()=>{Object.defineProperty(vB,'readyState',{configurable:true,value:2});vB.dispatchEvent(new Event('waiting'));});
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused]),[true,true]);
   await page.evaluate(()=>{delete vB.readyState;vB.dispatchEvent(new Event('canplay'));});
   await page.waitForFunction(()=>!vA.paused&&!vB.paused);
   await page.evaluate(()=>{Object.defineProperty(vB,'seeking',{configurable:true,value:true});vB.dispatchEvent(new Event('seeking'));});
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused]),[true,true]);
   await page.evaluate(()=>{delete vB.seeking;vB.dispatchEvent(new Event('seeked'));});
   await page.waitForFunction(()=>!vA.paused&&!vB.paused);
  },
  async compareBroken(page){
   await compare(page);await page.route('**/*edge-broken*',r=>r.fulfill({status:404,body:''}));
   await page.evaluate(()=>{cmpLoad(ALL[3],{...ALL[4],src:ALL[4].src+'?edge-broken'});window.unpaired=0;vA.addEventListener('timeupdate',()=>{if(vB.error)unpaired++;});cmpStart();});
   await page.waitForFunction(()=>vB.parentElement.querySelector('[data-fail]'));
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused,unpaired]),[true,true,0]);
  },
  async dripDeadline(page){
   await page.evaluate(()=>{
    resetClip(v,'deadline.mp4');Object.defineProperty(v,'src',{configurable:true,get:()=> 'deadline.mp4',set:()=>{}});
    Object.defineProperty(v,'currentSrc',{configurable:true,value:'deadline.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});
    Object.defineProperty(v,'currentTime',{configurable:true,get:()=>0,set:()=>{}});Object.defineProperty(v,'buffered',{configurable:true,value:{length:0}});
    setInterval(()=>v.dispatchEvent(new Event('progress')),2000);
   });await page.clock.runFor(32000);
   assert.equal(await page.evaluate(()=>!!v.parentElement.querySelector('[data-fail]:not([disabled])')),true,'媒體無進展達 30 秒時必須立即提供重試');
  },
  async reloadMissingSource(page){
   await page.evaluate(()=>{v.removeAttribute('src');v.load();Object.defineProperty(v,'currentSrc',{configurable:true,value:''});});
   await page.evaluate(()=>{const m=v.parentElement.querySelector('.vid-msg');m.dataset.fail='1';m.disabled=false;m.click();});
   assert.deepEqual(await page.evaluate(()=>[v._want,$('play').textContent.includes('⏸')]),[true,true]);
   await page.evaluate(()=>{delete v.currentSrc;});await page.waitForFunction(()=>!v.paused&&v._want);
  },
  async reloadFetching(page){
   await page.evaluate(()=>{v._fetching=true;const m=v.parentElement.querySelector('.vid-msg');m.dataset.fail='1';m.disabled=false;m.click();});
   assert.equal(await page.evaluate(()=>v._want),true);
   await page.waitForFunction(()=>!v.paused&&v._want);
  },
  async resetReferences(page){
   assert.equal(await page.evaluate(()=>{resetClip(v,'new-source.mp4');return v._clip==null&&v._start==null;}),true);
  },
  async hiddenNewSources(page){
   await compare(page);await page.evaluate(()=>{
    Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));window.hiddenPlays=[];
    for(const x of [v,vA,vB]){const play=x.play.bind(x);x.play=()=>{if(document.hidden)hiddenPlays.push(x.id);return play();};}
    load(3,false);cmpLoad(ALL[4],ALL[5]);
   });await page.waitForTimeout(1300);
   assert.deepEqual(await page.evaluate(()=>hiddenPlays),[]);
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
   await page.waitForFunction(()=>[v,vA,vB].every(x=>x.readyState>=2&&!x.seeking));
   assert.deepEqual(await page.evaluate(()=>[v,vA,vB].map(x=>x.paused&&!x._want)),[true,true,true]);
  },
  async neighborDedup(page){
   await page.evaluate(()=>{cancelPrefetch();window.original=ALL;window.neighborCalls=[];clipFetch=async k=>{neighborCalls.push(k);return k;};ALL=[S];filter=pfilter='ALL';});
   await page.evaluate(()=>preloadNeighbors(S));
   assert.deepEqual(await page.evaluate(()=>neighborCalls),[],'只有一拍時不得預載自己');
   await page.evaluate(()=>{cancelPrefetch();ALL=[S,original.find(x=>x!==S)];neighborCalls=[];});await page.evaluate(()=>preloadNeighbors(S));
   assert.equal(await page.evaluate(()=>neighborCalls.length),1,'只有兩拍時上一拍與下一拍只能下載一次');
  },
  async filteredColdPrefetch(page){
   const count=await page.evaluate(async()=>{
    cancelPrefetch();window.neighborCalls=[];clipFetch=async k=>{neighborCalls.push(k);return k;};
    filter=S.kind==='FH'?'BH':'FH';ALL=[S,{...ALL.find(x=>x!==S),kind:filter}];drawList();
    await new Promise(r=>setTimeout(r,50));return neighborCalls.length;
   });
   assert(count>0,'串流片段已完整緩衝時，篩選後必須重新預載鄰拍');
  },
  async tabReturn(page){
   await page.evaluate(()=>go(DAY,'overview'));await page.waitForFunction(()=>!v.offsetParent);await page.waitForTimeout(700);
   const t=Date.now();await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>v.offsetParent&&v.readyState>=2&&!v.seeking);
   assert(Date.now()-t<700,'返回已完整緩衝的片段不得重新下載');
  },
 })){
  if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(name))continue;
  const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
   if(['backgroundReload','dripDeadline'].includes(name))await page.clock.install();
   await page.goto(process.env.SITE_E2E_URL);await page.waitForFunction(()=>typeof ALL!=='undefined'&&ALL.length>=6);
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await ready(page);await page.waitForFunction(()=>fullyBuffered(v));
   await test(page);assert.deepEqual(errors,[]);results.push({engine,case:name,pass:true});
  }catch(e){results.push({engine,case:name,pass:false,error:e.message});}
  console.log(engine,name,results.at(-1).pass,results.at(-1).error||'');await context.close();
 }
 await browser.close();
}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
