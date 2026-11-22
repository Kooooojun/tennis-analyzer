// UI 方案 A 第 5 步：一場一頁（拿掉分頁），其他內容收進同頁展開區；舊網址 #d<場次>/<分頁> 與 go(場次, 分頁) 當別名。
// 事前預測與失敗方式：testset/results/ui-a5/pred.md（私人，不進 git）。
// 合成模式（預設）：amy／zed 假名、合成片，不讀使用者資料；SITE_REF=origin/main 預期紅（舊網頁還有分頁、沒有展開區）。
// SITE_E2E_URL＝真實副本：每場的展開區、第一屏、別名、收起即暫停；SITE_RESULTS＝另存截圖（私人，不進 git）。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const SECS=['這拍的全部數字','其他建議','分數與走勢','並排比較','圖表','怎麼練','其他場次','筆記','長說明'];
const ALIAS={overview:['分數與走勢','長說明'],video:['並排比較'],charts:['圖表'],stroke:['這拍的全部數字','筆記'],advice:['其他建議','怎麼練']};
const DISCLAIMER='這是練習參考，不能代替教練或醫療判斷。';
const SLACK=150;  // 協調者 2026-11-22：拍子列與免責可在第一屏下方 ≤ 150 px

// ---- 合成情境（25 拍，id 0–24；拍號＝id+1） ----
const LONG='擊球點在髖前的距離，自拋 0.8、對打 1.0（軀幹長）。這個差距比一格擊球格的誤差大，看 #13、#02 的擊球格，自拋那拍拍子在身體旁邊，對打那拍在前腳前。'.repeat(4);
const MAIN={title:'自拋時把球打在身前',why:LONG,cite:[{player:'zed',kind:'FH',drill:'rally',field:'prep',stat:'median',value:0.5}],practice:'自拋時把球丟在身體側前方一大步。',cue:'打在前腳前',jump:[[13,'zed #13'],[16,'zed #16']]};
const SCEN={
 two:{players:['amy','zed'],owners:id=>id<10?'amy':'zed',  // amy 10 拍、zed 15 拍：zed 的卡展開、amy 收成一行
      overall:[{player:'amy',insufficient:{title:'amy：資料不足',why:'只有 10 拍。',cite:[]},film_next:'側面拍。',look:[1,2,3]},{player:'zed',main:MAIN,look:[11,12,13]}]},
 single:{players:['me'],overall:[{player:'me',main:{...MAIN,why:'短。',cite:[{player:'me',kind:'FH',drill:'rally',field:'prep',stat:'median',value:0.5}],jump:[[5,'看 #05']]},look:[2,5,13]}]},
 none:{players:['me'],overall:[]},
};
async function open(browser,{viewport,mobile,scheme,scen,hash='#dsynthetic'}={}){
 const context=await browser.newContext({viewport:viewport||{width:1280,height:800},isMobile:!!mobile,hasTouch:!!mobile,colorScheme:scheme||'light'}),page=await context.newPage(),errors=[],clips=[];page.setDefaultTimeout(8000);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/Failed to load resource/.test(m.text()))errors.push('console: '+m.text());});
 page.on('request',r=>{if(/\.mp4/.test(r.url()))clips.push(r.url());});
 if(scen){
  const sc=SCEN[scen];
  await page.route('**/sessions/synthetic/data.js*',async route=>{
   const text=await (await route.fetch()).text(),head='window.SESSIONS=[',json=JSON.parse(text.slice(head.length,text.lastIndexOf(']')));
   json.players=sc.players;if(sc.owners)json.strokes.forEach(s=>{s.player=sc.owners(s.id);});json.overall=sc.overall;
   json.findings=[{title:'第一條建議',text:'內文',cite:[{metric:'prep',stat:'median',value:0.5,kind:'FH',player:sc.players[0]}],jump:[[3,'看 #03']]}];
   await route.fulfill({contentType:'text/javascript; charset=utf-8',body:head+JSON.stringify(json)+'];'});
  });
 }
 await page.goto(f.url+hash);await page.waitForSelector('body.ready');if(hash.startsWith('#d'))await page.waitForFunction(()=>typeof S!=='undefined'&&S);
 return {page,context,errors,clips};
}
const secs=page=>page.evaluate(()=>[...document.querySelectorAll('main .sec')].map(s=>{const b=s.querySelector('.sec-btn'),body=document.getElementById(b?.getAttribute('aria-controls'));return {title:s.querySelector('.sec-title')?.textContent.trim(),exp:b?.getAttribute('aria-expanded'),open:!!body&&!body.hidden&&!!body.offsetParent};}));
const openTitles=async page=>(await secs(page)).filter(s=>s.open).map(s=>s.title);
const btn=(page,title)=>page.locator('main .sec .sec-btn',{has:page.locator('.sec-title',{hasText:new RegExp('^'+title+'$')})});
const noOverflow=(page,msg)=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth).then(ok=>check(ok,msg));
const contrast=(page,sel)=>page.evaluate(sel=>{
 const rgb=s=>s.match(/[\d.]+/g).map(Number),lum=([r,g,b])=>[r,g,b].map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll(sel)].filter(e=>e.offsetParent&&e.textContent.trim()).map(e=>{
  const fg=rgb(getComputedStyle(e).color);let bg=null,n=e;
  while(n){const c=getComputedStyle(n).backgroundColor,v=rgb(c);if(v.length>=3&&(v.length<4||v[3]>0.99)&&!/rgba\(0, 0, 0, 0\)/.test(c)){bg=v;break;}n=n.parentElement;}
  bg??=[255,255,255];const a=lum(fg),b=lum(bg);return {text:e.textContent.trim().slice(0,16),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
},sel);
// 第一屏：捲到最上面時，每項底邊 ≤ 視窗高（拍子列、免責可多 SLACK）
const firstScreen=page=>page.evaluate(()=>{scrollTo(0,0);const b=q=>{const e=document.querySelector(q);return e&&e.offsetParent!==null?Math.round(e.getBoundingClientRect().bottom):null;};
 return {h:innerHeight,card:b('#overall .ov-card'),stage:b('#stage'),r3d:R3D.on&&!$('stage').contains($('r3dCv'))?b('#r3dCv'):null,controls:b('.player .controls'),players:b('#players'),axis:b('#axisLine'),strokes:b('#strokes'),line:b('#oneLine')};});
const fitMsg=(fs,tag)=>{const bad=[];for(const k of ['card','stage','controls','r3d','players'])if(fs[k]!=null&&fs[k]>fs.h)bad.push(k);for(const k of ['axis','strokes','line'])if(fs[k]==null||fs[k]>fs.h+SLACK)bad.push(k);for(const k of ['card','stage','controls'])if(fs[k]==null)bad.push(k+' 不見了');return bad.length?`${tag} 第一屏放不下 ${bad.join('、')}：${JSON.stringify(fs)}`:null;};
const sect=async(tag,fn)=>{try{await fn();}catch(e){failures.push(`${tag} 例外：${String(e.message).split('\n')[0]}`);}};

async function synthetic(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`,phone=!!opts.mobile;
 // ---- 版面：沒有分頁、9 個展開區預設收起、第一屏 ----
 await sect(tag,async()=>{
  const {page,context,errors,clips}=await open(browser,{...opts,scen:'two'});
  check(await page.evaluate(()=>!document.querySelector('#tabbar button')&&!document.querySelector('header #days')),`${tag} 不能再有分頁列和 header 的日期列`);
  const s=await secs(page);
  check(JSON.stringify(s.map(x=>x.title))===JSON.stringify(SECS),`${tag} 展開區要依序 ${SECS}，得到 ${JSON.stringify(s.map(x=>x.title))}`);
  check(s.every(x=>x.exp==='false'&&!x.open),`${tag} 展開區預設全部收起：${JSON.stringify(s)}`);
  check(await page.evaluate(()=>location.hash==='#dsynthetic'&&TAB===''),`${tag} 沒帶分頁的網址：TAB 是空字串`);
  await page.waitForFunction(()=>v.readyState>=1);
  check(clips.some(u=>/clips\/\d+\.mp4/.test(u)),`${tag} 一頁打開就要抓主影片`);
  check(await page.evaluate(()=>!vA.currentSrc&&!vB.currentSrc),`${tag} 並排比較收著時不抓比較影片`);
  const fs1=await firstScreen(page),m=fitMsg(fs1,tag);check(!m,m);
  check(fs1.axis<fs1.strokes&&fs1.strokes<fs1.line,`${tag} 順序：主軸數字 → 拍子列 → 免責：${JSON.stringify(fs1)}`);
  if(!phone) check(fs1.r3d!=null,`${tag} 桌機 3D 要在第一屏`);
  // 球員切換：所有人、amy、zed（同舊 #tabs 順序）
  check(JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('#players button')].map(b=>b.textContent.trim())))===JSON.stringify(['所有人','amy 10','zed 15']),`${tag} 球員切換要在 #players：${await page.evaluate(()=>$('players')?.textContent)}`);
  check(await page.evaluate(()=>![...document.querySelectorAll('#tabs button')].some(b=>/^(所有人|amy|zed)/.test(b.textContent))),`${tag} #tabs 不再放球員`);
  // 主軸卡：所有人 → zed（拍多）完整、amy 一行
  const cards=()=>page.evaluate(()=>[...document.querySelectorAll('#overall .ov-card')].map(c=>({title:c.querySelector('.ov-title')?.textContent.trim(),collapsed:c.classList.contains('ov-collapsed'),why:!!c.querySelector('.ov-why')?.offsetParent,jump:[...c.querySelectorAll('.ov-jump button')].filter(b=>b.offsetParent).length})));
  let c=await cards();
  check(c.length===2&&c[0].title==='自拋時把球打在身前'&&!c[0].collapsed&&c[0].why&&c[0].jump===2,`${tag} 所有人：zed 的卡完整在前：${JSON.stringify(c)}`);
  check(c[1]?.collapsed&&c[1].title==='amy：資料不足'&&!c[1].why&&c[1].jump===0,`${tag} 所有人：amy 收成一行標題：${JSON.stringify(c[1])}`);
  const more=page.locator('#overall .ov-open');
  check(await more.count()===1&&(await more.getAttribute('aria-expanded'))==='false',`${tag} 收起的卡要有展開鈕（aria-expanded=false）`);
  await more.click();c=await cards();
  check(!c[1].collapsed&&c[1].why&&(await more.getAttribute('aria-expanded'))==='true',`${tag} 點了 amy 的卡要展開：${JSON.stringify(c[1])}`);
  // 「為什麼」兩行＋看全文
  const why=await page.evaluate(()=>{const e=document.querySelector('#overall .ov-card .ov-why'),lh=parseFloat(getComputedStyle(e).lineHeight);return {h:e.getBoundingClientRect().height,lh,practice:!!document.querySelector('#overall .ov-card .ov-practice')?.offsetParent};});
  check(why.h<=why.lh*2+2&&!why.practice,`${tag} 為什麼收成兩行、練法收著：${JSON.stringify(why)}`);
  const full=page.locator('#overall .ov-card').first().locator('.ov-full');
  check(await full.count()===1&&(await full.getAttribute('aria-expanded'))==='false'&&/看全文/.test(await full.textContent()),`${tag} 要有「看全文 ›」鈕`);
  await full.click();
  const why2=await page.evaluate(()=>{const e=document.querySelector('#overall .ov-card .ov-why');return {h:e.getBoundingClientRect().height,lh:parseFloat(getComputedStyle(e).lineHeight),practice:!!document.querySelector('#overall .ov-card .ov-practice')?.offsetParent,cue:!!document.querySelector('#overall .ov-card .ov-cue')?.offsetParent};});
  check(why2.h>why.lh*2+2&&why2.practice&&why2.cue&&(await full.getAttribute('aria-expanded'))==='true',`${tag} 看全文後為什麼、練法、口訣都看得到：${JSON.stringify(why2)}`);
  // 選 amy：只剩 amy 一張、完整
  await page.locator('#players button',{hasText:/^amy/}).click();c=await cards();
  check(c.length===1&&c[0].title==='amy：資料不足'&&!c[0].collapsed,`${tag} 選 amy 後只剩她的卡且完整：${JSON.stringify(c)}`);
  check(await page.evaluate(()=>pfilter==='amy'&&[...document.querySelectorAll('#strokes button[data-id]')].every(b=>who(ALL[+b.dataset.id])==='amy')),`${tag} 選 amy 後拍子列只有 amy`);
  await page.locator('#players button',{hasText:'所有人'}).click();c=await cards();
  check(c.length===2&&!c[0].collapsed&&c[1].collapsed,`${tag} 選回所有人：zed 完整、amy 一行：${JSON.stringify(c)}`);
  await noOverflow(page,`${tag} 一頁無水平溢出`);
  const low=(await contrast(page,'.sec-title, .sec-meta, #players button, #axisLine, #oneLine, .ov-open, .ov-full')).filter(r=>r.ratio<4.5);
  check(!low.length,`${tag} 對比不足：${JSON.stringify(low)}`);
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`synthetic-${phone?'phone':'desk'}-${opts.scheme||'light'}.png`)});}
  await context.close();
 });
 // ---- 展開區開關：滑鼠、鍵盤、各自獨立 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'two'});
  for(const t of SECS){
   await btn(page,t).click();
   check((await openTitles(page)).includes(t)&&(await btn(page,t).getAttribute('aria-expanded'))==='true',`${tag} 點「${t}」要展開`);
  }
  check((await openTitles(page)).length===SECS.length,`${tag} 自己按的展開區各自獨立，全開：${await openTitles(page)}`);
  await btn(page,'圖表').click();
  check(!(await openTitles(page)).includes('圖表')&&(await openTitles(page)).length===SECS.length-1,`${tag} 再點一次收起，只收那一區`);
  await btn(page,'圖表').focus();await page.keyboard.press('Enter');
  check((await openTitles(page)).includes('圖表'),`${tag} Enter 要展開`);
  await page.keyboard.press(' ');
  check(!(await openTitles(page)).includes('圖表')&&await page.evaluate(()=>!v._want),`${tag} 空白鍵在區按鈕上是開關，不是播放`);
  check(await page.evaluate(()=>{const e=document.activeElement;return e.classList.contains('sec-btn')&&getComputedStyle(e).outlineStyle!=='none';}),`${tag} 區按鈕焦點框要看得到`);
  check(!errors.length,`${tag} 開關頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 別名：go(場次, 分頁) 與舊網址 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'two'});
  for(const [tab,want] of Object.entries(ALIAS)){
   await page.evaluate(()=>scrollTo(0,0));
   await page.evaluate(t=>go(DAY,t),tab);await page.waitForFunction(t=>TAB===t,tab);
   const o=await openTitles(page);
   check(JSON.stringify(o)===JSON.stringify(want),`${tag} go(DAY,'${tab}') 要只開 ${want}，得到 ${o}`);
   const pos=await page.evaluate(t=>{const sec=[...document.querySelectorAll('main .sec')].find(s=>!s.querySelector('.sec-body').hidden),r=sec.getBoundingClientRect(),pl=document.querySelector('.player'),sticky=getComputedStyle(pl).position==='sticky'?pl.getBoundingClientRect().bottom:0;return {y:scrollY,top:r.top,sticky,h:innerHeight};},tab);
   if(['video','stroke'].includes(tab)) check(pos.y===0,`${tag} ${tab}：播放器本來就在最上面，不捲動：${JSON.stringify(pos)}`);
   else check(pos.top>=pos.sticky-2&&pos.top<pos.h,`${tag} ${tab}：要捲到那一區、不被黏頂播放區蓋住：${JSON.stringify(pos)}`);
  }
  // 圖表打開才量寬度
  await page.evaluate(()=>go(DAY,'charts'));await page.waitForFunction(()=>TAB==='charts');
  const w=await page.evaluate(()=>[$('stripKnee').clientWidth,document.querySelector('#stripKnee svg')?.viewBox.baseVal.width]);
  check(w[1]&&Math.abs(w[0]-w[1])<=2,`${tag} 圖表 svg 寬要等於區塊寬：${w}`);
  // 同一個別名再按一次（hash 沒變）也要打開
  await btn(page,'圖表').click();
  await page.evaluate(()=>go(DAY,'charts'));
  await page.waitForFunction(()=>!$('secCharts').querySelector('.sec-body').hidden).catch(()=>{});
  check((await openTitles(page)).includes('圖表'),`${tag} 同一個別名再叫一次要重新打開`);
  // 走勢表在「分數與走勢」
  await page.evaluate(()=>go(DAY,'overview'));await page.waitForFunction(()=>TAB==='overview');
  check(await page.evaluate(()=>!!document.querySelector('#secScores table.trend')?.offsetParent),`${tag} 走勢表要在分數與走勢裡`);
  // 首頁連結不帶分頁；舊網址直接開
  check(await page.evaluate(()=>{location.hash='#home';return new Promise(r=>setTimeout(()=>r([...document.querySelectorAll('#home a[href^="#d"]')].every(a=>/^#d[^/]+$/.test(a.getAttribute('href')))),50));}),`${tag} 首頁的場次連結不帶分頁`);
  check(!errors.length,`${tag} 別名頁面錯誤 ${errors}`);
  await context.close();
  const o2=await open(browser,{...opts,scen:'two',hash:'#dsynthetic/advice'});
  check(JSON.stringify(await openTitles(o2.page))===JSON.stringify(ALIAS.advice)&&await o2.page.evaluate(()=>TAB==='advice'),`${tag} 舊網址 #d…/advice 開頁就展開建議和怎麼練：${await openTitles(o2.page)}`);
  await o2.context.close();
 });
 // ---- 收起＝看不到：比較影片暫停、主影片回首頁暫停 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'two'});
  await page.evaluate(()=>go(DAY,'video'));await page.locator('#vA').scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
  await page.locator('#cmpPlay').click();await page.waitForFunction(()=>!vA.paused&&!vB.paused);
  await btn(page,'並排比較').click();
  await page.waitForFunction(()=>vA.paused&&vB.paused,null,{timeout:3000}).catch(()=>{});
  check(await page.evaluate(()=>vA.paused&&vB.paused&&!vA._want&&!vB._want&&$('cmpPlay').textContent.includes('▶')),`${tag} 收起並排比較，比較影片要停：${await page.evaluate(()=>[vA.paused,vB.paused,vA._want,$('cmpPlay').textContent])}`);
  await btn(page,'並排比較').click();await page.waitForTimeout(300);
  check(await page.evaluate(()=>vA.paused&&vB.paused),`${tag} 再打開不自動續播`);
  // 主影片：回首頁要停
  await page.evaluate(()=>scrollTo(0,0));await page.waitForFunction(()=>v.readyState>=2);
  await page.locator('#play').click();await page.waitForFunction(()=>!v.paused);
  await page.evaluate(()=>{location.hash='#home';});await page.waitForFunction(()=>!v.offsetParent);
  check(await page.evaluate(()=>v.paused&&!v._want),`${tag} 回首頁主影片要停`);
  check(!errors.length,`${tag} 暫停頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 這拍主軸數字一行、jump、快捷鍵、長說明 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await page.evaluate(()=>load(4));await page.waitForFunction(()=>S.id===4);
  let t=(await page.locator('#axisLine').textContent()).replace(/\s+/g,' ');
  check(/#05/.test(t)&&/準備時間 0\.50 秒/.test(t)&&/中位/.test(t)&&!/NaN|undefined|null/.test(t),`${tag} 主軸數字一行要寫這拍的準備時間與中位數：「${t}」`);
  await page.evaluate(()=>{S.prep=null;load(7);});await page.waitForFunction(()=>S.id===7);
  t=(await page.locator('#axisLine').textContent()).replace(/\s+/g,' ');
  check(/#08/.test(t)&&!/NaN|undefined|null/.test(t),`${tag} 換拍要跟著換：「${t}」`);
  // jump：跳拍並把播放器放進畫面
  await page.evaluate(()=>scrollTo(0,document.body.scrollHeight));
  await page.locator('#overall .ov-jump button',{hasText:'看 #05'}).click();await page.waitForFunction(()=>S.id===4);
  await page.waitForTimeout(800);
  const r=await page.evaluate(()=>{const e=$('stage').getBoundingClientRect();return {top:e.top,bottom:e.bottom,h:innerHeight};});
  check(r.top>=-1&&r.top<r.h/2,`${tag} jump 後播放器要在畫面內：${JSON.stringify(r)}`);
  // 快捷鍵：不用切分頁就能逐格；焦點在筆記輸入框時不作用
  await page.evaluate(()=>document.activeElement?.blur());
  const c0=await page.evaluate(()=>cur);await page.keyboard.press('ArrowRight');
  check(await page.evaluate(c0=>cur===c0+1,c0),`${tag} → 要逐格`);
  await page.keyboard.press('n');
  check(await page.evaluate(()=>document.activeElement===$('noteIn')&&!!$('noteIn').offsetParent),`${tag} N 要打開筆記區並聚焦輸入框`);
  await page.keyboard.press(' ');check(await page.evaluate(()=>!v._want),`${tag} 輸入框裡打空白不能播放`);
  // 長說明：免責一行的「數字的限制 ›」打開它
  await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
  const lim=page.locator('#oneLine button');
  check(await lim.count()===1&&/數字的限制/.test(await lim.textContent()),`${tag} 免責一行要有「數字的限制 ›」`);
  await lim.click();
  check((await openTitles(page)).includes('長說明'),`${tag} 數字的限制要打開長說明`);
  const long=await page.evaluate(()=>{const b=$('secLong');return {text:b.innerText,help:[...b.querySelectorAll('.kbd-hint,.touch-hint')].some(e=>e.offsetParent)};});
  check(long.text.includes(DISCLAIMER)&&/方法說明/.test(long.text)&&long.help,`${tag} 長說明要有免責、方法說明、操作說明：${JSON.stringify({...long,text:long.text.slice(0,80)})}`);
  check(await page.evaluate(()=>!document.querySelector('.player details.help')),`${tag} 操作說明不再在播放區`);
  check(!errors.length,`${tag} 單人頁面錯誤 ${errors}`);
  await context.close();
  const o=await open(browser,{...opts,scen:'none'});
  await o.page.evaluate(()=>load(4));await o.page.waitForFunction(()=>S.id===4);
  t=(await o.page.locator('#axisLine').textContent()).replace(/\s+/g,' ');
  check(/#05/.test(t)&&/膝/.test(t)&&/114°/.test(t),`${tag} 沒有 overall：主軸數字一行退回準備時膝蓋：「${t}」`);
  check(await o.page.locator('#oneLine').isVisible()&&(await o.page.locator('#oneLine').textContent()).includes('練習參考'),`${tag} 沒有 overall 也要有一行免責`);
  await o.context.close();
 });
}

async function real(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,hash:'#home'});
  const days=await page.evaluate(()=>DAY_KEYS);
  for(const [i,d] of days.entries()){
   const dt=`${tag} 場次${i}`;
   await page.evaluate(d=>{location.hash='#d'+encodeURIComponent(d);},d);await page.waitForFunction(d=>DAY===d&&S,d);await page.waitForTimeout(300);
   const s=await secs(page);
   check(JSON.stringify(s.map(x=>x.title))===JSON.stringify(SECS),`${dt} 展開區順序：${JSON.stringify(s.map(x=>x.title))}`);
   const fs1=await firstScreen(page),m=fitMsg(fs1,dt);check(!m,m);
   const cards=await page.evaluate(()=>[...document.querySelectorAll('#overall .ov-card')].map(c=>c.classList.contains('ov-collapsed')));
   const n=await page.evaluate(()=>overallEntries(DAYS[DAY]).length);
   check(cards.length===n&&(n===0||!cards[0]&&cards.slice(1).every(Boolean)),`${dt} 主軸卡 ${n} 張，第一張完整、其他一行：${cards}`);
   const ax=(await page.locator('#axisLine').textContent()).replace(/\s+/g,' ');
   check(/#\d\d/.test(ax)&&!/NaN|undefined|null/.test(ax),`${dt} 主軸數字一行：「${ax}」`);
   if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`real-${opts.mobile?'phone':'desk'}-${opts.scheme||'light'}-s${i}.png`)});}
   for(const [tab,want] of Object.entries(ALIAS)){
    await page.evaluate(([d,t])=>go(d,t),[d,tab]);await page.waitForFunction(t=>TAB===t,tab);
    check(JSON.stringify(await openTitles(page))===JSON.stringify(want),`${dt} go(…,'${tab}') 只開 ${want}：${await openTitles(page)}`);
   }
   await page.evaluate(([d])=>go(d,'video'),[d]);await page.locator('#vA').scrollIntoViewIfNeeded();
   await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2,null,{timeout:20000});
   await page.locator('#cmpPlay').click();await page.waitForFunction(()=>!vA.paused);
   await btn(page,'並排比較').click();await page.waitForFunction(()=>vA.paused&&vB.paused,null,{timeout:3000}).catch(()=>{});
   check(await page.evaluate(()=>vA.paused&&vB.paused&&!vA._want),`${dt} 收起並排比較要停`);
   await noOverflow(page,`${dt} 無水平溢出`);
  }
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

const VIEWS=[['desktop',{}],['desktop-dark',{scheme:'dark'}],['phone',{viewport:{width:390,height:844},mobile:true}],['phone-dark',{viewport:{width:390,height:844},mobile:true,scheme:'dark'}]];
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{for(const [label,opts] of VIEWS){if(REAL)await real(browser,engine,label,opts);else await synthetic(browser,engine,label,opts);}}
  finally{await browser.close();}
 }
}finally{await f.close();}
if(failures.length){console.error(failures.join('\n'));console.error(`site_one_page：${failures.length} 條失敗`);process.exit(1);}
console.log(`site_one_page ok（${REAL?'真實副本':'合成'}）`);
