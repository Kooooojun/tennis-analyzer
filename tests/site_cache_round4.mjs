// Local-only real-media regressions. Use SITE_E2E_URL and PLAYWRIGHT_MODULE as in test_site_smoke.py.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch();
 for(const [name,test] of Object.entries({
  async coldStream(page){await page.waitForFunction(()=>v.readyState>=2);assert.equal(await page.evaluate(()=>v.src.startsWith('blob:')),false);},
  async playPrep(page){
   await page.evaluate(()=>{window.firstTime=null;window.preparingButtons=[];v.addEventListener('playing',()=>{if(v._want&&firstTime===null)firstTime=v.currentTime;});v.addEventListener('pause',()=>{if(v._want&&!v.paused&&firstTime===null)preparingButtons.push($('play').textContent);});toggle();});
   await page.waitForFunction(()=>firstTime!==null);assert.ok(await page.evaluate(()=>firstTime>=(S.contact-48+.5)/FPS-.03));
   const buttons=await page.evaluate(()=>preparingButtons);assert(buttons.length>0,'observe metadata pause before playing');assert(buttons.every(b=>b.includes('⏸')),'pending playback must keep the pause button');
  },
  async seekPending(page){await page.evaluate(()=>goto(100));await page.waitForFunction(()=>v.readyState>=2&&!v.seeking);assert.ok(Math.abs(await page.evaluate(()=>v.currentTime-(100+.5)/FPS))<.03);},
  async loadingKeyboard(page){
   await page.waitForTimeout(1100);const m=page.locator('#stage .vid-msg');assert.equal(await m.isDisabled(),true);
   await page.evaluate(()=>v.parentElement.querySelector('.vid-msg').focus());assert.equal(await page.evaluate(()=>document.activeElement===v.parentElement.querySelector('.vid-msg')),false);await page.keyboard.press('Enter');
   await page.evaluate(()=>v.parentElement.querySelector('.vid-msg').click());await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);assert.equal(await page.evaluate(()=>!!v.error),false);
  },
  async hiddenPrime(page){
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));window.hiddenPlays=0;const real=v.play.bind(v);v.play=()=>{hiddenPlays++;return real();};});
   await page.waitForTimeout(6500);assert.equal(await page.evaluate(()=>hiddenPlays),0);
  },
  async pendingBackground(page){
   await page.evaluate(()=>{toggle();Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
   assert.deepEqual(await page.evaluate(()=>[!!v._want,$('play').textContent.includes('▶')]),[false,true]);
  },
  async prefetchDeadline(page){
   await page.clock.install();await page.evaluate(()=>{window.abortSeen=false;window.fetch=async(k,{signal})=>new Response(new ReadableStream({start(c){const h=setInterval(()=>c.enqueue(new Uint8Array(1024)),2000);signal.addEventListener('abort',()=>{abortSeen=true;clearInterval(h);c.error(new Error('aborted'));});}}),{headers:{'Content-Type':'video/mp4'}});clipFetch('drip-prefetch.mp4',true);});
   await page.clock.runFor(31000);assert.equal(await page.evaluate(()=>abortSeen),true);
  },
  async retryButton(page){
   await page.waitForFunction(()=>v.readyState>=2);await page.unroute('**/*.mp4*');
   const key=await page.evaluate(()=>S.src+'?retry-buttons');let broken=true;
   await page.route('**/*retry-buttons*',async route=>{if(broken)await route.fulfill({status:404,body:''});else {await new Promise(r=>setTimeout(r,1200));await route.continue();}});
   await page.evaluate(key=>{ALL[S.id].src=key;load(S.id,false);},key);
   await page.waitForFunction(()=>v.parentElement.querySelector('[data-fail]'));broken=false;
   await page.evaluate(()=>v.parentElement.querySelector('.vid-msg').click());
   assert.deepEqual(await page.evaluate(()=>[v._want,$('play').textContent.includes('⏸')]),[true,true]);
   await page.waitForTimeout(300);assert.deepEqual(await page.evaluate(()=>[v._want,$('play').textContent.includes('⏸')]),[true,true]);
   await page.waitForFunction(()=>v.readyState>=2&&!v.error&&!v.paused);assert.ok(await page.evaluate(()=>v.currentTime>=(S.contact-48+.5)/FPS-.03));
  },
  async loadingOverlay(page){
   await page.setViewportSize({width:667,height:375});await page.waitForFunction(()=>!v.parentElement.querySelector('.vid-msg').hidden);
   assert.equal(await page.evaluate(()=>getComputedStyle($('cv')).visibility),'hidden');
   await page.waitForFunction(()=>v.readyState>=2&&!v.seeking);await page.waitForTimeout(600);
   assert.equal(await page.evaluate(()=>getComputedStyle($('cv')).visibility),'visible');
  },
  async prefetchGate(page){
   await page.waitForFunction(()=>v.readyState>=2);const calls=await page.evaluate(async()=>{cancelPrefetch();Object.defineProperty(v,'buffered',{configurable:true,value:{length:0}});window.calls=0;const old=clipFetch;clipFetch=()=>{calls++;return Promise.resolve('x');};await preloadNeighbors(S);clipFetch=old;return calls;});assert.equal(calls,0);
  },
  async lowData(page){
   await page.waitForFunction(()=>v.readyState>=3&&v.buffered.length&&v.buffered.end(v.buffered.length-1)>=v.duration-.05);
   const count=await page.evaluate(async()=>{cancelPrefetch();window.calls=0;const old=clipFetch;clipFetch=()=>{calls++;return Promise.resolve('x');};try{for(const connection of [{saveData:true,effectiveType:'4g'},{saveData:false,effectiveType:'3g'},{saveData:false,effectiveType:'2g'}]){Object.defineProperty(navigator,'connection',{configurable:true,value:connection});await preloadNeighbors(S);}return calls;}finally{clipFetch=old;}});assert.equal(count,0);
  },
 })){
  if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(name))continue;
  const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage();
  try{
   await page.route('**/*.mp4*',async route=>{await new Promise(r=>setTimeout(r,name==='loadingOverlay'||name==='loadingKeyboard'?4000:1800));try{await route.continue();}catch{}});
   await page.goto(process.env.SITE_E2E_URL);await page.waitForFunction(()=>typeof ALL!=='undefined'&&ALL.length);
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>!!S&&!!v.offsetParent);
   await test(page);results.push({engine,case:name,pass:true});
  }catch(e){results.push({engine,case:name,pass:false,error:e.message});}
  console.log(engine,name,results.at(-1).pass,results.at(-1).error||'');await context.close();
 }
 await browser.close();
}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
