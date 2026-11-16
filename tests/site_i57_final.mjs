// #57 PR4：只用合成場次，覆蓋載入失敗、日期軸與直式影片提示。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';

const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(),results=[];
const portrait=execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','testsrc2=s=180x320:r=60:d=3','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-movflags','frag_keyframe+empty_moov','-f','mp4','pipe:1']);
const history=dates=>dates.map((date,i)=>({session:`sample-${i}`,date,camera:'合成鏡頭',knee_src:'3D',score_version:9,items:{total:7,consistency:6}}));
async function chart(page,dates){
 await page.route('**/trend.js*',route=>route.fulfill({contentType:'text/javascript',body:`window.TREND=[${JSON.stringify({player:'me',kind:'FH',history:history(dates),flags:[]})}];`}));
 await page.goto(f.url);
 await page.locator('svg.spark').waitFor();
 return page.locator('svg.spark').evaluate(svg=>({
  dots:[...svg.querySelectorAll('circle[fill="var(--accent)"]')].map(c=>+c.getAttribute('cx')),
  ticks:[...svg.querySelectorAll('line')].filter(l=>l.getAttribute('x1')===l.getAttribute('x2')).map(l=>+l.getAttribute('x1')),
  texts:[...svg.querySelectorAll('text')].map(t=>{const b=t.getBBox();return {text:t.textContent,x:+t.getAttribute('x'),y:+t.getAttribute('y'),box:{x:b.x,y:b.y,width:b.width,height:b.height}};}),
  width:svg.viewBox.baseVal.width,height:svg.viewBox.baseVal.height,
 }));
}
const cases={
 async fullLoadFailure(page){
  let broken=true;
  await page.route('**/manifest.js*',route=>broken?route.fulfill({status:503,body:''}):route.continue());
  await page.goto(f.url);
  const alert=page.getByRole('alert');
  assert.equal(await alert.count(),1,'全站腳本失敗須有 alert');
  assert.match(await alert.textContent(),/載入失敗/);
  const retry=alert.getByRole('button',{name:'重試'});
  assert.equal(await retry.count(),1,'失敗提示須有重試按鈕');
  broken=false;
  await retry.focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>typeof DAY_KEYS!=='undefined'&&DAY_KEYS.length===1&&document.querySelector('#home .sess a'));
  assert.equal(await alert.count(),0,'重試成功須移除失敗提示');
 },
 async partialLoadFailure(page){
  let broken=true;
  await page.route('**/manifest.js*',route=>route.fulfill({contentType:'text/javascript',body:'window.SESSION_IDS=["synthetic","missing"];'}));
  await page.route('**/missing/data.js*',route=>route.fulfill({contentType:'text/javascript',body:broken?'':`window.SESSIONS.push({...window.SESSIONS[0],id:'missing',label:'恢復場次'});`,status:broken?503:200}));
  await page.goto(f.url);
  assert.equal(await page.locator('#home .sess a').count(),1,'部分載入失敗仍須顯示可用場次');
  const retry=page.getByRole('alert').getByRole('button',{name:'重試'});
  assert.equal(await retry.count(),1,'部分失敗須可重試');
  broken=false;await retry.click();
  await page.waitForFunction(()=>document.querySelectorAll('#home .sess a').length===2);
 },
 async poseAnnouncement(page){
  await page.route('**/pose/*.js*',route=>route.fulfill({status:503,body:''}));
  await page.goto(f.url);
  await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
  await page.waitForFunction(()=>S?._poseFails===1);
  assert.equal(await page.locator('.pose-live[role="status"][aria-live="polite"]').count(),3,'三播放器須沿用常駐 live region');
  const live=page.locator('#stage .pose-live');
  assert.equal(await live.textContent(),await page.locator('#stage .pose-msg').textContent());
  assert.equal(await live.evaluate(e=>e.hidden||getComputedStyle(e).display==='none'),false,'live region 不可隱藏於讀屏');
 },
 async dateTicks(page){
  const c=await chart(page,['2026-01-01','2026-01-02','2026-02-01']);
  assert.equal(c.ticks.length,3,'每個日期都須畫刻度，即使標籤被略過');
  assert(Math.abs((c.dots[1]-c.dots[0])/(c.dots[2]-c.dots[0])-1/31)<.001,'日期軸須依日數比例');
  assert(c.texts.filter(t=>t.text.includes('/')).length<3,'相距不足 40 px 只能略過文字');
 },
 async sameDate(page){
  const c=await chart(page,['2026-01-01','2026-01-01','2026-02-01']);
  assert(c.dots[1]-c.dots[0]>=9,'同日同分兩場的圓點不可重疊');
  assert.equal(c.ticks.length,2,'同日場次共用日期刻度');
  assert(c.dots.every(x=>x>=4.5&&x<=c.width-4.5),'偏移後圓點不可裁切');
 },
 async missingDate(page){
  const c=await chart(page,['2026-02-01',null,'2026-01-02','2026-01-01']);
  assert(c.texts.some(t=>t.text==='無日期'),'缺日期須明示無日期');
  assert(c.dots.every((x,i)=>!i||x>c.dots[i-1]),'亂序資料須先按日期排，缺日期接在最後');
  assert(Math.abs((c.dots[1]-c.dots[0])/(c.dots[2]-c.dots[0])-1/31)<.001,'缺日期不可讓已知日期變等距');
  assert.equal(c.ticks.length,4);
 },
 async labelsAndLegend(page){
  const c=await chart(page,['2026-01-01','2026-01-12','2026-02-01']);
  const labels=c.texts.filter(t=>t.text.includes('/')),legend=c.texts.filter(t=>t.text.startsWith('●'));
  assert(labels.length>=2,'日期軸須有可見日期');
  assert(Math.min(...legend.map(t=>t.box.y))-Math.max(...labels.map(t=>t.box.y+t.box.height))>=10,'日期標籤與圖例須至少間隔 10 px');
  assert(c.texts.every(t=>t.box.y+t.box.height<=c.height+.5),'文字不可超出 SVG');
 },
 async portraitMessage(page){
  await page.route('**/data.js*',async route=>{
   const response=await route.fetch();
   await route.fulfill({response,body:(await response.text()).replaceAll('"size":[640,360]','"size":[180,320]')});
  });
  await page.route('**/*.mp4*',route=>route.fulfill({contentType:'video/mp4',body:portrait}));
  await page.goto(f.url);await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
  await page.waitForFunction(()=>v.readyState>=2&&v.videoWidth===180&&v.videoHeight===320);
  await page.evaluate(()=>{const m=v.parentElement.querySelector('.vid-msg');m.textContent='影片載不到，點此重試';m.hidden=false;m.disabled=false;m.dataset.fail='';});
  const boxes=await page.evaluate(()=>({badge:document.getElementById('badge').getBoundingClientRect().toJSON(),message:document.querySelector('#stage .vid-msg').getBoundingClientRect().toJSON()}));
  assert(boxes.message.top>=boxes.badge.bottom+4,'提示須在時間 badge 下方至少 4 px');
 },
};
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   for(const [viewport,options] of [['desktop',{viewport:{width:1280,height:800}}],['iphone',devices['iPhone 13']]]){
    for(const [name,test] of Object.entries(cases)){
     const context=await browser.newContext(options),page=await context.newPage();
     try{
      await test(page);
      if(process.env.SITE_SCREENSHOTS&&['sameDate','missingDate','portraitMessage'].includes(name)){
       fs.mkdirSync(process.env.SITE_SCREENSHOTS,{recursive:true});
       await page.screenshot({path:`${process.env.SITE_SCREENSHOTS}/${engine.name()}-${viewport}-${name}.png`,fullPage:true});
      }
      results.push({engine:engine.name(),viewport,name,pass:true});
     }catch(e){results.push({engine:engine.name(),viewport,name,pass:false,error:e.message});}
     finally{await context.close();}
     console.log(JSON.stringify(results.at(-1)));
    }
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
if(process.env.SITE_RESULTS)fs.writeFileSync(process.env.SITE_RESULTS,JSON.stringify(results,null,2));
process.exitCode=results.some(r=>!r.pass)?1:0;
