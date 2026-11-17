// Synthetic media exercises contact offsets and short edge clips in both browser engines.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const runs=Number(process.env.SITE_COMPARE_RUNS||1),traceDir=process.env.SITE_COMPARE_TRACE;
assert(Number.isInteger(runs)&&runs>=1&&runs<=100,'SITE_COMPARE_RUNS 須為 1–100 的整數');
const mutation=process.env.SITE_COMPARE_MUTATION||'';
assert(['','unpaired','frame-stall'].includes(mutation),'SITE_COMPARE_MUTATION 僅支援 unpaired 或 frame-stall');
if(traceDir)fs.mkdirSync(traceDir,{recursive:true});
const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'site-compare-')),clips=[];
try{
 for(const duration of [3,1.5]){
  const file=path.join(scratch,`clip-${duration}.mp4`);
  execFileSync('ffmpeg',['-v','error','-f','lavfi','-i',`testsrc2=s=160x90:r=60:d=${duration}`,'-an','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-movflags','+faststart',file]);
  clips.push(fs.readFileSync(file));fs.unlinkSync(file);
 }
}finally{for(const file of fs.readdirSync(scratch))fs.unlinkSync(path.join(scratch,file));fs.rmdirSync(scratch);}
const results=[];
for(const [engine,type] of Object.entries({chromium,webkit})){
 const browser=await type.launch();
 for(let run=1;run<=runs;run++)for(const offset of [30,-60]){
  const context=await browser.newContext(engine==='webkit'?devices['iPhone 13']:{}),page=await context.newPage(),errors=[];
  let state={};
  page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.route('**/edge-synthetic-*.mp4',route=>{
    const data=clips[route.request().url().includes('synthetic-a')?0:1],range=/bytes=(\d+)-(\d*)/.exec(route.request().headers().range||'');
    const start=range?+range[1]:0,end=range&&range[2]?Math.min(+range[2],data.length-1):data.length-1;
    return route.fulfill({status:range?206:200,headers:{'Content-Type':'video/mp4','Accept-Ranges':'bytes','Content-Length':String(end-start+1),...(range?{'Content-Range':`bytes ${start}-${end}/${data.length}`}:{})},body:data.subarray(start,end+1)});
   });
   await page.goto(process.env.SITE_E2E_URL);await page.waitForFunction(()=>typeof ALL!=='undefined'&&ALL.length>1);
   await page.evaluate(()=>go(DAY_KEYS[0],'video'));await page.locator('#vA').scrollIntoViewIfNeeded();
   await page.evaluate(offset=>{
    const contact=offset>0?45:90,a={...ALL[0],src:'edge-synthetic-a.mp4',contact},b={...ALL[1],src:'edge-synthetic-b.mp4',contact:contact+offset};
    cmpLoad(a,b);cmpRate=1;
   },offset);
   await page.waitForFunction(()=>[vA,vB].every(x=>x.readyState>=3&&!x.seeking));
   await page.evaluate(({trace,mutation})=>{
    if(trace){
     window.edgeTrace=[];
     window.edgeSnapshot=(event,side,metadata)=>edgeTrace.push({at:performance.now(),event,side,times:[vA.currentTime,vB.currentTime],paused:[vA.paused,vB.paused],seeking:[vA.seeking,vB.seeking],ready:[vA.readyState,vB.readyState],metadata});
     for(const [i,x] of [vA,vB].entries()){
      for(const event of ['play','playing','pause','timeupdate','seeking','seeked','waiting','canplay','ended'])x.addEventListener(event,()=>edgeSnapshot(event,i));
      if(x.requestVideoFrameCallback){const frame=(now,metadata)=>{edgeSnapshot('rVFC',i,{now,...metadata});x.requestVideoFrameCallback(frame);};x.requestVideoFrameCallback(frame);}
     }
    }
    window.edgeStats={loops:0,advance:0,unpairedMs:0,endpointSamples:0,pauseCalls:0};
    let previous=[vA.currentTime,vB.currentTime],jumped=[false,false];
    for(const [i,x] of [vA,vB].entries())for(const event of ['seeking','seeked'])x.addEventListener(event,()=>{jumped[i]=true;});
    const pause=vA.pause.bind(vA);vA.pause=()=>{edgeStats.pauseCalls++;pause();};
    setInterval(()=>{
     const times=[vA.currentTime,vB.currentTime],raw=times[0]+cmpOff()/FPS,delta=times.map((t,i)=>t-previous[i]);
     if(delta[0]<-1)edgeStats.loops++;
     if(delta[0]>0&&delta[0]<.1)edgeStats.advance+=delta[0];
     if(raw>1.5/FPS&&raw<vB.duration-1.5/FPS){
      for(const [i,x] of [vA,vB].entries()){
       const other=[vA,vB][1-i];
       if(delta[i]>.00005&&delta[i]<.1&&!jumped[i]&&!x.paused&&!x.seeking&&(other.paused||other.readyState<3||other.error)){edgeStats.unpairedMs+=delta[i]*1000;window.edgeSnapshot?.('unpaired',i,{previous,times,delta,jumped});}
      }
     }else if((raw<0||raw>=vB.duration)&&vB.paused&&Math.abs(times[1]-Math.max(0,Math.min(vB.duration,raw)))<1/FPS)edgeStats.endpointSamples++;
     previous=times;jumped=[false,false];
    },10);
    // Mutation removes pairing while leaving A's render loop and real media playback running.
    if(mutation==='unpaired')cmpTick=()=>{cmpRender(Math.floor(vA.currentTime*FPS));if(!vA.paused)cmpRequest=vA.requestVideoFrameCallback?vA.requestVideoFrameCallback(cmpTick):requestAnimationFrame(cmpTick);};
    if(mutation==='frame-stall'&&vA.requestVideoFrameCallback){
     const request=vA.requestVideoFrameCallback.bind(vA);let until=0;
     vA.requestVideoFrameCallback=callback=>request((now,metadata)=>{
      if(!until&&vA.currentTime>=.9&&vA.currentTime<1)until=performance.now()+180;
      const delay=until-performance.now();
      if(delay>0)setTimeout(()=>callback(now,metadata),delay);else callback(now,metadata);
     });
    }
    cmpStart();
   },{trace:!!traceDir,mutation});
   await page.waitForTimeout(7200);
   state=await page.evaluate(()=>({...edgeStats,want:vA._want,paused:vA.paused}));
   if(traceDir)fs.writeFileSync(path.join(traceDir,`${engine}-offset${offset}-run${run}.json`),JSON.stringify(await page.evaluate(()=>edgeTrace),null,2));
   assert(state.loops>=1&&state.advance>3.5,'偏移比較必須持續前進超過一個完整循環');
   assert(state.pauseCalls<=20,'端點不得反覆暫停與 seek');
   assert.equal(state.unpairedMs,0,'共同可播區間不得單側前進');
   assert(state.endpointSamples>5,'缺少另一側畫面時必須停在端點等待');
   assert(state.want&&!state.paused,'比較區不得卡在待播狀態');assert.deepEqual(errors,[]);
   results.push({engine,offset,run,pass:true,...state});
  }catch(e){results.push({engine,offset,run,pass:false,...state,error:e.message});}
  console.log(JSON.stringify(results.at(-1)));await context.close();
 }
 await browser.close();
}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(x=>!x.pass)?1:0;
