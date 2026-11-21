// UI 方案 A 第 2 步：「每一拍」的拍子列預設只列 overall 標到的拍（main／second 的 jump 與 look）＋目前這拍，
// 最後一顆「全部 N 拍 ▾」展開成完整列表。沒有 overall 的舊場次維持完整列表。
// 事前預測與失敗方式：testset/results/ui-a2/pred.md。
// 合成模式（預設）：amy／zed 假名，不讀使用者資料；SITE_REF=origin/main 預期紅。
// SITE_E2E_URL＝真實副本：預設列的集合對 data.js 算出來的集合；SITE_RESULTS＝另存截圖（私人，不進 git）。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const sect=async(tag,fn)=>{try{await fn();}catch(e){failures.push(`${tag} 例外：${String(e.message).split('\n')[0]}`);}};

// 合成場次 25 拍（id 0–24，最終拍號＝id+1；id%3===0 是反拍）
const MAIN={title:'自拋時把球打在身前',why:'看 #13、#02。',cite:[],practice:'丟在側前方。',jump:[[13,'對打 #13'],[2,'自拋 #02']]};
const SECOND={title:'保持側身舉拍',why:'#05 已側身。',cite:[],practice:'維持。',jump:[[5,'好球：#05']]};
const INSUF={title:'資料不足',why:'只有 4 拍。',cite:[]};
const FILM='手機放側面。';
const SCEN={
 single:{players:['me'],overall:[{player:'me',main:MAIN,second:SECOND,look:[2,5,13,16]}]},  // 相關拍 id 1,4,12,15
 insuf:{players:['me'],overall:[{player:'me',insufficient:INSUF,film_next:FILM,second:{title:'看圖',why:'#03。',cite:[],jump:[[3,'看 #03']]},look:[1,2,3]}]},  // id 0,1,2
 two:{players:['amy','zed'],owners:id=>id<10?'amy':'zed',  // amy id 0–9（10 拍）、zed id 10–24（15 拍）
      overall:[{player:'amy',insufficient:{...INSUF,title:'amy'},film_next:FILM,look:[1,2,3]},{player:'zed',main:{...MAIN,jump:[[13,'zed #13'],[16,'zed #16']]},look:[11,12,13]}]},  // amy id 0,1,2；zed id 10,11,12,15
 none:{players:['me'],overall:[]},
 missing:{players:['me'],overall:undefined},
 nulled:{players:['me'],overall:null},
 ghost:{players:['me'],overall:[{player:'me',main:{...MAIN,jump:[[99,'沒有這拍']]},look:[97,98,99]}]},  // 拍號全找不到
 odd:{players:['me'],overall:[{player:'me',main:{...MAIN,jump:[[13,'對打 #13'],'x',null,[7]]},look:'abc'},{player:'me',insufficient:INSUF,look:[4,4,'5']}]},  // 欄位型別亂：不崩，合法的照算
};
const EXPECT={single:[1,4,12,15],insuf:[0,1,2],two:[0,1,2,10,11,12,15]};

async function open(browser,{viewport,mobile,scheme,scen}={}){
 const context=await browser.newContext({viewport:viewport||{width:1280,height:800},isMobile:!!mobile,hasTouch:!!mobile,colorScheme:scheme||'light'}),page=await context.newPage(),errors=[];page.setDefaultTimeout(8000);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push('console: '+m.text());});
 if(scen){
  const sc=SCEN[scen];
  await page.route('**/sessions/synthetic/data.js*',async route=>{
   const text=await (await route.fetch()).text(),head='window.SESSIONS=[',json=JSON.parse(text.slice(head.length,text.lastIndexOf(']')));
   json.players=sc.players;if(sc.owners)json.strokes.forEach(s=>{s.player=sc.owners(s.id);});
   if(sc.overall===undefined)delete json.overall;else json.overall=sc.overall;
   await route.fulfill({contentType:'text/javascript; charset=utf-8',body:head+JSON.stringify(json)+'];'});
  });
 }
 await page.goto(f.url);await page.waitForSelector('body.ready');
 return {page,context,errors};
}
const stroke=async(page,day,id)=>{await page.evaluate(([d,i])=>{go(d??DAY,'stroke');},[day,id]);await page.waitForFunction(()=>TAB==='stroke'&&S);if(id!=null){await page.evaluate(i=>load(i),id);await page.waitForFunction(i=>S.id===i,id);}};
// 列裡的拍（不含開關）：id、是否目前、文字
const row=page=>page.evaluate(()=>[...document.querySelectorAll('#strokes button:not(.strokes-more)')].map(b=>({id:+b.dataset.id,cur:b.classList.contains('cur'),text:b.textContent.replace(/\s+/g,' ').trim(),top:Math.round(b.getBoundingClientRect().top)})));
const more=page=>page.evaluate(()=>{const m=document.querySelector('#strokes .strokes-more');return m&&{text:m.textContent.trim(),exp:m.getAttribute('aria-expanded'),last:m===m.parentElement.lastElementChild,first:m===m.parentElement.firstElementChild,visible:!!m.offsetParent};});
const ids=r=>r.map(x=>x.id);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const noOverflow=(page,msg)=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth).then(ok=>check(ok,msg));
const kindTabs=page=>page.evaluate(()=>[...document.querySelectorAll('#tabs button')].filter(b=>b.offsetParent).map(b=>b.textContent.trim()));
const TAB_KEY=engine=>engine.name()==='webkit'&&process.platform==='darwin'?'Alt+Tab':'Tab';  // macOS 的 Safari／WebKit 預設 Tab 跳過按鈕

const contrast=(page,sel)=>page.evaluate(sel=>{
 const rgb=s=>s.match(/[\d.]+/g).map(Number),lum=([r,g,b])=>[r,g,b].map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll(sel)].filter(e=>e.offsetParent).map(e=>{
  const fg=rgb(getComputedStyle(e).color);let bg=null,n=e;
  while(n){const c=getComputedStyle(n).backgroundColor,v=rgb(c);if(v.length>=3&&(v.length<4||v[3]>0.99)&&!/rgba\(0, 0, 0, 0\)/.test(c)){bg=v;break;}n=n.parentElement;}
  bg??=[255,255,255];const a=lum(fg),b=lum(bg);return {sel,text:e.textContent.trim().slice(0,20),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
},sel);

async function synthetic(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 // ---- 單人：預設列、目前這拍、展開、收起 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await stroke(page,null,12);
  let r=await row(page),m=await more(page);
  check(same(ids(r),EXPECT.single),`${tag} 單人：預設列要是 overall 標到的拍 ${EXPECT.single}，得到 ${ids(r)}`);
  check(r.filter(x=>x.cur).map(x=>x.id).join()==='12'&&!r.some(x=>/目前這拍/.test(x.text)),`${tag} 目前這拍在相關拍裡：只標 .cur、不加「目前這拍」字樣：${JSON.stringify(r)}`);
  check(m&&m.last&&m.text==='全部 25 拍 ▾'&&m.exp==='false',`${tag} 開關要是最後一顆、「全部 25 拍 ▾」、aria-expanded=false：${JSON.stringify(m)}`);
  check(!(await kindTabs(page)).some(t=>/^(全部|正拍|反拍)/.test(t)),`${tag} 收起時不顯示種類篩選：${await kindTabs(page)}`);
  check(new Set(r.map(x=>x.top)).size===1,`${tag} 列要只有一排（所有按鈕 top 相同）：${r.map(x=>x.top)}`);
  // 目前這拍不在列內
  await page.evaluate(()=>load(0));await page.waitForFunction(()=>S.id===0);
  r=await row(page);
  check(same(ids(r),[0,...EXPECT.single]),`${tag} 目前這拍（#1）不在相關拍時要多一顆、依拍序：${ids(r)}`);
  check(r[0]?.cur&&/目前這拍/.test(r[0].text),`${tag} 多出來的那顆要是 .cur 且標「目前這拍」：${r[0]?.text}`);
  check(new Set(r.map(x=>x.top)).size===1,`${tag} 多一顆後仍一排`);
  await page.evaluate(()=>load(15));await page.waitForFunction(()=>S.id===15);
  r=await row(page);
  check(same(ids(r),EXPECT.single),`${tag} 換回相關拍後，多出來那顆要消失：${ids(r)}`);
  // 點列裡的拍
  await page.locator('#strokes button[data-id="4"]').click();await page.waitForFunction(()=>S.id===4);
  check(same(ids(await row(page)),EXPECT.single),`${tag} 點列裡的拍後列不變`);
  // 展開
  const btn=page.locator('#strokes .strokes-more');
  await btn.click();
  r=await row(page);m=await more(page);
  check(r.length===25&&same(ids(r),[...Array(25).keys()]),`${tag} 展開後要 25 拍依序：${ids(r)}`);
  check(m&&m.first&&m.exp==='true'&&/收起/.test(m.text),`${tag} 展開後開關變「收起 ▴」、aria-expanded=true、放第一顆：${JSON.stringify(m)}`);
  const kt=await kindTabs(page);
  check(kt.some(t=>/^全部/.test(t))&&kt.some(t=>/^正拍/.test(t))&&kt.some(t=>/^反拍/.test(t)),`${tag} 展開後要有種類篩選：${kt}`);
  check(await page.evaluate(()=>document.activeElement?.classList.contains('strokes-more')),`${tag} 展開後焦點仍在開關上`);
  await page.evaluate(()=>[...document.querySelectorAll('#tabs button')].find(b=>b.textContent.startsWith('反拍')).click());
  check((await row(page)).length===9&&(await row(page)).every(x=>x.id%3===0),`${tag} 展開後反拍篩選仍有用：${ids(await row(page))}`);
  // 收起（篩選是反拍時，收起後列不受它影響）
  await page.locator('#strokes .strokes-more').click();
  r=await row(page);
  check(same(ids(r),EXPECT.single),`${tag} 收起後回到相關拍（不受反拍篩選影響）：${ids(r)}`);
  check(!(await kindTabs(page)).some(t=>/^(全部|正拍|反拍)/.test(t)),`${tag} 收起後種類篩選又隱藏`);
  // 上一拍／下一拍仍走完整列表（不改控制列）
  check(await page.evaluate(()=>filter==='ALL'),`${tag} 收起後殘留的種類篩選要清掉（列看不到它，上一拍／下一拍不能還被它限制）`);
  await page.evaluate(()=>load(4));
  await page.evaluate(()=>step(1));await page.waitForFunction(()=>S.id===5);
  check(await page.evaluate(()=>S.id===5),`${tag} step(1) 仍走完整列表（#5 → #6）`);
  check(!errors.length,`${tag} 單人頁面錯誤 ${errors}`);
  await noOverflow(page,`${tag} 單人無水平溢出`);
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`synthetic-${opts.mobile?'mobile':'desktop'}-single.png`),fullPage:true});}
  await context.close();
 });
 // ---- 換場次（setDay）後收起 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await stroke(page,null,12);
  await page.locator('#strokes .strokes-more').click();
  check((await row(page)).length===25,`${tag} 展開`);
  await page.evaluate(()=>setDay(DAY));
  check((await more(page))?.exp==='false'&&(await row(page)).length<=5,`${tag} setDay 之後要收起：${JSON.stringify(await more(page))} ${(await row(page)).length}`);
  check(!errors.length,`${tag} setDay 頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 鍵盤：Tab 到開關，Enter 展開收起 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await stroke(page,null,12);
  await page.evaluate(()=>{document.activeElement?.blur();});
  await page.locator('#strokes button[data-id="15"]').focus();
  await page.keyboard.press(TAB_KEY(engine));
  check(await page.evaluate(()=>document.activeElement?.classList.contains('strokes-more')),`${tag} 從最後一拍 Tab 一下要到開關：${await page.evaluate(()=>document.activeElement?.outerHTML.slice(0,60))}`);
  await page.keyboard.press('Enter');
  check((await more(page))?.exp==='true'&&(await row(page)).length===25,`${tag} Enter 要展開`);
  check(await page.evaluate(()=>document.activeElement?.classList.contains('strokes-more')),`${tag} 展開後焦點仍在開關（鍵盤才能直接收起）`);
  await page.keyboard.press('Enter');  // 全頁的 Space 是播放／暫停（原本就這樣），所以只驗 Enter
  check((await more(page))?.exp==='false'&&(await row(page)).length===4,`${tag} 再按 Enter 要收起：${JSON.stringify(await more(page))}`);
  // 目前這拍不在列內時，鍵盤選列裡的另一拍：列會重建（多出來那顆消失），焦點要留在被選的那拍上
  await page.evaluate(()=>load(0));await page.waitForFunction(()=>S.id===0);
  await page.locator('#strokes button[data-id="4"]').focus();
  await page.keyboard.press('Enter');await page.waitForFunction(()=>S.id===4);
  check(await page.evaluate(()=>document.activeElement?.dataset?.id==='4')&&same(ids(await row(page)),EXPECT.single),`${tag} 重建列後焦點要留在 #5：${await page.evaluate(()=>document.activeElement?.outerHTML.slice(0,50))}`);
  check(!errors.length,`${tag} 鍵盤頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- insufficient：只有 look＋second.jump ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'insuf'});
  await stroke(page,null,1);
  check(same(ids(await row(page)),EXPECT.insuf),`${tag} insufficient：列要是 look＋second.jump 的拍 ${EXPECT.insuf}：${ids(await row(page))}`);
  check(!errors.length,`${tag} insufficient 頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 兩人：球員篩選 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'two'});
  await stroke(page,null,12);
  let r=await row(page);
  check(same(ids(r),EXPECT.two),`${tag} 兩人所有人：兩人的相關拍 ${EXPECT.two}，得到 ${ids(r)}`);
  check((await more(page))?.text==='全部 25 拍 ▾',`${tag} 兩人開關 N 是全部拍數：${(await more(page))?.text}`);
  check((await kindTabs(page)).some(t=>/^amy /.test(t))&&(await kindTabs(page)).some(t=>/^zed /.test(t)),`${tag} 收起時球員切換仍看得到：${await kindTabs(page)}`);
  await page.evaluate(()=>[...document.querySelectorAll('#tabs button')].find(b=>b.textContent.startsWith('amy ')).click());
  await page.evaluate(()=>load(0));await page.waitForFunction(()=>S.id===0);
  r=await row(page);
  check(same(ids(r),[0,1,2]),`${tag} 選 amy：只剩 amy 的相關拍 0,1,2：${ids(r)}`);
  check((await more(page))?.text==='全部 10 拍 ▾',`${tag} 選 amy 開關是「全部 10 拍 ▾」：${(await more(page))?.text}`);
  await page.evaluate(()=>[...document.querySelectorAll('#tabs button')].find(b=>b.textContent.startsWith('zed ')).click());
  await page.evaluate(()=>load(12));await page.waitForFunction(()=>S.id===12);
  r=await row(page);
  check(same(ids(r),[10,11,12,15]),`${tag} 選 zed：只剩 zed 的相關拍 10,11,12,15：${ids(r)}`);
  check(r.every(x=>/zed/.test(x.text)),`${tag} 兩人場次每顆標球員名：${JSON.stringify(r.map(x=>x.text))}`);
  await page.evaluate(()=>[...document.querySelectorAll('#tabs button')].find(b=>b.textContent.startsWith('所有人')).click());
  check(same(ids(await row(page)),EXPECT.two),`${tag} 選回所有人`);
  check(!errors.length,`${tag} 兩人頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 沒有 overall、拍號找不到、欄位亂 ----
 for(const scen of ['none','missing','nulled','ghost'])await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen});
  await stroke(page,null,12);
  const r=await row(page);
  check(r.length===25&&same(ids(r),[...Array(25).keys()]),`${tag} ${scen}：維持完整 25 拍：${r.length}`);
  check((await more(page))===null,`${tag} ${scen}：沒有開關`);
  const kt=await kindTabs(page);
  check(kt.some(t=>/^全部/.test(t))&&kt.some(t=>/^正拍/.test(t)),`${tag} ${scen}：種類篩選照常：${kt}`);
  check(!errors.length,`${tag} ${scen} 頁面錯誤 ${errors}`);
  await context.close();
 });
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'odd'});
  await stroke(page,null,12);
  const r=await row(page);
  check(r.some(x=>x.id===12)&&r.length<25&&(await more(page))!==null,`${tag} odd：合法的拍號照算、其餘忽略，不崩：${ids(r)}`);
  check(!errors.length,`${tag} odd 頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 手機：一行、可橫向捲動、目前這拍捲進可見範圍 ----
 if(opts.mobile)await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await stroke(page,null,12);
  const g=await page.evaluate(()=>{const b=document.getElementById('strokes');return {sw:b.scrollWidth,cw:b.clientWidth,ox:getComputedStyle(b).overflowX,wrap:getComputedStyle(b).flexWrap};});
  check(g.ox==='auto'||g.ox==='scroll',`${tag} 列要可橫向捲動（overflow-x）：${JSON.stringify(g)}`);
  check(g.sw>g.cw,`${tag} 390px 下 5 顆放不下，列要比可視寬：${JSON.stringify(g)}`);
  await noOverflow(page,`${tag} 列捲動不能把整頁撐出水平捲軸`);
  // 目前這拍（最後一顆相關拍 #16）要在列的可見範圍內
  await page.evaluate(()=>load(15));await page.waitForFunction(()=>S.id===15);
  const vis=await page.evaluate(()=>{const b=document.getElementById('strokes'),c=b.querySelector('.cur').getBoundingClientRect(),r=b.getBoundingClientRect();return c.left>=r.left-1&&c.right<=r.right+1;});
  check(vis,`${tag} 目前這拍要捲進列的可見範圍`);
  await page.evaluate(()=>{document.getElementById('strokes').scrollLeft=0;});
  const sl=await page.evaluate(()=>{const b=document.getElementById('strokes');b.scrollLeft=40;return b.scrollLeft;});
  check(sl>0,`${tag} 列真的能橫向捲動：scrollLeft=${sl}`);
  check(new Set((await row(page)).map(x=>x.top)).size===1,`${tag} 手機仍一排`);
  const hit=await page.evaluate(()=>[...document.querySelectorAll('#strokes button')].map(b=>{const r=b.getBoundingClientRect();return Math.min(r.height,r.width);}));
  check(hit.every(h=>h>=44),`${tag} 觸控按鈕要 ≥ 44px：${hit}`);
  check(!errors.length,`${tag} 手機頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 深淺色對比、桌機一排 ----
 for(const scheme of ['light','dark'])await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scheme,scen:'single'});
  await stroke(page,null,0);  // 目前這拍不在相關拍：有「目前這拍」文字
  const rs=await contrast(page,'#strokes .strokes-more, #strokes button.cur, #strokes button.cur .mini, #strokes button:not(.cur) .mini');
  const bad=rs.filter(x=>x.ratio<4.5);
  check(rs.length>=4&&bad.length===0,`${tag} ${scheme}：開關與列內文字對比要 ≥ 4.5：${JSON.stringify(bad)}（共量 ${rs.length}）`);
  await page.locator('#strokes .strokes-more').click();
  const rs2=await contrast(page,'#strokes .strokes-more');
  check(rs2.length===1&&rs2[0].ratio>=4.5,`${tag} ${scheme}：展開後「收起」對比：${JSON.stringify(rs2)}`);
  await noOverflow(page,`${tag} ${scheme} 無水平溢出`);
  check(!errors.length,`${tag} ${scheme} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

// ---- 真實副本：每場預設列對 data.js ----
async function real(browser,engine,label,opts){
 const tag=`${engine.name()} ${label} 真實副本`;
 const {page,context,errors}=await open(browser,opts);
 const days=await page.evaluate(()=>DAY_KEYS);
 let withRow=0,without=0;
 for(const day of days){
  const t=await (await fetch(new URL(`sessions/${encodeURIComponent(day)}/data.js`,f.url))).text(),raw=JSON.parse(t.slice(t.indexOf('push(')+5,t.lastIndexOf(')')));
  const ov=(raw.overall||[]).filter(o=>o&&(o.main||o.insufficient)),n=raw.strokes.length;
  await page.evaluate(d=>go(d,'stroke'),day);await page.waitForFunction(d=>TAB==='stroke'&&DAY===d&&S,day);
  await page.evaluate(()=>{pfilter='ALL';drawTabs();drawList();});
  const ownerOf=i=>raw.strokes[i].player||'me';
  const want=new Set();
  for(const o of ov){for(const k of [...(Array.isArray(o.look)?o.look:[]),...[o.main,o.second].flatMap(p=>Array.isArray(p?.jump)?p.jump.map(j=>j[0]):[])]){if(Number.isInteger(k)&&k>=1&&k<=n)want.add(k-1);}}
  const r=await row(page),m=await more(page),cur=await page.evaluate(()=>S.id);
  if(!want.size){
   without++;
   check(r.length===n&&m===null,`${tag} ${day}：沒有 overall：完整 ${n} 拍、沒有開關，得到 ${r.length} 拍、開關 ${JSON.stringify(m)}`);
  }else{
   withRow++;
   const exp=[...new Set([...want,cur])].sort((a,b)=>a-b);
   check(same(ids(r),exp),`${tag} ${day}：預設列要是 overall 標到的拍＋目前這拍 ${exp}，得到 ${ids(r)}`);
   check(m&&m.last&&m.text===`全部 ${n} 拍 ▾`,`${tag} ${day}：開關：${JSON.stringify(m)}`);
   check(new Set(r.map(x=>x.top)).size===1,`${tag} ${day}：一排`);
   await noOverflow(page,`${tag} ${day} 無水平溢出`);
   if(process.env.SITE_RESULTS&&!process.env.SITE_NO_SHOT){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`real-${engine.name()}-${opts.mobile?'mobile':'desktop'}-${day.replace(/[^\w-]/g,'_')}-row.png`),fullPage:false});}
   await page.locator('#strokes .strokes-more').click();
   check((await row(page)).length===n,`${tag} ${day}：展開後 ${n} 拍：${(await row(page)).length}`);
   if(process.env.SITE_RESULTS&&!process.env.SITE_NO_SHOT){await page.screenshot({path:path.join(process.env.SITE_RESULTS,`real-${engine.name()}-${opts.mobile?'mobile':'desktop'}-${day.replace(/[^\w-]/g,'_')}-expanded.png`),fullPage:false});}
   await page.locator('#strokes .strokes-more').click();
   check((await row(page)).length<n,`${tag} ${day}：收起`);
  }
 }
 check(withRow>0,`${tag}：副本裡至少要有一場有 overall（否則沒驗到預設列）`);
 check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
 await context.close();
}

try{
 const engines=(process.env.SITE_ENGINES||'chromium,webkit').split(',').map(x=>({chromium,webkit})[x]);
 for(const engine of engines){
  const browser=await engine.launch();
  try{
   for(const [label,opts] of [['桌機',{}],['手機 390px',{viewport:{width:390,height:800},mobile:true}]]){
    if(REAL)await real(browser,engine,label,opts);else await synthetic(browser,engine,label,opts);
   }
  }finally{await browser.close();}
 }
}finally{await f.close?.();}
if(failures.length){console.error(failures.join('\n'));process.exit(1);}
console.log('site_stroke_row ok'+(REAL?'（真實副本）':''));
