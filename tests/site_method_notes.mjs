// #143 第 4–6 項與文件不一致：單拍有效骨架格數、方法說明（套件版本，舊場次「未記錄」）、免責句、暫定標示。
// 事前預測與失敗方式：testset/results/method-notes/pred.md。合成場次，不讀使用者資料。
// PLAYWRIGHT_MODULE 指向本機 playwright-core；不設 SITE_E2E_URL（跑合成 fixture）。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const DISCLAIMER='這是練習參考，不能代替教練或醫療判斷。';
const METHOD={mediapipe:'1.1.1 / 1.2.0',model:'pose_heavy.task',sha256:'ab'.repeat(32),url:'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task',method:'4',frames:1000,detected:840,interpolated:60,videos:3,recorded:2};
const poseJs=(id,frames)=>`POSE("synthetic",${id},${JSON.stringify({frames})});`;
const full=Array.from({length:17},(_,i)=>[.3+(i%3)*.1,.2+i*.025,.99]);
const zeros=Array.from({length:17},()=>[0,0,0]);  // 全 0 的骨架仍是骨架；null 才是沒偵測到
async function open(browser,{methodVer,viewport,mobile}={}){
 const context=await browser.newContext({viewport:viewport||{width:1280,height:800},isMobile:!!mobile,hasTouch:!!mobile}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/sessions/synthetic/data.js*',async route=>{
  const text=await (await route.fetch()).text(),head='window.SESSIONS=[',json=JSON.parse(text.slice(head.length,text.lastIndexOf(']')));
  if(methodVer!==undefined)json.methodVer=methodVer;  // undefined = 舊版 data.js（沒有這個欄位）
  await route.fulfill({contentType:'text/javascript; charset=utf-8',body:head+JSON.stringify(json)+'];'});
 });
 await page.route('**/pose/3.js*',route=>route.fulfill({contentType:'text/javascript; charset=utf-8',  // 第 3、7、8 格沒偵測到，第 10 格全 0
  body:poseJs(3,Array.from({length:180},(_,i)=>[3,7,8].includes(i)?null:i===10?zeros:full))}));
 await page.route('**/pose/6.js*',async route=>{await new Promise(r=>setTimeout(r,700));await route.fulfill({contentType:'text/javascript; charset=utf-8',body:poseJs(6,Array.from({length:180},()=>full))});});
 await page.goto(f.url);await page.waitForSelector('body.ready');
 return {page,context,errors};
}
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   for(const [label,opts] of [['桌機',{}],['手機 400px',{viewport:{width:400,height:800},mobile:true}]]){
    const tag=`${engine.name()} ${label}`;
    // ---- 單拍有效骨架格數 ----
    {
     const {page,context,errors}=await open(browser,opts);
     await page.evaluate(()=>go(DAY,'stroke'));
     await page.evaluate(()=>load(3,false));await page.waitForFunction(()=>S?.id===3&&S.frames?.length);
     const expected=await page.evaluate(()=>({n:S.frames.filter(x=>x!=null).length,m:S.frames.length}));
     check(expected.n===177&&expected.m===180,`${tag}：測試資料應是 177／180，得到 ${JSON.stringify(expected)}`);
     const t=(await page.locator('#poseCount').textContent()).replace(/\s+/g,'');
     check(t.includes('這拍有效骨架177／180格'),`${tag}：有效格數文字應含「這拍有效骨架 177／180 格」（null 不算、全 0 要算），得到「${t}」`);
     check(await page.locator('#poseCount').isVisible(),`${tag}：有效格數要看得到`);
     await page.evaluate(()=>load(5,false));await page.waitForFunction(()=>S?.id===5&&S.frames?.length);
     check((await page.locator('#poseCount').textContent()).replace(/\s+/g,'').includes('180／180格'),`${tag}：每格都有骨架時是 180／180`);
     await page.evaluate(()=>load(6,false));  // 骨架檔慢 700 ms：載入前不能顯示成 0／180
     const early=(await page.locator('#poseCount').textContent()).replace(/\s+/g,'');
     check(/載入中/.test(early)&&!/0／180/.test(early),`${tag}：骨架還沒到不能顯示 0 格，得到「${early}」`);
     await page.waitForFunction(()=>S?.id===6&&S.frames?.length);
     check((await page.locator('#poseCount').textContent()).replace(/\s+/g,'').includes('180／180格'),`${tag}：骨架到了之後更新`);
     check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：單拍無水平溢出`);
     check(!errors.length,`${tag}：單拍頁錯誤 ${errors}`);
     await context.close();
    }
    // ---- 方法說明：舊場次（欄位不存在／null）與有版本紀錄 ----
    for(const [name,methodVer] of [['舊 data.js（沒有欄位）',undefined],['methodVer 為 null',null],['有版本紀錄',METHOD]]){
     const {page,context,errors}=await open(browser,{...opts,methodVer});
     await page.evaluate(()=>go(DAY,'overview'));
     const note=(await page.locator('#methodNote').textContent()).replace(/\s+/g,' ');
     check(await page.locator('#methodNote').isVisible(),`${tag} ${name}：方法說明要看得到`);
     check(!/undefined|null|NaN/.test(note),`${tag} ${name}：方法說明不能出現 undefined／null／NaN：「${note}」`);
     if(methodVer){
      check(note.includes('1.1.1 / 1.2.0')&&note.includes('pose_heavy.task')&&note.includes('abababababab')&&note.includes('https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task'),`${tag} ${name}：版本、模型檔、sha256 前 12 碼、來源要寫出來：「${note}」`);
      check(/1000/.test(note)&&/840/.test(note)&&/60/.test(note)&&/內插/.test(note),`${tag} ${name}：有骨架與內插格數：「${note}」`);
      check(/3 支中 2 支有紀錄/.test(note),`${tag} ${name}：只有部分影片有紀錄要講「3 支中 2 支有紀錄」：「${note}」`);
      check(!note.includes('未記錄'),`${tag} ${name}：有紀錄時不寫未記錄：「${note}」`);
     }else check(note.includes('未記錄'),`${tag} ${name}：舊場次要寫「未記錄」：「${note}」`);
     check(/3D 估計.*單鏡頭.*僅供參考/.test(await page.locator('#overview').textContent()),`${tag} ${name}：總覽原有的 3D 估計說明不能被擠掉`);
     check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag} ${name}：總覽無水平溢出`);
     check(!errors.length,`${tag} ${name}：總覽錯誤 ${errors}`);
     if(process.env.SITE_RESULTS&&methodVer!==null){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`${engine.name()}-${opts.mobile?'mobile':'desktop'}-method-${methodVer?'recorded':'unrecorded'}.png`),fullPage:true});}
     await context.close();
    }
    // ---- 免責句（總覽與建議）與暫定標示 ----
    {
     const {page,context}=await open(browser,opts);
     for(const tab of ['overview','advice']){
      await page.evaluate(tab=>go(DAY,tab),tab);
      const el=page.locator(`[data-tab~="${tab}"] .disclaimer:visible`);
      check(await el.count()===1&&(await el.textContent()).trim()===DISCLAIMER,`${tag}：${tab} 要有一句免責「${DISCLAIMER}」`);
      const style=await el.evaluate(e=>{const s=getComputedStyle(e);return {position:s.position,fits:e.scrollWidth<=e.clientWidth+1};});
      check(['static','relative'].includes(style.position)&&style.fits,`${tag}：${tab} 免責句不能浮在畫面上或溢出：${JSON.stringify(style)}`);
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：${tab} 無水平溢出`);
     }
     await page.evaluate(()=>go(DAY,'advice'));
     const advice=(await page.locator('[data-tab~="advice"]:visible').allTextContents()).join(' ');
     check(/每 5 球錄一次（暫定）/.test(advice),`${tag}：「每 5 球錄一次」要標暫定`);
     check(/≤\s*35%[^。]*≤\s*140°[^。]*暫定|暫定[^。]*≤\s*35%[^。]*≤\s*140°/.test(advice),`${tag}：綠色門檻（轉肩 ≤35%、膝 ≤140°）要標暫定`);
     await context.close();
    }
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
if(failures.length){console.error(failures.join('\n'));process.exit(1);}
console.log('site_method_notes ok');
