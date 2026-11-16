// Local Range fixture: force native fallback and freeze media progress while real bytes trickle in.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const results=[];
for(const [name,engine] of Object.entries({chromium,webkit})){
 const browser=await engine.launch();
 try{
  const context=await browser.newContext(name==='webkit'?devices['iPhone 13']:{}),page=await context.newPage();
  await page.goto(process.env.SITE_E2E_URL);
  await page.evaluate(()=>{window.fetch=()=>Promise.reject(new TypeError('native fallback'));go(DAY_KEYS[0],'stroke');});await page.waitForFunction(()=>v.readyState>=2);
  const id=name+'-'+Date.now();
  await page.evaluate(id=>{
   window.assignments=[];window.progressCount=0;window.dripStart=Date.now();
   const src=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'src');
   Object.defineProperty(v,'src',{configurable:true,get(){return src.get.call(this);},set(u){assignments.push((Date.now()-dripStart)/1000);src.set.call(this,u);}});
   ALL[3].src+='?chunk=1024&interval=2&case='+id;load(3,false);v._want=v._resume=true;
   Object.defineProperty(v,'readyState',{configurable:true,value:0});Object.defineProperty(v,'buffered',{configurable:true,value:{length:0}});Object.defineProperty(v,'currentTime',{configurable:true,get:()=>0,set:()=>{}});
   v.addEventListener('progress',()=>progressCount++);
  },id);
  let bounded=true;try{await page.waitForFunction(()=>assignments.length>=2,null,{timeout:35000});}catch{bounded=false;}
  await page.waitForTimeout(300);
  const state=await page.evaluate(()=>({assignments,progressCount}));
  const events=fs.readFileSync(process.env.SITE_SERVER_LOG,'utf8').trim().split('\n').map(s=>JSON.parse(s)).filter(e=>e.case===id),chunks=events.filter(e=>e.event==='chunk');
  results.push({engine:name,bounded,...state,chunkCount:chunks.length,chunkBytes:[...new Set(chunks.map(e=>e.bytes))]});console.log(JSON.stringify(results.at(-1)));if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
  if(!process.env.SITE_BASELINE){assert(bounded);assert(state.assignments[1]>=(state.progressCount>=8?29:10)&&state.assignments[1]<=33);assert(chunks.length>=5);assert(chunks.every(e=>e.bytes===1024||e.bytes===2));}
 }finally{await browser.close();}
}
console.log(JSON.stringify(results,null,2));if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
