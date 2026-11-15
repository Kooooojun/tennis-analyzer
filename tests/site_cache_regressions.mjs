// Run against the fixture server; each case gets an independent browser page.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium,webkit,devices}=await import(process.env.PLAYWRIGHT_MODULE);
const results=[];
for(const [name,engine] of Object.entries({chromium,webkit})){
 const browser=await engine.launch();
 for(const [label,test] of Object.entries({
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
  async hiddenStall(page){

   await page.evaluate(()=>{go(DAY_KEYS[0],'stroke');});await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'hidden.mp4');Object.defineProperty(document,'hidden',{configurable:true,value:true});Object.defineProperty(v,'currentSrc',{configurable:true,value:'hidden.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});v._fetching=false;window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'hidden.mp4',set:()=>window.reloads++});});
   await page.clock.runFor(25000);
   assert.deepEqual(await page.evaluate(()=>({reloads,failed:!!v.parentElement.querySelector('[data-fail]')})),{reloads:0,failed:false});
  },
  async byteProgress(page){
   await page.evaluate(()=>{go(DAY_KEYS[0],'stroke');});await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{resetClip(v,'progress.mp4');Object.defineProperty(v,'currentSrc',{configurable:true,value:'progress.mp4'});Object.defineProperty(v,'readyState',{configurable:true,value:0});v._fetching=false;window.reloads=0;Object.defineProperty(v,'src',{configurable:true,get:()=> 'progress.mp4',set:()=>window.reloads++});setInterval(()=>v.dispatchEvent(new Event('progress')),2000);});
   await page.clock.runFor(12500);assert.equal(await page.evaluate(()=>reloads),0);
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
   await page.evaluate(()=>go(DAY_KEYS[0],'overview'));await page.waitForTimeout(200);assert.equal(requests.length,0,'overview fetches none');
   await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>{if(!S)return false;const list=visible(),i=list.indexOf(S);return CLIPS.get(list[(i-1+list.length)%list.length].src)?.url;});
   const expected=await page.evaluate(()=>{const list=visible();const i=list.indexOf(S);return [S.src,list[(i+1)%list.length].src,list[(i-1+list.length)%list.length].src].map(u=>new URL(u,location.href).href);});assert.deepEqual(requests.slice(0,3),expected);
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
   await page.waitForFunction(()=>vA.readyState>=1&&vB._fetching);
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
   await page.evaluate(()=>{const real=fetch;let bad=true;window.fetch=async(...args)=>{if(bad&&String(args[0]).includes('badcase')){bad=false;return new Response('broken',{headers:{'Content-Type':'video/mp4'}});}return real(...args);};ALL[3].src+='?badcase';load(3,false);});
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
  async blockedPartner(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>{vB.play=()=>Promise.reject(new DOMException('blocked','NotAllowedError'));cmpStart();});
   await page.waitForTimeout(100);
   assert.deepEqual(await page.evaluate(()=>[vA.paused,vB.paused,$('cmpPlay').textContent.includes('▶')]),[true,true,true]);
  },
  async partnerRetry(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   await page.evaluate(()=>{window.goodPartner=vB.src;cmpStart();vB.src='data:video/mp4,broken';});
   await page.waitForFunction(()=>vB.parentElement.querySelector('[data-fail]'));
   await page.evaluate(()=>{Object.defineProperty(vB,'currentSrc',{configurable:true,get:()=>goodPartner});vB.parentElement.querySelector('.vid-msg').click();});
   await page.waitForFunction(()=>!vA.paused&&!vB.paused&&vB.readyState>=2);
   assert.equal(await page.evaluate(()=>$('cmpPlay').textContent.includes('⏸')),true);
  },
  async emptyBuffer(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
   const count=await page.evaluate(()=>{stopDead(vA);Object.defineProperty(vB,'readyState',{configurable:true,value:2});let seeks=0;Object.defineProperty(vB,'currentTime',{configurable:true,get:()=>0,set:()=>seeks++});cmpTick();return seeks;});assert.equal(count,0);
  },
  async fetchPercent(page){
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
   await page.evaluate(()=>{const real=fetch;window.fetch=async(...args)=>String(args[0]).includes('percent')?new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(65536));}}),{headers:{'Content-Type':'video/mp4','Content-Length':'131072'}}):real(...args);ALL[3].src+='?percent';load(3,false);});
   await page.waitForTimeout(1800);assert.match(await page.evaluate(()=>v.parentElement.querySelector('.vid-msg').textContent),/50%/);
  },
  async fetchProgress(page){

   await page.evaluate(()=>{window.savedFetch=fetch;window.fetch=async()=>new Response(new ReadableStream({start(c){let n=0;const h=setInterval(()=>{c.enqueue(new Uint8Array([1]));if(++n===5){clearInterval(h);c.close();}},4000);}}),{headers:{'Content-Type':'video/mp4'}});window.fetchDone=false;clipFetch('slow.mp4').then(url=>{window.fetchDone=url.startsWith('blob:');});});
   await page.clock.runFor(21000);assert.equal(await page.evaluate(()=>fetchDone),true);
  },
 })){
  if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(label))continue;
  const context=await browser.newContext(name==='webkit'?devices['iPhone 13']:{}),page=await context.newPage();
  await page.addInitScript(small=>{if(small)window.CLIP_CACHE_LIMIT=2*1024*1024;window.liveClips=new Map();window.revoked=0;window.revokedActive=0;const create=URL.createObjectURL,revoke=URL.revokeObjectURL;URL.createObjectURL=b=>{const u=create(b);liveClips.set(u,b.size);return u;};URL.revokeObjectURL=u=>{revoked++;if([...document.querySelectorAll('video')].some(v=>v.src===u))revokedActive++;liveClips.delete(u);revoke(u);};},label==='lru');
  try{if(['hiddenStall','byteProgress','fetchProgress','retryBudget'].includes(label))await page.clock.install();await page.goto(process.env.SITE_E2E_URL);await test(page);results.push({engine:name,case:label,pass:true});}
  catch(error){results.push({engine:name,case:label,pass:false,error:String(error.message)});}
  console.log(name,label,results.at(-1).pass,results.at(-1).error||'');await context.close();
 }
 await browser.close();
}
console.log(JSON.stringify(results,null,2));
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(r=>!r.pass)?1:0;
