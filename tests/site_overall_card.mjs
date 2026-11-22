// 整體建議第 3 步／UI 方案 A1：總覽最上面「這場先練一件事」卡片、免責收成一行。UI 方案 A 第 5 步起卡片在一頁的第一屏（不再有總覽分頁）。
// 事前預測與失敗方式：testset/results/overall-card/pred.md。
// 合成模式（預設）：用 amy／zed 這種假名，不讀使用者資料；SITE_REF=origin/main 預期紅（找不到卡片）。
// SITE_E2E_URL＝真實副本：有 overall 的場次顯示卡片（張數、標題對 data.js）、沒有的 0 張；SITE_RESULTS＝另存截圖（私人，不進 git）。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const ONE_LINE='練習參考，不能代替教練或醫療判斷。3D 為單鏡頭估計。';
const DISCLAIMER='這是練習參考，不能代替教練或醫療判斷。';
const squash=s=>s.replace(/\s+/g,' ').trim();

// ---- 合成情境：改 fixture 的 data.js（25 拍，id 0–24；final 拍號＝id+1） ----
const MAIN={title:'自拋時把球打在身前，像對打那樣',why:'擊球點在髖前的距離，自拋 0.8、對打 1.0。看 #13、#02。',cite:[],practice:'自拋時把球丟在身體側前方一大步；下次同一機位拍，看自拋的擊球點是不是接近對打的 1.0。',cue:'打在前腳前',jump:[[13,'對打 #13'],[2,'自拋 #02']]};
const SECOND={title:'保持側身舉拍',why:'#05 擊球前已側身。',cite:[],practice:'維持現在的側身時機。',jump:[[5,'看 #05']]};  // 沒有口訣
const INSUF={title:'資料不足以給方向',why:'只有 4 拍正拍，全是對打，看不出要先改的地方。',cite:[]};
const FILM='手機放在側面約 90°、固定、全身在畫面中間，連續正拍 30 拍以上。';
const tamper=(o,n)=>({...o,title:o.title+n});
const SCEN={
 single:{players:['me'],overall:[{player:'me',main:MAIN,second:SECOND,look:[2,5,13]}]},
 insuf:{players:['me'],overall:[{player:'me',insufficient:INSUF,film_next:FILM,second:{title:'看圖觀察：拍子在後',why:'#03 擊球前拍子已在後。',cite:[],jump:[[3,'看 #03']]},look:[1,2,3]}]},
 two:{players:['amy','zed'],owners:id=>id<10?'amy':'zed',  // amy 10 拍、zed 15 拍；overall 陣列 amy 在前，頁面要 zed 在前
      overall:[{player:'amy',insufficient:{...INSUF,title:'amy：資料不足'},film_next:FILM,look:[1,2,3]},{player:'zed',main:{...MAIN,title:'zed 的重點',jump:[[13,'zed #13'],[16,'zed #16']]},look:[11,12,13]}]},
 twoMain:{players:['amy','zed'],owners:id=>id%2?'amy':'zed',  // 各 12／13 拍，兩人都有 main
      overall:[{player:'amy',main:{...MAIN,title:'amy 的重點',jump:[[2,'amy #02']]},look:[2,4,6]},{player:'zed',main:{...MAIN,title:'zed 的重點',jump:[[1,'zed #01']]},look:[1,3,5]}]},
 none:{players:['me'],overall:[]},
 missing:{players:['me'],overall:undefined},  // 舊 data.js：沒有 overall 欄
 nulled:{players:['me'],overall:null},
 broken:{players:['me'],overall:[{player:'me',look:[1,2,3]},{player:'me',main:tamper(MAIN,'<img src=x onerror="window.__xss=1">'),look:[2,5,13]}]},  // 第一筆壞（沒 main 也沒 insufficient）：略過；第二筆標題含 HTML：當文字
};

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
 if(await page.evaluate(()=>pfilter!=='ALL'))await page.evaluate(()=>{[...document.querySelectorAll('#players button')].find(b=>b.dataset.p==='ALL')?.click();});  // UI 方案 A 第 6 步：沒 hash 進來時多人場次預設拍數最多的球員；這支測「所有人」，先切回去
 return {page,context,errors};
}
// UI 方案 A 第 5 步：卡片在一頁的第一屏（.lead），不用再切到總覽分頁；這裡打開沒帶分頁的 #d<場次>
const overview=async(page,day)=>{await page.evaluate(d=>go(d??DAY),day);await page.waitForFunction(d=>DAY===(d??DAY)&&TAB===''&&S&&!$('lead').hidden,day);};
const cards=page=>page.evaluate(()=>[...document.querySelectorAll('#overall .ov-card')].map(c=>({
 cls:c.className,name:c.querySelector('.ov-name')?.textContent.trim()??null,title:c.querySelector('.ov-title')?.textContent.trim(),
 why:c.querySelector('.ov-why')?.textContent.replace(/\s+/g,' ').trim()??null,practice:c.querySelector('.ov-practice')?.textContent.replace(/\s+/g,' ').trim()??null,
 cue:c.querySelector('.ov-cue')?.textContent.replace(/\s+/g,' ').trim()??null,film:c.querySelector('.ov-film')?.textContent.replace(/\s+/g,' ').trim()??null,
 jumps:[...c.querySelectorAll(':scope > .ov-body > .ov-acts > .ov-jump button')].map(b=>b.textContent.trim()),
 second:(d=>d&&{open:d.open,summary:d.querySelector('summary').textContent.trim(),title:d.querySelector('.ov-title')?.textContent.trim(),jumps:[...d.querySelectorAll('.ov-jump button')].map(b=>b.textContent.trim()),cue:d.querySelector('.ov-cue')?.textContent.trim()??null})(c.querySelector('details.ov-second')),
 text:c.textContent.replace(/\s+/g,' ').trim()})));
const pick=(page,label)=>page.evaluate(l=>{const b=[...document.querySelectorAll('#players button')].find(x=>l instanceof RegExp?x.textContent.startsWith(l):x.textContent.startsWith(l));b.click();},label);
const noOverflow=(page,msg)=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth).then(ok=>check(ok,msg));

// 對比（WCAG）：文字色對它實際看到的背景（往上找第一個不透明背景）
const contrast=(page,sel)=>page.evaluate(sel=>{
 const rgb=s=>s.match(/[\d.]+/g).map(Number),lum=([r,g,b])=>[r,g,b].map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll(sel)].filter(e=>e.offsetParent).map(e=>{
  const fg=rgb(getComputedStyle(e).color);let bg=null,n=e;
  while(n){const c=getComputedStyle(n).backgroundColor,v=rgb(c);if(v.length>=3&&(v.length<4||v[3]>0.99)&&!/rgba\(0, 0, 0, 0\)/.test(c)){bg=v;break;}n=n.parentElement;}
  bg??=[255,255,255];const a=lum(fg),b=lum(bg);return {sel,text:e.textContent.trim().slice(0,20),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
},sel);

const sect=async(tag,fn)=>{try{await fn();}catch(e){failures.push(`${tag} 例外：${String(e.message).split('\n')[0]}`);}};
async function synthetic(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 // ---- 單人：main＋second ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await overview(page);
  const c=await cards(page);
  check(c.length===1,`${tag} 單人 main＋second：要 1 張卡，得到 ${c.length}`);
  if(c.length===1){
   const k=c[0];
   check(k.name===null,`${tag} 單人場次不顯示名字，得到「${k.name}」`);
   check(k.title===MAIN.title&&k.why?.includes(MAIN.why)&&k.practice?.includes(MAIN.practice),`${tag} 標題／為什麼／練法要照 overall.main：${JSON.stringify(k)}`);
   check(k.cue?.includes('打在前腳前'),`${tag} 有口訣要顯示：${k.cue}`);
   check(JSON.stringify(k.jumps)===JSON.stringify(['對打 #13','自拋 #02']),`${tag} main 的 jump 按鈕要 2 顆：${JSON.stringify(k.jumps)}`);
   check(k.second&&k.second.open===false&&/次要/.test(k.second.summary),`${tag} second 要是收起的 details、摘要有「次要」：${JSON.stringify(k.second)}`);
   check(k.second?.cue===null,`${tag} second 沒口訣就不顯示口訣`);
   check(!k.text.includes(SECOND.practice)||!(await page.locator('details.ov-second .ov-practice').isVisible()),`${tag} second 預設收起時內文看不到`);
   await page.locator('#overall .ov-full').first().click();  // 一頁：次要收在「看全文」裡
   await page.locator('details.ov-second summary').click();
   check(await page.locator('details.ov-second .ov-title').isVisible()&&(await page.locator('details.ov-second .ov-title').textContent()).trim()===SECOND.title,`${tag} 展開 second 後看得到它的標題`);
   check(JSON.stringify((await cards(page))[0].second.jumps)===JSON.stringify(['看 #05']),`${tag} second 的 jump 按鈕`);
   // 標題比 second 大
   const sizes=await page.evaluate(()=>[parseFloat(getComputedStyle(document.querySelector('.ov-main .ov-title')).fontSize),parseFloat(getComputedStyle(document.querySelector('details.ov-second .ov-title')).fontSize)]);
   check(sizes[0]>sizes[1],`${tag} second 要小一號：${sizes}`);
   // 位置：卡片在一頁最上面（影片、免責一行之上）
   const y=await page.evaluate(()=>{const top=e=>e?e.getBoundingClientRect().top+scrollY:null;return {card:top(document.querySelector('.ov-card')),limits:top(document.querySelector('#oneLine')),stage:top(document.querySelector('#stage'))};});
   check(y.card!=null&&y.card<y.stage&&y.card<(y.limits??1e9),`${tag} 卡片要在一頁最上面（影片與免責一行之上）：${JSON.stringify(y)}`);
  }
  // 免責一行與「數字的限制 ›」
  const line=squash(await page.locator('#oneLine').first().textContent().catch(()=>''));
  check(line.includes(ONE_LINE),`${tag} 卡片下要有一行免責「${ONE_LINE}」，得到「${line}」`);
  const btn=page.locator('#oneLine button.ov-limits-btn');
  check(await btn.count()===1&&/數字的限制/.test(await btn.textContent()),`${tag} 要有「數字的限制 ›」按鈕`);
  check((await btn.getAttribute('aria-expanded'))==='false',`${tag} 按鈕要有 aria-expanded=false`);
  check(!(await page.locator('#methodNote').isVisible())&&!(await page.locator('#limits .disclaimer',{hasText:DISCLAIMER}).first().isVisible()),`${tag} 收起時方法說明與原本的免責段落看不到`);
  await btn.click();
  check((await btn.getAttribute('aria-expanded'))==='true',`${tag} 展開後 aria-expanded=true`);
  const full=squash(await page.locator('#secLong').innerText());
  check(await page.locator('#methodNote').isVisible()&&/方法說明：/.test(await page.locator('#methodNote').textContent()),`${tag} 展開後方法說明要看得到`);
  check(full.includes(DISCLAIMER)&&/「3D估」為 3D 估計（單鏡頭，僅供參考），是模型從單一鏡頭估出的人體相對座標，不是多機校正的實測角度。/.test(full),`${tag} 展開後原本的免責與 3D 說明要一字不少`);
  await btn.press('Enter');  // 鍵盤也能收
  check((await btn.getAttribute('aria-expanded'))==='false'&&!(await page.locator('#methodNote').isVisible()),`${tag} 再按（Enter）要收起`);
  await noOverflow(page,`${tag} 單人總覽無水平溢出`);
  check(!errors.length,`${tag} 單人總覽頁面錯誤 ${errors}`);
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`synthetic-${opts.mobile?'mobile':'desktop'}-single.png`),fullPage:true});}
  await context.close();
 });
 // ---- jump：滑鼠與鍵盤 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'single'});
  await overview(page);
  await page.locator('#overall .ov-main button',{hasText:'對打 #13'}).click();
  await page.waitForFunction(()=>S?.id===12);  // 一頁：不換分頁，只換拍
  check(await page.evaluate(()=>S.id===12&&byNo(13)===S),`${tag} 點「對打 #13」要跳到單拍 #13（S.id===12），得到 ${await page.evaluate(()=>location.hash+' '+S?.id)}`);
  await overview(page);
  await page.locator('#overall .ov-main button',{hasText:'自拋 #02'}).click();
  await page.waitForFunction(()=>S?.id===1);
  check(await page.evaluate(()=>S.id===1),`${tag} 點「自拋 #02」要跳到單拍 #02`);
  // 鍵盤：從總覽按 Tab 找到 jump 按鈕，Enter 跳拍
  await overview(page);
  await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);});
  let hit=null;
  const TAB_KEY=engine.name()==='webkit'&&process.platform==='darwin'?'Alt+Tab':'Tab';  // macOS 的 Safari／WebKit 預設 Tab 跳過按鈕，要 Option+Tab
  for(let i=0;i<60&&!hit;i++){await page.keyboard.press(TAB_KEY);hit=await page.evaluate(()=>{const a=document.activeElement;return a?.closest('#overall .ov-jump')?a.textContent.trim():null;});}
  check(hit==='對打 #13',`${tag} 鍵盤 Tab 要先到第一顆 jump 按鈕「對打 #13」，得到「${hit}」`);
  if(hit){await page.keyboard.press('Enter');await page.waitForFunction(()=>S?.id===12).catch(()=>{});check(await page.evaluate(()=>S.id===12),`${tag} 鍵盤 Enter 要跳到 #13：${await page.evaluate(()=>TAB+' '+S?.id)}`);}
  check(!errors.length,`${tag} jump 頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- insufficient＋film_next（＋second） ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'insuf'});
  await overview(page);
  const c=await cards(page);
  check(c.length===1,`${tag} insufficient：1 張卡，得到 ${c.length}`);
  if(c.length===1){
   const k=c[0];
   check(/ov-insufficient/.test(k.cls)&&k.title===INSUF.title&&k.why?.includes(INSUF.why),`${tag} insufficient 標題與為什麼：${JSON.stringify(k)}`);
   check(k.film?.includes('下次這樣拍')&&k.film.includes(FILM),`${tag} 要顯示「下次這樣拍：film_next」：${k.film}`);
   check(k.jumps.length===0&&k.practice===null&&k.cue===null,`${tag} insufficient 沒有 jump／練法／口訣`);
   check(!/錯誤|失敗|警告|異常|不合格/.test(k.text),`${tag} insufficient 語氣中性，不能有錯誤／失敗／警告字眼：「${k.text}」`);
   check(k.second&&k.second.open===false&&/次要/.test(k.second.summary),`${tag} insufficient 的 second（看圖觀察）也要收起、標次要：${JSON.stringify(k.second)}`);
   const border=await page.locator('.ov-insufficient').evaluate(e=>[getComputedStyle(e).borderLeftColor,getComputedStyle(document.documentElement).getPropertyValue('--warn').trim()]);
   check(border[0]!==undefined&&!/^(rgb\(240, 150, 90\)|rgb\(201, 106, 31\)|rgb\(\d+, 0, 0\))/.test(border[0]),`${tag} insufficient 不用警示色當邊框：${border}`);
  }
  check(!errors.length,`${tag} insufficient 頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 兩人：拍數多的在前、名字、pfilter ----
 for(const scen of ['two','twoMain'])await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen});
  await overview(page);
  let c=await cards(page);
  const first=scen==='two'?'zed':null;  // two：zed 15 拍、amy 10 拍；twoMain：zed 13（偶數 id 0..24）、amy 12
  check(c.length===2,`${tag} ${scen} 所有人：每人一張共 2 張，得到 ${c.length}`);
  if(c.length===2){
   check(c[0].name==='zed'&&c[1].name==='amy',`${tag} ${scen}：拍數多的在前（zed 再 amy），得到 ${c.map(x=>x.name)}`);
   check(c[0].title===(scen==='two'?'zed 的重點':'zed 的重點')&&c[1].title===(scen==='two'?'amy：資料不足':'amy 的重點'),`${tag} ${scen}：各卡內容要屬於各自的人：${c.map(x=>x.title)}`);
  }
  await page.evaluate(()=>go(DAY,'stroke'));await page.waitForFunction(()=>TAB==='stroke');
  await pick(page,'amy ');await overview(page);
  c=await cards(page);
  check(c.length===1&&c[0].name==='amy',`${tag} ${scen} 選 amy：只剩 amy 的卡，得到 ${JSON.stringify(c.map(x=>x.name))}`);
  await page.evaluate(()=>go(DAY,'stroke'));await pick(page,'zed ');await overview(page);
  c=await cards(page);
  check(c.length===1&&c[0].name==='zed',`${tag} ${scen} 選 zed：只剩 zed 的卡，得到 ${JSON.stringify(c.map(x=>x.name))}`);
  if(scen==='two'&&c.length===1){  // zed 的 jump 對到 zed 的拍（final #13、#16）
   await page.locator('#overall .ov-main button',{hasText:'zed #16'}).click();await page.waitForFunction(()=>S?.id===15);
   check(await page.evaluate(()=>S.player==='zed'),`${tag} zed 的 jump 要到 zed 的拍`);
  }
  await page.evaluate(()=>go(DAY,'stroke'));await pick(page,'所有人');await overview(page);
  check((await cards(page)).length===2,`${tag} ${scen} 選回所有人：2 張`);
  // 已經在總覽時點人也要即時更新（呼叫按鈕 onclick）
  await page.evaluate(()=>{pfilter='ALL';});
  await page.evaluate(()=>{[...document.querySelectorAll('#players button')].find(x=>x.textContent.startsWith('amy ')).click();});
  check((await cards(page)).length===1,`${tag} ${scen} 在總覽內改 pfilter 要立刻重畫`);
  check(!errors.length,`${tag} ${scen} 頁面錯誤 ${errors}`);
  await noOverflow(page,`${tag} ${scen} 無水平溢出`);
  await context.close();
 });
 // ---- 沒有 overall 的舊場次：畫面維持原樣 ----
 for(const scen of ['none','missing','nulled'])await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen});
  await overview(page);
  check((await page.locator('.ov-card').count())===0&&(await page.locator('#overall .ov-card').count())===0,`${tag} ${scen}：沒有 overall 不能畫卡`);
  check((await page.locator('#lead').innerText()).indexOf('這場先練一件事')<0,`${tag} ${scen}：不能出現空的「這場先練一件事」框`);
  // 一頁（UI 方案 A 第 5 步）：有沒有卡，第一屏都是一行免責＋「數字的限制 ›」，原本那句免責、方法說明、3D 說明在「長說明」
  check(await page.locator('#oneLine').isVisible()&&squash(await page.locator('#oneLine').textContent()).includes(ONE_LINE)&&await page.locator('#oneLine button.ov-limits-btn').count()===1,`${tag} ${scen}：第一屏要有一行免責與「數字的限制 ›」`);
  await page.locator('#oneLine button.ov-limits-btn').click();
  const el=page.locator('#limits .disclaimer:visible');
  check(await el.count()===1&&(await el.textContent()).trim()===DISCLAIMER,`${tag} ${scen}：打開後原本那句免責看得到（site_method_notes 的條件）`);
  check(await page.locator('#methodNote').isVisible(),`${tag} ${scen}：打開後方法說明看得到`);
  check(/3D 估計.*單鏡頭.*僅供參考/.test(await page.locator('#limits').innerText()),`${tag} ${scen}：3D 估計說明維持`);
  check(!errors.length,`${tag} ${scen} 頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 壞項目與 HTML 文字 ----
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'broken'});
  await overview(page);
  const c=await cards(page);
  check(c.length===1,`${tag} 沒 main／insufficient 的壞項目要略過、不畫空卡：得到 ${c.length}`);
  check(c.length===1&&c[0].title.includes('<img src=x onerror='),`${tag} 標題裡的 HTML 要當文字顯示：${c[0]?.title}`);
  check(await page.evaluate(()=>window.__xss!==1&&!document.querySelector('#overall img')),`${tag} 標題裡的 HTML 不能被執行`);
  check(!errors.length,`${tag} 壞項目頁面錯誤 ${errors}`);
  await context.close();
 });
 // ---- 深淺色對比、手機版面 ----
 for(const scheme of ['light','dark'])await sect(tag,async()=>{
  for(const scen of ['single','insuf'])await sect(tag,async()=>{
   const {page,context,errors}=await open(browser,{...opts,scheme,scen});
   await overview(page);
   await page.locator('#overall .ov-full').first().click();
   await page.locator('details.ov-second summary').first().click();
   const rs=await contrast(page,'#overall .ov-card, #overall .ov-card :is(.ov-name,.ov-kicker,.ov-title,.ov-why,.ov-practice,.ov-cue,.ov-film,summary,button), #oneLine, #oneLine .ov-limits-btn');
   const bad=rs.filter(r=>r.ratio<4.5);
   check(rs.length>5&&bad.length===0,`${tag} ${scheme} ${scen}：文字對比要 ≥ 4.5：${JSON.stringify(bad)}（共量 ${rs.length} 個）`);
   check(!errors.length,`${tag} ${scheme} ${scen} 頁面錯誤 ${errors}`);
   await noOverflow(page,`${tag} ${scheme} ${scen} 無水平溢出`);
   await context.close();
  });
 });
}

// ---- 真實副本：每場 data.js 的 overall 對畫面 ----
async function real(browser,engine,label,opts){
 const tag=`${engine.name()} ${label} 真實副本`;
 const {page,context,errors}=await open(browser,opts);
 const ids=await page.evaluate(()=>DAY_KEYS);
 let withCards=0,without=0;
 for(const id of ids){
  const t=await (await fetch(new URL(`sessions/${encodeURIComponent(id)}/data.js`,f.url))).text(),raw=JSON.parse(t.slice(t.indexOf('push(')+5,t.lastIndexOf(')')));
  const ov=(raw.overall||[]).filter(o=>o.main||o.insufficient);
  await overview(page,id);
  const c=await cards(page);
  if(!ov.length){
   without++;
   check(c.length===0,`${tag} ${id}：沒有 overall 不能畫卡，得到 ${c.length}`);
   check(await page.locator('#oneLine').isVisible(),`${tag} ${id}：沒有 overall 的場次也有一行免責`);
  }else{
   withCards++;
   check(c.length===ov.length,`${tag} ${id}：卡數要 ${ov.length}，得到 ${c.length}`);
   const want=new Set(ov.map(o=>(o.main||o.insufficient).title));
   check(c.every(k=>want.has(k.title)),`${tag} ${id}：卡片標題要在 data.js 的 overall 內：${JSON.stringify(c.map(k=>k.title))}`);
   const mainOnes=ov.filter(o=>o.main);
   if(mainOnes.length){  // 第一顆 jump 要跳到那一拍
    const [n,lab]=mainOnes[0].main.jump[0];
    await page.locator('#overall .ov-main .ov-jump button',{hasText:lab}).first().click();
    await page.waitForFunction(n=>S?.id===n-1,n).catch(()=>{});
    check(await page.evaluate(n=>S.id===n-1,n),`${tag} ${id}：jump「${lab}」要到 #${n}，得到 id ${await page.evaluate(()=>S.id)}`);
    await overview(page,id);
   }
   await noOverflow(page,`${tag} ${id} 總覽無水平溢出`);
   if(process.env.SITE_RESULTS&&!process.env.SITE_NO_SHOT){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`real-${engine.name()}-${opts.mobile?'mobile':'desktop'}-${id.replace(/[^\w-]/g,'_')}.png`),fullPage:false});}
  }
 }
 check(withCards>0,`${tag}：副本裡至少要有一場有 overall（否則沒驗到卡片）`);
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
console.log('site_overall_card ok'+(REAL?'（真實副本）':''));
