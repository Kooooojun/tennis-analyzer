// Run against the fixture server; each case gets an independent browser page.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
for(const [name,engine] of Object.entries({chromium,webkit})){
 const browser=await engine.launch();
 for(const [label,test] of Object.entries({
  async routeStall(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'route.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'http://example.test/route.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'http://example.test/route.mp4',set:()=>reloads++});});
   await page.clock.runFor(8000);await page.evaluate(()=>{location.hash='#home';});await page.waitForFunction(()=>!v.offsetParent);await page.clock.runFor(3000);
   await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>!!v.offsetParent);await page.clock.runFor(2000);assert.equal(await page.evaluate(()=>reloads),0);
  },
  async routeBackoff(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'route-retry.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'http://example.test/route-retry.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});Object.defineProperty(v,'error',{configurable:true,value:{code:2}});window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'http://example.test/route-retry.mp4',set:()=>reloads++});});
   await page.clock.runFor(4000);await page.evaluate(()=>{location.hash='#home';});await page.waitForFunction(()=>!v.offsetParent);await page.clock.runFor(20000);
   await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>!!v.offsetParent);await page.clock.runFor(1000);assert.equal(await page.evaluate(()=>reloads),1);
  },
  async routeError(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'route-error.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'http://example.test/route-error.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});Object.defineProperty(v,'error',{configurable:true,value:{code:2}});window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'http://example.test/route-error.mp4',set:()=>reloads++});});
   await page.clock.runFor(1500);await page.evaluate(()=>{location.hash='#home';});await page.waitForFunction(()=>!v.offsetParent);await page.clock.runFor(3000);
   await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>!!v.offsetParent);await page.clock.runFor(500);assert.equal(await page.evaluate(()=>reloads),0);
  },
  async compareForegroundStill(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>{stopDead(vA);resetClip(vA,'foreground.mp4');vA._want=vA._resume=vB._want=vB._resume=true;Object.defineProperty(vA,'currentSrc',{configurable:true,value:'http://example.test/foreground.mp4'});Object.defineProperty(vA,'readyState',{configurable:true,value:0});Object.defineProperty(vA,'error',{configurable:true,value:{code:2}});window.intents=[];Object.defineProperty(vA,'src',{configurable:true,get:()=> 'http://example.test/foreground.mp4',set:()=>intents.push([vA._want,vB._want])});});
   await page.clock.runFor(4000);await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});await page.clock.runFor(20000);
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});assert.deepEqual(await page.evaluate(()=>intents[1]),[false,false]);
  },
  async byteCeiling(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'ceiling.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'http://example.test/ceiling.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'http://example.test/ceiling.mp4',set:()=>reloads++});setInterval(()=>v.dispatchEvent(new Event('progress')),2000);});
   await page.clock.runFor(25000);assert.equal(await page.evaluate(()=>reloads),1);assert.equal(await page.evaluate(()=>!!v.parentElement.querySelector('[data-fail]:not([disabled])')),true);
  },
  async recoveredBudget(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'recovered.mp4');window.bad=true;window.fakeSource='http://example.test/recovered.mp4';Object.defineProperty(v,'currentSrc',{configurable:true,get:()=>fakeSource});Object.defineProperty(v,'readyState',{configurable:true,get:()=>bad?0:4});Object.defineProperty(v,'error',{configurable:true,get:()=>bad?{code:2}:null});window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=>fakeSource,set:url=>{fakeSource=url;reloads++;}});});
   await page.clock.runFor(125000);assert.equal(await page.evaluate(()=>reloads),4);
   await page.evaluate(()=>{bad=false;v.dispatchEvent(new Event('loadedmetadata'));});await page.clock.runFor(1000);
   await page.evaluate(()=>{bad=true;});await page.clock.runFor(20000);assert.equal(await page.evaluate(()=>reloads),6,'a recovered clip gets a fresh backoff budget');
  },
  async backgroundAlign(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   const state=await page.evaluate(async()=>{stopDead(vA);const token=vA._loadToken;await setClip(vA,A,()=>{});vA._want=vA._resume=vB._want=vB._resume=true;Object.defineProperty(document,'hidden',{configurable:true,value:true});Object.defineProperty(vA,'readyState',{configurable:true,value:4});Object.defineProperty(vB,'readyState',{configurable:true,value:4});window.starts=0;const old=cmpStart;cmpStart=()=>starts++;vA._align();cmpStart=old;return {starts,want:vA._want||vB._want,paused:vA.paused&&vB.paused,button:$('cmpPlay').textContent.includes('▶')};});
   assert.deepEqual(state,{starts:0,want:false,paused:true,button:true});
  },
  async compareAutoStill(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>{stopDead(vA);resetClip(vA,'auto.mp4');vA._want=vA._resume=vB._want=vB._resume=true;Object.defineProperty(vA,'currentSrc',{configurable:true,value:'http://example.test/auto.mp4'});Object.defineProperty(vA,'readyState',{configurable:true,value:0});Object.defineProperty(vA,'error',{configurable:true,value:{code:2}});window.intents=[];Object.defineProperty(vA,'src',{configurable:true,get:()=> 'http://example.test/auto.mp4',set:()=>intents.push([vA._want,vB._want])});});
   await page.clock.runFor(19000);assert.deepEqual(await page.evaluate(()=>intents[1]),[false,false]);assert.equal(await page.evaluate(()=>$('cmpPlay').textContent.includes('▶')),true);
  },
  async compareStallPause(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>cmpStart());await page.waitForFunction(()=>!vA.paused&&!vB.paused);
   await page.evaluate(()=>{Object.defineProperty(vA,'readyState',{configurable:true,value:2});Object.defineProperty(vA,'currentTime',{configurable:true,get:()=>0,set:()=>{}});Object.defineProperty(vA,'buffered',{configurable:true,value:{length:0}});window.partnerPaused=[];const original=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'src');Object.defineProperty(vA,'src',{configurable:true,get(){return original.get.call(this);},set(u){partnerPaused.push(vB.paused);}});});
   await page.clock.runFor(12000);assert.equal(await page.evaluate(()=>partnerPaused[0]),true);
  },
  async oversized(page){
   const state=await page.evaluate(async()=>{const old=fetch;CLIPS.set('kept',{size:1,url:URL.createObjectURL(new Blob(['old']))});window.fetch=async()=>new Response('large',{headers:{'Content-Type':'video/mp4','Content-Length':String(CLIP_LIMIT+1)}});try{await clipFetch('oversized.mp4');return CLIPS.has('kept');}finally{window.fetch=old;}});assert.equal(state,true);
  },
  async playRetries(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   const retries=await page.evaluate(()=>{stopDead(v);const m=v.parentElement.querySelector('.vid-msg');m.dataset.fail='1';m.disabled=false;let n=0;m.onclick=()=>n++;toggle();return n;});assert.equal(retries,1);
  },
  async sharedBadBlob(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   const states=await page.evaluate(async()=>{stopDead(vA);const key=A.src,url=await clipFetch(key,true);vA.src=url;vB.src=url;vA.dispatchEvent(new Event('error'));vA.removeAttribute('src');vA.load();releaseClips();const first=liveClips.has(url);vB.removeAttribute('src');vB.load();releaseClips();return [first,liveClips.has(url),revokedActive];});assert.deepEqual(states,[true,false,0]);
  },
  async readyHidesMessage(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=3&&!v.seeking&&!v._align&&!v._fetching);
   const hidden=await page.evaluate(()=>{const m=v.parentElement.querySelector('.vid-msg');m.hidden=false;m.textContent='影片下載中… 11%';v.dispatchEvent(new Event('canplay'));return m.hidden;});assert.equal(hidden,true);
  },
  async mime(page){
   const cached=await page.evaluate(async()=>{const old=fetch;window.fetch=async()=>new Response('not media',{headers:{'Content-Type':'text/html'}});try{await clipFetch('mime.mp4');return CLIPS.has('mime.mp4');}finally{window.fetch=old;}});
   assert.equal(cached,false);
  },
  async length(page){
   const kept=await page.evaluate(async()=>{const old=fetch;CLIPS.set('old',{size:1,url:URL.createObjectURL(new Blob(['old']))});window.fetch=async()=>new Response('clip',{headers:{'Content-Type':'video/mp4','Content-Length':'invalid'}});try{await clipFetch('length.mp4');return CLIPS.has('old')&&CLIPS.has('length.mp4');}finally{window.fetch=old;}});
   assert.equal(kept,true);
  },
  async completedPrefetch(page){
   const kept=await page.evaluate(async()=>{const old=fetch;window.fetch=async()=>new Response('clip',{headers:{'Content-Type':'video/mp4'}});try{await clipFetch('prefetch.mp4',true);prefetch=CLIPS.get('prefetch.mp4');cancelPrefetch();return CLIPS.has('prefetch.mp4');}finally{window.fetch=old;}});
   assert.equal(kept,true);
  },
  async pendingAlignment(page){
   await page.evaluate(()=>{go(DAY_KEYS[0],'stroke');});await page.waitForFunction(()=>v.readyState>=2);
   const kept=await page.evaluate(()=>{v._fetching=true;v._align=()=>{};v.addEventListener('loadedmetadata',v._align);toggle();toggle();return !!v._align;});
   assert.equal(kept,true);
  },
  async playingHiddenIntent(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=3);await page.evaluate(()=>toggle());await page.waitForFunction(()=>!v.paused&&v._want);
   const state=await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));v.dispatchEvent(new Event('playing'));return [v.paused,v._want];});assert.deepEqual(state,[false,true]);
  },
  async hiddenStall(page){

   await page.evaluate(()=>{go(DAY_KEYS[0],'stroke');});await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'hidden.mp4');Object.defineProperty(document,'hidden',{configurable:true,value:true});Object.defineProperty(v,'currentSrc',{configurable:true,value:'hidden.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});v._fetching=false;window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'hidden.mp4',set:()=>window.reloads++});});
   await page.clock.runFor(25000);
   assert.deepEqual(await page.evaluate(()=>({reloads,failed:!!v.parentElement.querySelector('[data-fail]')})),{reloads:0,failed:false});
  },
  async byteProgress(page){
   await page.evaluate(()=>{go(DAY_KEYS[0],'stroke');});await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'progress.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'progress.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});v._fetching=false;window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'progress.mp4',set:()=>window.reloads++});setInterval(()=>v.dispatchEvent(new Event('progress')),2000);});
   await page.clock.runFor(12500);assert.equal(await page.evaluate(()=>reloads),1,'只有 progress 事件、沒有媒體進展也必須重載');
  },
  async lru(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(async()=>{cancelPrefetch();for(let i=3;i<15;i++)await clipFetch(ALL[i].src+'?lru='+i);});
   const state=await page.evaluate(()=>({bytes:[...liveClips.values()].reduce((a,b)=>a+b,0),limit:CLIP_LIMIT,revoked,active:revokedActive}));
   assert(state.revoked>0,'LRU must actually revoke URLs');assert(state.bytes<=2*1024*1024);assert.equal(state.active,0);
  },
  async prefetchOrder(page){
   const requests=[];page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('.mp4'))requests.push(r.url());});
   await page.waitForTimeout(200);assert.equal(requests.length,0,'home fetches none');
   await page.evaluate(()=>go(DAY_KEYS[0],'overview'));await page.waitForFunction(()=>S);const main=await page.evaluate(()=>new URL(S.src,location.href).href);for(let t=0;t<50&&!requests.length;t++)await page.waitForTimeout(100);assert.equal(requests[0],main,'one page (UI A5): the player is always on it, so its own clip is fetched first (was: overview fetches none)');
   await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>{if(!S)return false;const list=visible(),i=list.indexOf(S);return CLIPS.get(list[(i-1+list.length)%list.length].src)?.url;});
   const expected=await page.evaluate(()=>{const list=visible();const i=list.indexOf(S);return [S.src,list[(i+1)%list.length].src,list[(i-1+list.length)%list.length].src].map(u=>new URL(u,location.href).href);});assert.deepEqual([...new Set(requests)].slice(0,3),expected);
  },
  async abortPrefetch(page){
   let aborted=false;await page.route('**/*.mp4*',async route=>{if(route.request().url().includes('pendingprefetch')){try{await new Promise(r=>setTimeout(r,1000));await route.continue();}catch{}}else await route.continue();});
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{cancelPrefetch();const key=ALL[4].src+'?pendingprefetch';clipFetch(key,true);prefetch=CLIPS.get(key);window.pendingEntry=prefetch;});
   await page.evaluate(()=>load(3,false));aborted=await page.evaluate(()=>pendingEntry.controller.signal.aborted);assert.equal(aborted,true);
  },
  async compareCancel(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.route('**/*slowpair*',async route=>{await new Promise(r=>setTimeout(r,600));try{await route.continue();}catch{}});
   await page.evaluate(()=>{const b={...ALL[4],src:ALL[4].src+'?slowpair'};cmpLoad(ALL[3],b);cmpStart();});
   await page.waitForFunction(()=>vA.readyState>=1&&!vB.readyState);
   await page.evaluate(()=>$('cmpPlay').click());
   await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.waitForTimeout(100);
   const state=await page.evaluate(()=>({time:vA.currentTime,target:(Math.max(0,A.contact-48)+.5)/FPS,delta:vB.currentTime-cmpBt(),paused:vA.paused&&vB.paused}));
   assert(Math.abs(state.time-state.target)<1/60,'cancel retains initial frame');assert(Math.abs(state.delta)<1/60);assert(state.paused);
  },
  async retryBudget(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'retry.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'http://example.test/retry.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});Object.defineProperty(v,'error',{configurable:true,value:{code:2}});window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'http://example.test/retry.mp4',set:()=>window.reloads++});});
   await page.clock.runFor(1500);assert.equal(await page.evaluate(()=>reloads),0,'first error waits two seconds');
   await page.clock.runFor(2500);assert.equal(await page.evaluate(()=>reloads),1);
   await page.clock.runFor(12000);assert.equal(await page.evaluate(()=>reloads),1,'backoff waits 15 seconds');
   await page.clock.runFor(110000);assert.equal(await page.evaluate(()=>reloads),4,'only three automatic retries');
   await page.clock.runFor(120000);assert.equal(await page.evaluate(()=>reloads),4);
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
   await page.clock.runFor(20000);assert.equal(await page.evaluate(()=>reloads),4);
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
   assert.equal(await page.evaluate(()=>reloads),5,'foreground retries a failed clip once');
  },
  async corruptBlob(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(async()=>{const real=fetch;let bad=true;window.fetch=async(...args)=>{if(bad&&String(args[0]).includes('badcase')){bad=false;return new Response('broken',{headers:{'Content-Type':'video/mp4'}});}return real(...args);};ALL[3].src+='?badcase';await clipFetch(ALL[3].src,true);load(3,false);});
   await page.waitForFunction(()=>v.error&&v.src.startsWith('blob:'));
   const bad=await page.evaluate(()=>v.src);
   await page.waitForFunction(()=>!v.src.startsWith('blob:')&&v.readyState>=2&&!v.error);
   assert.equal(await page.evaluate(()=>CLIPS.has(v._clipKey)),false);
   assert.equal(await page.evaluate(bad=>retiredClips.has(bad),bad),false);
  },
  async compareError(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>cmpStart());await page.waitForFunction(()=>!vA.paused&&!vB.paused);
   await page.evaluate(()=>{Object.defineProperty(vA,'error',{configurable:true,value:{code:2}});vA.pause();vA.dispatchEvent(new Event('error'));});
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused,$('cmpPlay').textContent.includes('⏸'),vA._want,vB._want]),[true,true,true,true,true]);
  },
  async primeOnTap(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   const calls=await page.evaluate(()=>{stopDead(vA);window.primes=[0,0];for(const [i,x] of [vA,vB].entries()){Object.defineProperty(x,'readyState',{configurable:true,value:0});x.play=()=>{primes[i]++;return Promise.resolve();};}cmpStart();return primes;});assert.deepEqual(calls,[1,1],'a tap must prime streams blocked before metadata');
  },
  async blockedPartner(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>{vB.play=()=>Promise.reject(new DOMException('blocked','NotAllowedError'));cmpStart();});
   await page.waitForTimeout(100);
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused,$('cmpPlay').textContent.includes('▶')]),[true,true,true]);
  },
  async partnerRetry(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   let release=false;await page.route('**/*partner-retry*',route=>release?route.continue():route.fulfill({status:404,body:''}));
   await page.evaluate(()=>{cmpLoad(A,{...B,src:B.src+'?partner-retry'});cmpStart();});
   await page.waitForFunction(()=>vB.parentElement.querySelector('[data-fail]'));
   release=true;await page.evaluate(()=>vB.parentElement.querySelector('.vid-msg').click());
   await page.waitForFunction(()=>vB.readyState>=2&&!vB._reloading);
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused,$('cmpPlay').textContent.includes('▶')]),[true,true,true]);
   await page.evaluate(()=>cmpStart());await page.waitForFunction(()=>!vA.paused&&!vB.paused);
   assert.equal(await page.evaluate(()=>$('cmpPlay').textContent.includes('⏸')),true);
  },
  async emptyBuffer(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   const count=await page.evaluate(()=>{stopDead(vA);Object.defineProperty(vB,'readyState',{configurable:true,value:2});let seeks=0;Object.defineProperty(vB,'currentTime',{configurable:true,get:()=>0,set:()=>seeks++});cmpTick();return seeks;});assert.equal(count,0);
  },
  async cancelledReload(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'cancel.mp4');v._want=v._resume=true;Object.defineProperty(v,'currentSrc',{configurable:true,value:'http://example.test/cancel.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});Object.defineProperty(v,'error',{configurable:true,value:{code:2}});window.intents=[];Object.defineProperty(v,'src',{configurable:true,get:()=> 'http://example.test/cancel.mp4',set:()=>intents.push(v._want)});});
   await page.clock.runFor(2600);await page.evaluate(()=>stopDead(v));await page.clock.runFor(20000);
   assert.deepEqual(await page.evaluate(()=>intents.slice(0,2)),[true,false],'cancelling a pending reload cancels later automatic playback');
  },
  async foregroundTimerOrder(page){
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));window.aborted=false;window.fetch=async(key,{signal})=>new Response(new ReadableStream({start(c){signal.addEventListener('abort',()=>{window.aborted=true;c.error(new Error('aborted'));});}}),{headers:{'Content-Type':'video/mp4'}});clipFetch('resume.mp4');});
   await page.clock.setSystemTime(new Date(Date.now()+20000));
   await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
   await page.clock.runFor(500);assert.equal(await page.evaluate(()=>aborted),false,'resumed timer may run before visibilitychange');
   await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  },
  async fetchPercent(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{const real=fetch;window.fetch=async(...args)=>String(args[0]).includes('percent')?new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(65536));}}),{headers:{'Content-Type':'video/mp4','Content-Length':'131072'}}):real(...args);clipFetch('percent.mp4',true);});
   await page.waitForTimeout(1800);assert.equal(await page.evaluate(()=>CLIPS.get('percent.mp4').bytes/CLIPS.get('percent.mp4').total),.5,'prefetch tracks byte progress without blocking the player');
  },
  async fetchProgress(page){

   await page.evaluate(()=>{window.savedFetch=fetch;window.fetch=async()=>new Response(new ReadableStream({start(c){let n=0;const h=setInterval(()=>{c.enqueue(new Uint8Array([1]));if(++n===5){clearInterval(h);c.close();}},4000);}}),{headers:{'Content-Type':'video/mp4'}});window.fetchDone=false;clipFetch('slow.mp4').then(url=>{window.fetchDone=url.startsWith('blob:');});});
   await page.clock.runFor(21000);assert.equal(await page.evaluate(()=>fetchDone),true);
  },
 })){
  if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(label))continue;
  const context=await browser.newContext(name==='webkit'?devices['iPhone 13']:{}),page=await context.newPage();
  await page.addInitScript(small=>{if(small)window.CLIP_CACHE_LIMIT=2*1024*1024;window.liveClips=new Map();window.revoked=0;window.revokedActive=0;const create=URL.createObjectURL,revoke=URL.revokeObjectURL;URL.createObjectURL=b=>{const u=create(b);liveClips.set(u,b.size);return u;};URL.revokeObjectURL=u=>{revoked++;if([...document.querySelectorAll('video')].some(v=>v.src===u))revokedActive++;liveClips.delete(u);revoke(u);};},label==='lru');
  try{if(['hiddenStall','byteProgress','fetchProgress','retryBudget','cancelledReload','foregroundTimerOrder','routeStall','routeBackoff','routeError','compareForegroundStill','byteCeiling','recoveredBudget','compareAutoStill','compareStallPause'].includes(label))await page.clock.install();await page.goto(process.env.SITE_E2E_URL);await test(page);results.push({engine:name,case:label,pass:true});}
  catch(error){results.push({engine:name,case:label,pass:false,error:String(error.message)});}
  console.log(name,label,results.at(-1).pass,results.at(-1).error||'');await context.close();
 }
 await browser.close();
}
console.log(JSON.stringify(results,null,2));
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(r=>!r.pass)?1:0;
