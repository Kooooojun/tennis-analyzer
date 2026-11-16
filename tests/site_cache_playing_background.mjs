// Local 25-second policy checks: controlled visibility keeps media active; natural uses real background; native-pause injects the native pause a browser policy may impose.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch(engine==='chromium'?{headless:false,...(process.env.SITE_CHROMIUM_EXECUTABLE?{executablePath:process.env.SITE_CHROMIUM_EXECUTABLE}:{}),ignoreDefaultArgs:['--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding','--disable-background-timer-throttling']}:{headless:true});
 for(const mode of ['continue-policy','natural','native-pause']){
  if(process.env.SITE_CASES&&!process.env.SITE_CASES.split(',').includes(mode))continue;
  const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.goto(process.env.SITE_E2E_URL);await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>[v,vA,vB].every(x=>x.readyState>=3));
   await page.evaluate(()=>{[v,vA,vB].forEach((x,i)=>Object.assign(x.parentElement.style,{position:'fixed',top:'100px',left:(i*33)+'%',width:'33%',height:'160px',zIndex:'1000',aspectRatio:'auto'}));});
   await page.waitForFunction(()=>[v,vA,vB].every(x=>x.readyState>=3&&!x.seeking&&!x._align&&!x._reloading));
   await page.evaluate(()=>{toggle();cmpStart();});await page.waitForFunction(()=>[v,vA,vB].every(x=>!x.paused&&x._want));
   await page.evaluate(()=>{window.hideCalls=[];window.updates=0;v.addEventListener('timeupdate',()=>updates++);for(const x of [v,vA,vB]){const native=x.pause.bind(x);x.pause=()=>{hideCalls.push({id:x.id,hidden:document.hidden});return native();};}});
   let front;
   if(mode==='continue-policy')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
   else { front=await context.newPage();
   if(engine==='chromium'){for(const p of [page,front])await p._connection.toImpl(p).delegate._mainFrameSession._client.send('Emulation.setFocusEmulationEnabled',{enabled:false});await front.bringToFront();}
   else await page._connection.toImpl(page).delegate._pageProxySession.send('Emulation.setActiveAndFocused',{active:false}); }
   // 背景頁會停止 rAF，須用計時輪詢觀察 visibility。
   await page.waitForFunction(()=>document.hidden,null,{polling:100});
   const beforePolicy=await page.evaluate(()=>({calls:hideCalls.length,states:[v,vA,vB].map(x=>({paused:x.paused,want:x._want}))}));
   if(mode==='native-pause')await page.evaluate(()=>{for(const x of [v,vA,vB])HTMLMediaElement.prototype.pause.call(x);});
   await new Promise(r=>setTimeout(r,25000));
   if(mode==='continue-policy')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
   else if(engine==='chromium'){await front.close();await page._connection.toImpl(page).delegate._mainFrameSession._client.send('Emulation.setFocusEmulationEnabled',{enabled:true});await page.bringToFront();}
   else await page._connection.toImpl(page).delegate._pageProxySession.send('Emulation.setActiveAndFocused',{active:true});
   await page.waitForFunction(()=>!document.hidden);await page.waitForTimeout(200);
   const state=await page.evaluate(()=>({paused:[v,vA,vB].map(x=>x.paused),buttons:[$('play').textContent,$('cmpPlay').textContent],updates}));
   if(mode==='continue-policy'){assert.equal(beforePolicy.calls,0,'hiding an already playing clip must not call pause');assert(state.paused.every(x=>!x));assert(state.updates>=5);}
   assert.equal(state.buttons[0].includes('⏸'),!state.paused[0]);assert.equal(state.buttons[1].includes('⏸'),!state.paused[1]);assert.equal(state.paused[1],state.paused[2]);
   if(mode==='native-pause')assert(state.paused.every(Boolean));
   assert.deepEqual(errors,[]);results.push({engine,mode,pass:true,beforePolicy,...state});
  }catch(e){results.push({engine,mode,pass:false,error:e.message,states:await page.evaluate(()=>[v,vA,vB].map(x=>({id:x.id,paused:x.paused,want:x._want,ready:x.readyState,seeking:x.seeking,align:!!x._align,reloading:!!x._reloading,error:x.error?.code})))});}
  console.log(JSON.stringify(results.at(-1)));await context.close();
 }
 await browser.close();
}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
