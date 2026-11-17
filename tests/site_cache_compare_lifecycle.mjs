// 真實影片驗證播放中切換比較，以及片尾事件晚於使用者暫停的順序。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(),results=[];
try{
 for(const [engine,type] of Object.entries({chromium,webkit})){
  const browser=await type.launch();
  for(const name of ['reload-playing','reference-paused','pause-before-ended','hidden-native-pause','hidden-playing-before-pause','hidden-loader-before-pause']){
   const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[];let state={};
   page.on('pageerror',e=>errors.push(e.message));
   try{
    if(name.startsWith('hidden-'))await page.setViewportSize({width:400,height:300});
    await page.goto(f.url);await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();
    await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking&&!x._align&&!x._reloading));
    await page.evaluate(()=>{cmpRate=1;cmpGoto(132);});await page.waitForFunction(()=>[vA,vB].every(x=>!x.seeking));
    await page.evaluate(()=>cmpStart());await page.waitForFunction(()=>[vA,vB].every(x=>!x.paused&&x._want));
    if(name==='reload-playing'){
     await page.route('**/*cmp-reload*',async route=>{await new Promise(resolve=>setTimeout(resolve,250));await route.continue();});
     await page.evaluate(()=>{
      for(const id of [1,2]){ALL[id].src+='?cmp-reload=1';ALL[id].contact=110;}
      PRESETS.push({day:DAY_KEYS[0],a:[DAY_KEYS[0],2],b:[DAY_KEYS[0],3],label:'切換比較'});drawPresets();$('presets').lastElementChild.click();
     });
     await page.waitForTimeout(100);
     const loading=await page.evaluate(()=>({frame:cmpCur,edge:vB._edgeWait,paused:vA.paused,ready:[vA.readyState,vB.readyState]}));
     await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking&&!x._align&&!x._reloading));
     state=await page.evaluate(()=>({frame:cmpCur,expected:A.contact-48,edge:vB._edgeWait,paused:[vA.paused,vB.paused],time:vA.currentTime}));state.loading=loading;
     assert.equal(loading.frame,state.expected,'新片載入中不可讓殘留回呼覆寫比較起始格');
     assert.equal(loading.edge,false,'新片未就緒時不可誤設端點等待');
     assert.equal(state.frame,state.expected,'切換比較必須停在 contact−48');
     assert.equal(state.edge,false);assert(state.paused.every(Boolean));
     assert(Math.abs(state.time-(state.expected+.5)/60)<1/60);
    }else if(name==='hidden-native-pause'){
     await page.evaluate(()=>{
      Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));
      HTMLMediaElement.prototype.pause.call(vB);vB._loader.visibility();
     });
     await page.waitForFunction(()=>[vA,vB].every(x=>x.paused&&!x._want));
     state=await page.evaluate(()=>({paused:[vA.paused,vB.paused],want:[vA._want,vB._want],edge:vB._edgeWait,ended:vB.ended}));
     assert(!state.ended&&!state.edge,'沒有 ended 的原生政策暫停不可偽裝成端點等待');
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
     await page.waitForTimeout(50);assert(await page.evaluate(()=>[vA,vB].every(x=>x.paused&&!x._want)));
     await page.locator('#cmpPlay').click();await page.waitForFunction(()=>[vA,vB].every(x=>!x.paused&&x._want));
    }else if(name.startsWith('hidden-')){
     await page.evaluate(mode=>{
      cancelAnimationFrame(cmpRequest);vA.cancelVideoFrameCallback?.(cmpRequest);cmpRequest=null;
      const defer=event=>{if(document.hidden)event.stopImmediatePropagation();};vA.addEventListener('playing',defer,true);
      vB.addEventListener('pause',function ended(){if(!vB.ended)return;vB.removeEventListener('pause',ended,true);vA.removeEventListener('playing',defer,true);
       window.latePlaying={beforeEnded:vB.ended};if(mode==='hidden-loader-before-pause')vB._loader.visibility();else vA.dispatchEvent(new Event('playing'));latePlaying.afterEnded=vB.ended;
      },true);
      Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));
      vA.playbackRate=2;vB.playbackRate=1;
     },name);
     await page.waitForFunction(()=>window.latePlaying);await page.waitForTimeout(50);
     state=await page.evaluate(()=>({...latePlaying,want:[vA._want,vB._want],edge:vB._edgeWait,ended:vB.ended}));
     assert(state.beforeEnded,'必須由 B 真實片尾觸發晚到 playing');
     assert(state.afterEnded&&state.ended&&state.edge&&state.want.every(Boolean),name==='hidden-loader-before-pause'?'隱藏期片尾早於 pause 事件時，載入取樣不可清除續播意圖':'隱藏期晚到 playing 不可 seek 掉片尾並清除續播意圖');
     await page.evaluate(()=>window.scrollTo(0,0));await page.waitForFunction(()=>!shown(vA)&&!shown(vB));
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
     await page.locator('#vA').scrollIntoViewIfNeeded();
     await page.waitForFunction(()=>[vA,vB].every(x=>!x.paused&&x._want),null,{timeout:3000});
    }else{
     if(name==='reference-paused')await page.evaluate(()=>hold(vA));
     else await page.evaluate(()=>{
      // Pin the native end before the reference loop, without a drift correction winning the race.
      const tick=cmpTick;cancelAnimationFrame(cmpRequest);vA.cancelVideoFrameCallback?.(cmpRequest);cmpRequest=null;cmpTick=()=>{};window.restoreComparisonTick=()=>{cmpTick=tick;};vA.playbackRate=.1;
      const pause=()=>{if(vB.ended){vB.removeEventListener('pause',pause,true);$('cmpPlay').click();}};
      vB.addEventListener('pause',pause,true);
     });
     await page.waitForFunction(()=>vB.ended,null,{timeout:5000});await page.waitForTimeout(50);
     state=await page.evaluate(()=>({paused:[vA.paused,vB.paused],want:[vA._want,vB._want],edge:vB._edgeWait,ended:vB.ended}));
     assert(state.ended&&state.paused.every(Boolean)&&state.want.every(x=>!x),'使用者暫停後的片尾不得恢復播放意圖');
     assert.equal(state.edge,false,'沒有續播意圖的片尾不可變成端點等待');
     await page.evaluate(()=>window.restoreComparisonTick?.());
     await page.locator('#cmpPlay').click();await page.waitForFunction(()=>[vA,vB].every(x=>!x.paused&&x._want));
    }
    assert.deepEqual(errors,[]);results.push({engine,case:name,pass:true,...state});
   }catch(error){results.push({engine,case:name,pass:false,...state,error:error.message});}
   console.log(JSON.stringify(results.at(-1)));await context.close();
  }
  await browser.close();
 }
}finally{await f.close();}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
