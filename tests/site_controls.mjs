// UI 方案 A 第 3 步：單拍控制列收斂（播放、◀格、格▶、停在引拍完成、停在擊球、速度下拉、「顯示 ▾」），鍵盤提示收進「操作說明」。
// 事前預測與失敗方式：testset/results/ui-a3/pred.md。
// 合成模式（預設）：amy 假名、合成片，不讀使用者資料；SITE_REF=origin/main 預期紅（舊網頁沒有這些控制項）。
// SITE_E2E_URL＝真實副本：每場的控制列、停在引拍完成／擊球對 data.js 的 prep／contact；SITE_RESULTS＝另存截圖（私人，不進 git）。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const sect=async(tag,fn)=>{try{await fn();}catch(e){failures.push(`${tag} 例外：${String(e.message).split('\n')[0]}`);}};
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const NOPREP=3;  // 合成場次裡 prep 為 null 的那拍（id 3）；其餘 prep=.5、contact=90
const SHOW=['skel','guides','trail','r3dBtn','theme'];
const CONTROLS=['play','prev','next','toPrep','toHit','speed','viewBtn'];

async function open(browser,{viewport,mobile,scheme,storage}={}){
 const context=await browser.newContext({viewport:viewport||{width:1280,height:800},isMobile:!!mobile,hasTouch:!!mobile,colorScheme:scheme||'light'}),page=await context.newPage(),errors=[];page.setDefaultTimeout(8000);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push('console: '+m.text());});
 if(storage!==undefined)await page.addInitScript(([k,v])=>{try{localStorage.setItem(k,v);}catch{}},['tennis-view-opts-v1',storage]);
 if(!REAL)await page.route('**/sessions/synthetic/data.js*',async route=>{  // id 3 沒有 prep
  const text=await (await route.fetch()).text(),head='window.SESSIONS=[',json=JSON.parse(text.slice(head.length,text.lastIndexOf(']')));
  json.strokes.find(s=>s.id===NOPREP).prep=null;
  await route.fulfill({contentType:'text/javascript; charset=utf-8',body:head+JSON.stringify(json)+'];'});
 });
 await page.goto(f.url);await page.waitForSelector('body.ready');
 return {page,context,errors};
}
const stroke=async(page,id,day)=>{await page.evaluate(d=>go(d??DAY,'stroke'),day);await page.waitForFunction(()=>TAB==='stroke'&&S);if(id!=null){await page.evaluate(i=>load(i),id);await page.waitForFunction(i=>S.id===i,id);}};
// 影片下面看得到的控制項（按 DOM 順序）
const visibleControls=page=>page.evaluate(()=>[...document.querySelectorAll('.player .controls button, .player .controls select')].filter(e=>e.offsetParent&&getComputedStyle(e).visibility!=='hidden').map(e=>e.id));
const noOverflow=(page,msg)=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth).then(ok=>check(ok,msg));
const menu=page=>page.evaluate(()=>{const p=document.getElementById('viewPanel'),b=document.getElementById('viewBtn');return p&&b&&{open:!p.hidden&&!!p.offsetParent,exp:b.getAttribute('aria-expanded'),ctl:b.getAttribute('aria-controls')};});
const contrast=(page,sel)=>page.evaluate(sel=>{
 const rgb=s=>s.match(/[\d.]+/g).map(Number),lum=([r,g,b])=>[r,g,b].map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll(sel)].filter(e=>e.offsetParent).map(e=>{
  const fg=rgb(getComputedStyle(e).color);let bg=null,n=e;
  while(n){const c=getComputedStyle(n).backgroundColor,v=rgb(c);if(v.length>=3&&(v.length<4||v[3]>0.99)&&!/rgba\(0, 0, 0, 0\)/.test(c)){bg=v;break;}n=n.parentElement;}
  bg??=[255,255,255];const a=lum(fg),b=lum(bg);return {sel,text:(e.textContent||e.id).trim().slice(0,20),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
},sel);
const wantPrep=(page)=>page.evaluate(()=>S.prep==null?null:Math.max(0,Math.min(N-1,S.contact-Math.round(S.prep*FPS))));

// ---- 控制列：只留指定項目；跳格；速度 ----
async function core(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,opts);
  await stroke(page,12);
  check(same(await visibleControls(page),CONTROLS),`${tag} 控制列只留 ${CONTROLS}，得到 ${await visibleControls(page)}`);
  check(await page.evaluate(ids=>ids.every(i=>{const e=document.getElementById(i);return !e||!e.offsetParent;}),SHOW),`${tag} 骨架／輔助線／軌跡／3D／深淺色不能在控制列上`);
  check(await page.evaluate(()=>!document.getElementById('speeds')&&!document.getElementById('speedCyc')),`${tag} 舊的 4 顆速度鈕與輪流切換鈕要拿掉`);
  check(await page.evaluate(()=>!!document.getElementById('prevS')?.offsetParent&&!!document.getElementById('nextS')?.offsetParent),`${tag} 上一拍／下一拍要在`);
  // 速度：一顆下拉，4 個值，預設 0.25，換拍後保持
  const opt=await page.evaluate(()=>[...document.getElementById('speed').options].map(o=>o.value));
  check(same(opt,['0.1','0.25','0.5','1']),`${tag} 速度選項：${opt}`);
  check(await page.evaluate(()=>document.getElementById('speed').value==='0.25'&&rate===0.25&&v.playbackRate===0.25),`${tag} 預設 0.25×`);
  check(await page.evaluate(()=>!!document.getElementById('speed').getAttribute('aria-label')||!!document.querySelector('label[for=speed]')),`${tag} 速度下拉要有名稱（aria-label）`);
  for(const val of ['1','0.1','0.5','0.25']){
   await page.locator('#speed').selectOption(val);
   check(await page.evaluate(x=>rate===+x&&v.playbackRate===+x&&document.getElementById('speed').value===x,val),`${tag} 選 ${val}× 後 rate／playbackRate 要跟著`);
  }
  await page.locator('#speed').selectOption('0.5');await page.evaluate(()=>load(13));await page.waitForFunction(()=>S.id===13);
  check(await page.evaluate(()=>rate===0.5&&document.getElementById('speed').value==='0.5'&&v.playbackRate===0.5),`${tag} 換拍後速度保持`);
  check(await page.evaluate(()=>!(document.activeElement&&document.activeElement.id==='speed')),`${tag} 程式選值不能把焦點留在下拉`);
  // 停在引拍完成／停在擊球
  await page.evaluate(()=>load(12));await page.waitForFunction(()=>S.id===12);
  check(await page.locator('#toPrep').isEnabled()&&/停在引拍完成/.test(await page.locator('#toPrep').textContent()),`${tag} #toPrep 要可按、文字「停在引拍完成」`);
  check(/停在擊球/.test(await page.locator('#toHit').textContent()),`${tag} #toHit 文字「停在擊球」`);
  await page.locator('#toPrep').click();
  check(await page.evaluate(()=>cur===S.contact-Math.round(S.prep*FPS)&&cur===60),`${tag} 停在引拍完成：第 60 格，得到 ${await page.evaluate(()=>cur)}`);
  check(await page.evaluate(()=>S.phases.find(p=>p.name==='引拍完成').f===cur),`${tag} 要和階段列的「引拍完成」同一格`);
  check(await page.evaluate(()=>+document.getElementById('seek').value===cur),`${tag} 時間軸跟著`);
  await page.locator('#toHit').click();
  check(await page.evaluate(()=>cur===S.contact&&cur===90),`${tag} 停在擊球：第 90 格，得到 ${await page.evaluate(()=>cur)}`);
  // 播放中按也要停住
  await page.evaluate(()=>toggle());await page.waitForFunction(()=>v._want);
  await page.locator('#toPrep').click();
  check(await page.evaluate(()=>cur===60),`${tag} 播放中按停在引拍完成：${await page.evaluate(()=>cur)}`);
  await page.evaluate(()=>{if(v._want)toggle();});
  // 沒有 prep：停用並說明；換回恢復
  await page.evaluate(i=>load(i),NOPREP);await page.waitForFunction(i=>S.id===i,NOPREP);
  const d=await page.evaluate(()=>{const b=document.getElementById('toPrep');return {dis:b.disabled,title:b.title||b.getAttribute('aria-label')||''};});
  check(d.dis&&/沒有/.test(d.title),`${tag} 沒有 prep 的拍：#toPrep 要停用並說明：${JSON.stringify(d)}`);
  await page.evaluate(()=>load(12));await page.waitForFunction(()=>S.id===12);
  check(await page.locator('#toPrep').isEnabled(),`${tag} 換回有 prep 的拍要恢復可按`);
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await noOverflow(page,`${tag} 無水平溢出`);
  await context.close();
 });
}

// ---- 顯示選單：開關、Esc、點外面、焦點、開關各項、記住 ----
async function view(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,opts);
  await stroke(page,12);
  const m0=await menu(page);
  check(m0&&!m0.open&&m0.exp==='false'&&m0.ctl==='viewPanel',`${tag} 選單預設關、aria-expanded=false、aria-controls：${JSON.stringify(m0)}`);
  check(/顯示/.test(await page.locator('#viewBtn').textContent()),`${tag} 按鈕文字「顯示」`);
  await page.locator('#viewBtn').click();
  const m1=await menu(page);
  check(m1.open&&m1.exp==='true',`${tag} 按下去要開：${JSON.stringify(m1)}`);
  check(await page.evaluate(ids=>ids.every(i=>document.getElementById(i)?.offsetParent),SHOW),`${tag} 開了以後五項都要看得到`);
  check(await page.evaluate(()=>[...document.querySelectorAll('#viewPanel button')].map(b=>b.id).join()==='skel,guides,trail,r3dBtn,theme'),`${tag} 選單裡的順序：骨架、輔助線、手腕軌跡、3D 回放、深淺色`);
  const box=await page.evaluate(()=>{const r=document.getElementById('viewPanel').getBoundingClientRect();return {l:r.left,r:r.right,w:innerWidth,h:innerHeight,t:r.top,b:r.bottom};});
  check(box.l>=0&&box.r<=box.w,`${tag} 選單要在視窗左右之內：${JSON.stringify(box)}`);
  check(box.t>=0&&box.b<=box.h,`${tag} 選單要整個在視窗內（影片下緣放不下就往上開）：${JSON.stringify(box)}`);
  await noOverflow(page,`${tag} 開選單不能撐出水平捲軸`);
  const small=await page.evaluate(()=>[...document.querySelectorAll('#viewPanel button, #viewBtn')].map(b=>{const r=b.getBoundingClientRect();return Math.min(r.width,r.height);}));
  if(opts.mobile)check(small.every(x=>x>=43.5),`${tag} 觸控按鈕要 ≥ 44px：${small}`);
  // 再按一次關
  await page.locator('#viewBtn').click();check(!(await menu(page)).open,`${tag} 再按一次要關`);
  // Esc 關、焦點回按鈕
  await page.locator('#viewBtn').click();await page.locator('#skel').focus();await page.keyboard.press('Escape');
  check(!(await menu(page)).open&&await page.evaluate(()=>document.activeElement.id==='viewBtn'),`${tag} Esc 要關、焦點回 #viewBtn：${await page.evaluate(()=>document.activeElement.id)}`);
  // 焦點在 body（Safari 點按鈕不給焦點）時 Esc 也要關
  await page.locator('#viewBtn').click();await page.evaluate(()=>document.activeElement.blur());await page.keyboard.press('Escape');
  check(!(await menu(page)).open,`${tag} 焦點不在選單裡按 Esc 也要關`);
  // 焦點在「顯示」按鈕按 Shift+Tab：離開選單就關
  await page.locator('#viewBtn').click();await page.locator('#viewBtn').focus();await page.keyboard.press('Shift+Tab');
  check(!(await menu(page)).open,`${tag} 在「顯示」按鈕按 Shift+Tab 要關`);
  // 點外面關
  await page.locator('#viewBtn').click();await page.mouse.click(2,2);
  check(!(await menu(page)).open,`${tag} 點外面要關`);
  // 關著時裡面的按鈕不能被 Tab 到
  check(await page.evaluate(()=>[...document.querySelectorAll('#viewPanel button')].every(b=>!b.offsetParent)),`${tag} 關著時五項不能被看到／Tab 到`);
  // 鍵盤：Enter 開；Tab 走完最後一項後關
  await page.locator('#viewBtn').focus();await page.keyboard.press('Enter');
  check((await menu(page)).open,`${tag} 焦點在按鈕按 Enter 要開`);
  check(await page.evaluate(()=>!v._want),`${tag} Enter 開選單不能順便播放`);
  await page.locator('#theme').focus();await page.keyboard.press('Tab');
  check(!(await menu(page)).open,`${tag} Tab 離開最後一項後選單要關：${JSON.stringify(await menu(page))}`);
  // 各項：骨架／輔助線／軌跡
  await page.locator('#viewBtn').click();
  for(const [id,key] of [['skel','skel'],['guides','guides'],['trail','trail']]){
   check(await page.evaluate(([i,k])=>OPT[k]===true&&document.getElementById(i).getAttribute('aria-pressed')==='true'&&document.getElementById(i).classList.contains('on'),[id,key]),`${tag} ${id} 預設要開`);
   await page.locator('#'+id).click();
   check(await page.evaluate(([i,k])=>OPT[k]===false&&document.getElementById(i).getAttribute('aria-pressed')==='false'&&!document.getElementById(i).classList.contains('on'),[id,key]),`${tag} 按 ${id} 後要關（OPT、aria-pressed、.on）`);
   check((await menu(page)).open,`${tag} 按開關後選單不用自己關（可以連按）`);
  }
  check(JSON.parse(await page.evaluate(()=>localStorage.getItem('tennis-view-opts-v1')))?.skel===false,`${tag} 要存進 localStorage`);
  // 記住：重新載入後三項仍是關
  await page.reload();await page.waitForSelector('body.ready');await stroke(page,12);
  check(await page.evaluate(()=>OPT.skel===false&&OPT.guides===false&&OPT.trail===false),`${tag} 重新載入後三項仍是關：${await page.evaluate(()=>JSON.stringify(OPT))}`);
  await page.locator('#viewBtn').click();
  check(await page.evaluate(()=>['skel','guides','trail'].every(i=>document.getElementById(i).getAttribute('aria-pressed')==='false'&&!document.getElementById(i).classList.contains('on'))),`${tag} 重新載入後按鈕外觀跟著狀態`);
  await page.locator('#guides').click();
  check(JSON.parse(await page.evaluate(()=>localStorage.getItem('tennis-view-opts-v1'))).guides===true,`${tag} 再開輔助線要存`);
  // 3D 回放：按了就開，不存
  await page.locator('#r3dBtn').click();
  check(await page.evaluate(()=>R3D.on&&!document.getElementById('r3d').hidden&&document.getElementById('r3dBtn').getAttribute('aria-pressed')==='true'),`${tag} 選單裡的 3D 回放要能開面板`);
  check(!('r3d' in JSON.parse(await page.evaluate(()=>localStorage.getItem('tennis-view-opts-v1')))),`${tag} 3D 回放不存`);
  await page.locator('#r3dBtn').click();
  check(await page.evaluate(()=>!R3D.on),`${tag} 3D 回放再按要關`);
  // 深淺色
  const t0=await page.evaluate(()=>document.documentElement.dataset.theme||'');
  await page.locator('#theme').click();
  check(await page.evaluate(t=>(document.documentElement.dataset.theme||'')!==t,t0),`${tag} 選單裡的深淺色要能切`);
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await context.close();
 });
 // 存了壞資料：不崩、用預設
 for(const bad of ['not json','{"skel":"x","guides":0,"evil":true}','[1,2]','null'])await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,storage:bad});
  await stroke(page,12);
  check(await page.evaluate(()=>OPT.skel===true&&OPT.guides===true&&OPT.trail===true&&!('evil' in OPT)),`${tag} 壞資料 ${bad}：要用預設且不收未知鍵：${await page.evaluate(()=>JSON.stringify(OPT))}`);
  check(!errors.length,`${tag} 壞資料 ${bad} 頁面錯誤 ${errors}`);
  await context.close();
 });
 // 存了合法的關：只認布林
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,storage:'{"skel":false,"guides":"no"}'});
  await stroke(page,12);
  check(await page.evaluate(()=>OPT.skel===false&&OPT.guides===true&&OPT.trail===true),`${tag} 只認布林：${await page.evaluate(()=>JSON.stringify(OPT))}`);
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

// ---- 說明：預設收起、展開看得到快捷鍵 ----
async function help(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,opts);
  await stroke(page,12);
  if(opts.mobile&&opts.viewport.width<opts.viewport.height){  // 直立手機：說明整個收掉（固定在上方的播放區 ≤ 60% 高；本來這裡也不顯示提示）
   check(await page.evaluate(()=>!document.querySelector('.player details.help').offsetParent),`${tag} 直立手機不顯示說明`);
   check(!errors.length,`${tag} 頁面錯誤 ${errors}`);await context.close();return;
  }
  const s0=await page.evaluate(()=>{const d=document.querySelector('.player details.help');return d&&{open:d.open,sum:d.querySelector('summary')?.textContent.trim(),kbd:!!document.querySelector('.player details.help .kbd-hint'),touch:!!document.querySelector('.player details.help .touch-hint'),outside:!!document.querySelector('.player > .kbd-hint, .player > .touch-hint')};});
  check(s0&&!s0.open&&/說明/.test(s0.sum)&&s0.kbd&&s0.touch&&!s0.outside,`${tag} 說明預設收起、鍵盤與觸控提示都在裡面：${JSON.stringify(s0)}`);
  check(await page.evaluate(()=>{const d=document.querySelector('.player details.help'),h=d.getBoundingClientRect().height,s=d.querySelector('summary').getBoundingClientRect().height;return h<=s+14;}),`${tag} 收起時兩行提示不佔版面（details 高度只有摘要那一行）`);
  await page.locator('.player details.help summary').focus();await page.keyboard.press('Enter');
  check(await page.evaluate(()=>document.querySelector('.player details.help').open),`${tag} 摘要按 Enter 要展開`);
  const sh=await page.evaluate(()=>({kbd:document.querySelector('.player .kbd-hint').getBoundingClientRect().height>0,touch:document.querySelector('.player .touch-hint').getBoundingClientRect().height>0,text:document.querySelector('.player details.help').textContent}));
  if(opts.mobile)check(sh.touch&&/滑動/.test(sh.text),`${tag} 觸控裝置展開要看到觸控提示：${JSON.stringify(sh)}`);
  else check(sh.kbd&&['空白','播放/暫停','逐格','換一拍','寫筆記'].every(w=>sh.text.includes(w)),`${tag} 桌機展開要看到快捷鍵說明：${JSON.stringify(sh)}`);
  await noOverflow(page,`${tag} 展開說明無水平溢出`);
  // 快捷鍵本身不改：空白、←→、↑↓
  await page.locator('.player details.help summary').evaluate(e=>e.blur());await page.evaluate(()=>load(12));
  await page.keyboard.press('ArrowRight');const a=await page.evaluate(()=>cur);await page.keyboard.press('ArrowLeft');const b=await page.evaluate(()=>cur);
  check(a===b+1,`${tag} ←→ 逐格照舊：${b}→${a}`);
  await page.keyboard.press('ArrowDown');await page.waitForFunction(()=>S.id===13);
  await page.keyboard.press('ArrowUp');await page.waitForFunction(()=>S.id===12);
  await page.keyboard.press(' ');check(await page.evaluate(()=>!!v._want),`${tag} 空白播放照舊`);await page.keyboard.press(' ');
  check(await page.evaluate(()=>!v._want),`${tag} 空白再按暫停`);
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

// ---- 版面：390 控制列最多 2 排；深淺色對比 ----
async function layout(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,opts);
  await stroke(page,12);
  const tops=await page.evaluate(()=>new Set([...document.querySelectorAll('.player .controls button, .player .controls select')].filter(e=>e.offsetParent).map(e=>Math.round(e.getBoundingClientRect().top))).size);
  check(tops<=2,`${tag} 控制列最多 2 排：${tops}`);
  const sm=await page.evaluate(()=>[...document.querySelectorAll('.player .controls button, .player .controls select')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect();return {id:e.id,w:r.width,h:r.height,l:r.left,r:r.right};}).filter(x=>(matchMedia('(pointer:coarse)').matches&&(x.w<43.5||x.h<43.5))||x.l<-0.5||x.r>innerWidth+0.5));
  check(sm.length===0,`${tag} 控制項要在視窗內${opts.mobile?'、≥ 44px':''}：${JSON.stringify(sm)}`);
  const cl=await page.evaluate(()=>{const c=document.querySelector('.player .controls');return c.scrollWidth<=c.clientWidth;});
  check(cl,`${tag} 控制列不能橫向捲動`);
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});
   await page.screenshot({path:path.join(process.env.SITE_RESULTS,`synthetic-${opts.mobile?'mobile':'desktop'}-closed.png`)});
   await page.locator('#viewBtn').click();await page.screenshot({path:path.join(process.env.SITE_RESULTS,`synthetic-${opts.mobile?'mobile':'desktop'}-menu.png`)});}
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await context.close();
 });
 for(const scheme of ['light','dark'])await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scheme});
  await stroke(page,12);
  await page.locator('#viewBtn').click();
  const rs=await contrast(page,'#viewBtn, #speed, #toPrep, #toHit, #viewPanel button, .player details.help summary');
  const bad=rs.filter(x=>x.ratio<4.5);
  check(rs.length>=9&&bad.length===0,`${tag} ${scheme}：控制項與選單文字對比要 ≥ 4.5：${JSON.stringify(bad)}（共量 ${rs.length}）`);
  await page.locator('#toPrep').evaluate(e=>{e.disabled=true;});  // 停用狀態也要看得到
  const dis=await contrast(page,'#toPrep');check(dis.length===1,`${tag} ${scheme}：停用的 #toPrep 仍要看得到`);
  check(!errors.length,`${tag} ${scheme} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

// ---- 真實副本：每場的控制列與跳格對 data.js ----
async function real(browser,engine,label,opts){
 const tag=`${engine.name()} ${label} 真實副本`;
 const {page,context,errors}=await open(browser,opts);
 const days=await page.evaluate(()=>DAY_KEYS);
 let withPrep=0,withoutPrep=0;
 for(const day of days){
  await stroke(page,null,day);
  check(same(await visibleControls(page),CONTROLS),`${tag} ${day}：控制列只留 ${CONTROLS}，得到 ${await visibleControls(page)}`);
  const ids=await page.evaluate(()=>ALL.map(s=>s.id));
  for(const id of ids){
   await page.evaluate(i=>load(i,false),id);await page.waitForFunction(i=>S.id===i,id);
   const want=await wantPrep(page),dis=await page.locator('#toPrep').isDisabled();
   if(want==null){withoutPrep++;check(dis,`${tag} ${day} #${id}：沒有 prep 要停用`);continue;}
   withPrep++;check(!dis,`${tag} ${day} #${id}：有 prep 要可按`);
   if(id%4===0){await page.locator('#toPrep').click();const got=await page.evaluate(()=>cur);check(got===want,`${tag} ${day} #${id}：停在引拍完成 ${want}，得到 ${got}`);await page.locator('#toHit').click();const h=await page.evaluate(()=>[cur,Math.min(N-1,S.contact)]);check(h[0]===h[1],`${tag} ${day} #${id}：停在擊球 ${h[1]}，得到 ${h[0]}`);}
  }
  await noOverflow(page,`${tag} ${day} 無水平溢出`);
  if(process.env.SITE_RESULTS&&!process.env.SITE_NO_SHOT){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});const d=day.replace(/[^\w-]/g,'_'),k=`real-${engine.name()}-${opts.mobile?'mobile':'desktop'}-${d}`;
   await page.evaluate(()=>load(ALL[Math.min(3,ALL.length-1)].id,false));await page.evaluate(()=>scrollTo(0,0));
   await page.screenshot({path:path.join(process.env.SITE_RESULTS,k+'-closed.png')});
   await page.locator('#viewBtn').click();await page.screenshot({path:path.join(process.env.SITE_RESULTS,k+'-menu.png')});await page.locator('#viewBtn').click();}
 }
 check(withPrep>0,`${tag}：副本裡至少要有一拍有 prep（否則沒驗到跳格）`);
 console.log(`${tag}：有 prep ${withPrep} 拍、沒有 ${withoutPrep} 拍`);
 check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
 await context.close();
}

try{
 const engines=(process.env.SITE_ENGINES||'chromium,webkit').split(',').map(x=>({chromium,webkit})[x]);
 for(const engine of engines){
  const browser=await engine.launch();
  try{
   for(const [label,opts] of [['桌機',{}],['手機 390px',{viewport:{width:390,height:844},mobile:true}],['手機橫向',{viewport:{width:844,height:390},mobile:true}]]){
    if(REAL)await real(browser,engine,label,opts);
    else{await core(browser,engine,label,opts);await view(browser,engine,label,opts);await help(browser,engine,label,opts);await layout(browser,engine,label,opts);}
   }
  }finally{await browser.close();}
 }
}finally{await f.close?.();}
if(failures.length){console.error(failures.join('\n'));process.exit(1);}
console.log('site_controls ok'+(REAL?'（真實副本）':''));
