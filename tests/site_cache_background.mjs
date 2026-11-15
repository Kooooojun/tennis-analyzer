// The Range fixture pauses after 64 KiB. Verify actual visibility, not merely tab focus.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const {chromium,webkit,devices}=await import(process.env.PLAYWRIGHT_MODULE);
const name=process.env.SITE_ENGINE||'chromium',engine=name==='webkit'?webkit:chromium;
const browser=await engine.launch(name==='chromium'?{
 headless:false,...(process.env.SITE_CHROMIUM_EXECUTABLE?{executablePath:process.env.SITE_CHROMIUM_EXECUTABLE}:{}),
 ignoreDefaultArgs:['--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding','--disable-background-timer-throttling'],
}:{headless:true});
try{
 const context=await browser.newContext(name==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(process.env.SITE_E2E_URL);await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));await page.waitForFunction(()=>S);
 const id=name+'-'+Date.now();
 await page.evaluate(id=>{window.sawFailure=false;setInterval(()=>{if(v.parentElement.querySelector('[data-fail]'))window.sawFailure=true;},100);ALL[3].src+='?gap=12&case='+id;load(3,false);},id);
 await page.waitForTimeout(400);const front=await context.newPage();
 // Playwright forces focus in each renderer. Its own protocol session must release that override.
 if(name==='chromium'){
  for(const p of [page,front])await p._connection.toImpl(p).delegate._mainFrameSession._client.send('Emulation.setFocusEmulationEnabled',{enabled:false});
  await front.bringToFront();
 }else await page._connection.toImpl(page).delegate._pageProxySession.send('Emulation.setActiveAndFocused',{active:false});
 await page.waitForFunction(()=>document.hidden);
 await new Promise(r=>setTimeout(r,20000));
 const hidden=await page.evaluate(()=>({state:document.visibilityState,failed:sawFailure,ready:v.readyState})),start=Date.now();
 if(name==='chromium'){await front.close();await page._connection.toImpl(page).delegate._mainFrameSession._client.send('Emulation.setFocusEmulationEnabled',{enabled:true});await page.bringToFront();}
 else await page._connection.toImpl(page).delegate._pageProxySession.send('Emulation.setActiveAndFocused',{active:true});
 await page.waitForFunction(()=>!document.hidden);
 let playable=false,seconds=null;
 try{
  await page.waitForFunction(()=>v.readyState>=2&&!v.parentElement.querySelector('[data-fail]'),null,{timeout:30000});
  await page.evaluate(()=>{v._testTime=v.currentTime;v.play().catch(()=>{});});await page.waitForFunction(()=>v.currentTime>v._testTime);
  playable=true;seconds=(Date.now()-start)/1000;
 }catch{}
 const events=fs.readFileSync(process.env.SITE_SERVER_LOG,'utf8').trim().split('\n').map(s=>JSON.parse(s)).filter(e=>e.case===id);
 const result={engine:name,hidden,failed:await page.evaluate(()=>sawFailure),playable,seconds,requests:events.filter(e=>e.event==='request').length,aborts:events.filter(e=>e.event==='abort').length,errors,events};
 console.log(JSON.stringify(result,null,2));if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(result,null,2));
 if(!process.env.SITE_BASELINE){assert.equal(hidden.state,'hidden');assert(playable);assert(!result.failed);assert.equal(result.requests,1);assert.equal(result.aborts,0);assert.deepEqual(errors,[]);}
}finally{await browser.close();}
