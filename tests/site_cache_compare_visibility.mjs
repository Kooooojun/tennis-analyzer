// 真實合成媒體跨循環；隱藏時停送 rAF，回前景後必須重新配對。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const runs=Number(process.env.SITE_VISIBILITY_RUNS||1);
assert(Number.isInteger(runs)&&runs>=1&&runs<=100,'SITE_VISIBILITY_RUNS 須為 1–100 的整數');
const f=await fixture(),results=[],scratch=fs.mkdtempSync(path.join(os.tmpdir(),'compare-visibility-')),clips=[];
try{
 for(const duration of [3,3.5]){
  const file=path.join(scratch,`${duration}.mp4`);
  execFileSync('ffmpeg',['-v','error','-f','lavfi','-i',`testsrc2=s=160x90:r=60:d=${duration}`,'-an','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-movflags','+faststart',file]);
  clips.push(fs.readFileSync(file));fs.unlinkSync(file);
 }
 for(const [engine,type] of Object.entries({chromium,webkit})){
  const browser=await type.launch();
  for(let run=1;run<=runs;run++){
  const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.addInitScript(()=>{
    const request=window.requestAnimationFrame.bind(window),cancel=window.cancelAnimationFrame.bind(window),jobs=new Map();let next=0;
    window.visibilityFrames={held:0};
    const deliver=(id,now)=>{
     const job=jobs.get(id);if(!job)return;
     job.native=null;
     if(document.hidden){visibilityFrames.held++;return;}
     jobs.delete(id);job.callback(now);
    };
    window.requestAnimationFrame=callback=>{const id=++next;const job={callback,native:request(now=>deliver(id,now))};jobs.set(id,job);return id;};
    window.cancelAnimationFrame=id=>{const job=jobs.get(id);if(job&&job.native!==null)cancel(job.native);jobs.delete(id);};
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)for(const [id,job] of jobs)if(job.native===null)job.native=request(now=>deliver(id,now));});
   });
   await page.route('**/visibility-*.mp4',route=>{
    const data=clips[route.request().url().includes('visibility-a')?0:1],range=/bytes=(\d+)-(\d*)/.exec(route.request().headers().range||'');
    const start=range?+range[1]:0,end=range&&range[2]?Math.min(+range[2],data.length-1):data.length-1;
    return route.fulfill({status:range?206:200,headers:{'Content-Type':'video/mp4','Accept-Ranges':'bytes','Content-Length':String(end-start+1),...(range?{'Content-Range':`bytes ${start}-${end}/${data.length}`}:{})},body:data.subarray(start,end+1)});
   });
   await page.goto(f.url);await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();
   await page.evaluate(()=>{cmpLoad({...ALL[0],src:'visibility-a.mp4',contact:90},{...ALL[1],src:'visibility-b.mp4',contact:90});cmpRate=1;});
   await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking&&!x._align&&!x._reloading));
   await page.evaluate(()=>{cmpGoto(132);});await page.waitForFunction(()=>[vA,vB].every(x=>!x.seeking));
   await page.evaluate(()=>{
    window.visibilityTrace=[];window.visibilityLoops=0;window.hiddenTicks=0;
    window.visibilitySnapshot=()=>({at:performance.now(),hidden:document.hidden,times:[vA.currentTime,vB.currentTime],paused:[vA.paused,vB.paused],want:[vA._want,vB._want],edge:[vA._edgeWait,vB._edgeWait],seeking:[vA.seeking,vB.seeking],ready:[vA.readyState,vB.readyState]});
    for(const x of [vA,vB])for(const event of ['seeking','seeked','pause','playing','ended'])x.addEventListener(event,()=>visibilityTrace.push({event,side:x.id,...visibilitySnapshot()}));
    vA.addEventListener('seeking',()=>{if(document.hidden&&vA.currentTime<.1)visibilityLoops++;});
    const tick=cmpTick;cmpTick=()=>{if(document.hidden)hiddenTicks++;return tick();};
    window.visibilityMetrics={unpairedMs:0,maxErrorMs:0,maxPost200Ms:0,samples:[]};
    let previous=[vA.currentTime,vB.currentTime],jumped=[false,false];
    for(const [i,x] of [vA,vB].entries())for(const event of ['seeking','seeked'])x.addEventListener(event,()=>{jumped[i]=true;});
    setInterval(()=>{
     const times=[vA.currentTime,vB.currentTime],delta=times.map((t,i)=>t-previous[i]),elapsed=performance.now()-window.visibilityReturnAt;
     if(elapsed>=0&&elapsed<=1000){
      const error=Math.abs(vB.currentTime-cmpBt())*1000;
      visibilityMetrics.maxErrorMs=Math.max(visibilityMetrics.maxErrorMs,error);
      if(elapsed>=200&&!vA.seeking&&!vB.seeking)visibilityMetrics.maxPost200Ms=Math.max(visibilityMetrics.maxPost200Ms,error);
      const raw=vA.currentTime+cmpOff()/FPS;
      if(raw>1.5/FPS&&raw<vB.duration-1.5/FPS)for(const [i,x] of [vA,vB].entries())if(delta[i]>.00005&&delta[i]<.1&&!jumped[i]&&!x.paused&&!x.seeking&&[vA,vB][1-i].paused)visibilityMetrics.unpairedMs+=delta[i]*1000;
      visibilityMetrics.samples.push({elapsed,times,paused:[vA.paused,vB.paused],seeking:[vA.seeking,vB.seeking],errorMs:error});
     }
     previous=times;jumped=[false,false];
    },10);
    cmpStart();
   });
   await page.waitForFunction(()=>[vA,vB].every(x=>!x.paused&&x._want));
   await page.evaluate(()=>{window.visibilityWitness=false;requestAnimationFrame(()=>{visibilityWitness=true;});Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});
   await page.waitForTimeout(2100);
   const hidden=await page.evaluate(()=>({...visibilitySnapshot(),loops:visibilityLoops,hiddenTicks,frames:visibilityFrames,witness:visibilityWitness}));
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});window.visibilityReturnAt=performance.now();document.dispatchEvent(new Event('visibilitychange'));});
   await page.waitForTimeout(200);
   const restored=await page.evaluate(()=>({...visibilitySnapshot(),syncError:Math.abs(vB.currentTime-cmpBt())}));
   await page.waitForTimeout(800);
   const advanced=await page.evaluate(()=>visibilitySnapshot()),trace=await page.evaluate(()=>visibilityTrace);
   const metrics=await page.evaluate(()=>visibilityMetrics);
   const row={engine,run,hidden,restored,advanced,metrics,trace};results.push(row);
   assert(hidden.loops>=1,'隱藏期間必須跨過 A 原生循環');
   assert(hidden.frames.held>=1&&!hidden.witness,'隱藏期間必須確實扣住 rAF 回呼');
   assert(restored.paused.every(x=>!x)&&restored.want.every(Boolean),'回前景後比較兩側必須保留意圖並恢復播放');
   assert(restored.syncError<=1.5/60,'回前景後必須按接觸偏移重新對齊');
   assert.equal(metrics.unpairedMs,0,'回前景後一秒內不得單側前進');
   assert(metrics.maxErrorMs<1.5/60*1000,'回前景後每輪一秒最大誤差必須小於既有 1.5 格門檻');
   assert(metrics.maxPost200Ms<=1.5/60*1000,'回前景穩定後同步誤差不可超過既有 1.5 格門檻');
   assert(metrics.samples.length>=50,'缺少回前景後一秒的計時樣本');
   assert(advanced.times.every((t,i)=>t-restored.times[i]>.3),'恢復後兩側必須持續前進');
   assert.deepEqual(errors,[]);row.pass=true;
  }catch(error){const row=results.at(-1);if(row?.engine===engine&&row.run===run)Object.assign(row,{pass:false,error:error.message});else results.push({engine,run,pass:false,error:error.message});}
  console.log(JSON.stringify(results.at(-1)));await context.close();
  }
  await browser.close();
 }
}finally{await f.close();for(const file of fs.readdirSync(scratch))fs.unlinkSync(path.join(scratch,file));fs.rmdirSync(scratch);}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
