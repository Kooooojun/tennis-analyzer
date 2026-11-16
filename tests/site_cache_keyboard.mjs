// Keyboard & screen-reader retry E2E (issue #55): real Tab/Enter, aria-live single announcement, disabled reset.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';

const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];

for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch();
 try{
  const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.goto(process.env.SITE_E2E_URL);
   await page.waitForFunction(()=>typeof ALL!=='undefined'&&ALL.length);
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
   await page.waitForFunction(()=>!!S&&v.readyState>=3&&!v.seeking);

   await page.evaluate(()=>{
    window.__failTexts=[];
    const m=v.parentElement.querySelector('.vid-msg');
    new MutationObserver(()=>{
     if(m.textContent.includes('影片載不到')) window.__failTexts.push(m.textContent);
    }).observe(m,{childList:true,characterData:true,subtree:true});
   });

   let broken=true;
   await page.route('**/*kbd-retry*',async route=>{
    if(broken) await route.fulfill({status:404,body:''});
    else await route.continue();
   });
   await page.evaluate(()=>{
    const u=new URL(S.src,location.href);
    u.searchParams.set('kbd-retry','1');
    S.src=u.href;
    load(ALL.indexOf(S),false);
   });
   await page.waitForFunction(()=>!!v.parentElement.querySelector('[data-fail]:not([disabled])'));
   await page.waitForTimeout(1200);

   const failInfo=await page.evaluate(()=>{
    const m=v.parentElement.querySelector('.vid-msg');
    return {ariaLive:m.getAttribute('aria-live'),failCount:window.__failTexts.length,disabled:m.disabled};
   });
   assert.equal(failInfo.ariaLive,'polite','失敗提示必須設定 aria-live="polite"');
   assert.equal(failInfo.failCount,1,'失敗提示 DOM 文字變化應只發生 1 次');
   assert.equal(failInfo.disabled,false,'失敗時重試按鈕應為可操作狀態');

   broken=false;
   let reached=false;
   for(let i=0;i<100;i++){
    await page.keyboard.press('Tab');
    if(await page.evaluate(()=>document.activeElement===v.parentElement.querySelector('.vid-msg'))){
     reached=true;
     break;
    }
   }
   assert.equal(reached,true,`${engine} 按 Tab 必須能聚焦到重試按鈕`);

   await page.keyboard.press('Enter');
   await page.waitForFunction(()=>v.readyState>=3&&!v.error&&!v.seeking&&!v._reloading&&!v.paused,null,{timeout:7000});
   await page.evaluate(()=>{v.playbackRate=1;});
   const t0=await page.evaluate(()=>v.currentTime);
   await page.waitForTimeout(250);
   assert(await page.evaluate(t=>v.currentTime>t+0.05,t0),'按 Enter 重試後影片必須實際恢復播放');

   await page.waitForTimeout(1200);
   const after=await page.evaluate(()=>{
    const m=v.parentElement.querySelector('.vid-msg');
    return {hidden:m.hidden,disabled:m.disabled,text:m.textContent,failCount:window.__failTexts.length};
   });
   assert.equal(after.hidden,true,'恢復播放後提示應隱藏');
   assert.equal(after.disabled,true,'恢復播放後 disabled 狀態必須重設為 true');
   assert.equal(after.text,'','恢復播放後應清空提示文字');
   assert.equal(after.failCount,1,'恢復播放後不應再重複觸發失敗提示');

   // Verify disabled is also reset when recovery happens via loadedmetadata/canplay without clicking retry.
   broken=true;
   const validUrl=await page.evaluate(()=>{
    const u=new URL(S.src,location.href);
    u.searchParams.delete('kbd-retry');
    return u.href;
   });
   await page.evaluate(()=>{
    const u=new URL(S.src,location.href);
    u.searchParams.set('kbd-retry','2');
    S.src=u.href;
    load(ALL.indexOf(S),false);
   });
   await page.waitForFunction(()=>!!v.parentElement.querySelector('[data-fail]:not([disabled])'));
   broken=false;
   await page.evaluate(u=>{v.src=u;v.load();},validUrl);
   await page.waitForFunction(()=>v.readyState>=3&&!v.error&&v.parentElement.querySelector('.vid-msg').hidden);
   const autoRecovered=await page.evaluate(()=>{
    const m=v.parentElement.querySelector('.vid-msg');
    return {hidden:m.hidden,disabled:m.disabled,text:m.textContent};
   });
   assert.equal(autoRecovered.hidden,true,'自動恢復時應隱藏提示');
   assert.equal(autoRecovered.disabled,true,'自動恢復時 disabled 必須重設為 true');
   assert.equal(autoRecovered.text,'','自動恢復時應清空提示文字');

   assert.deepEqual(errors,[]);
   results.push({engine,pass:true});
  }catch(e){
   results.push({engine,pass:false,error:e.message,errors});
  }finally{
   await context.close();
  }
 }finally{
  await browser.close();
 }
 console.log(JSON.stringify(results.at(-1)));
}

if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
