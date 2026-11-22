// UI 方案 A 第 6 步：沒帶 hash 打開就進最近一場（日期最新；同日拍數多的）；多人場次預設拍數最多的球員。
// 「其他場次」展開區放首頁的場次列表（同一個函式畫），並有「所有場次」連結回首頁 #home；有 hash 的舊網址照舊。
// 事前預測與失敗方式：testset/results/ui-a6/pred.md（私人，不進 git）。
// 合成模式（預設）：用 page.route 把合成場次改成多場、amy／zed 假名，不讀使用者資料；SITE_REF=origin/main 時跳過（舊網頁沒有這些行為）。
// SITE_FORCE=1 SITE_REF=origin/main：硬跑舊網頁，證明這支測試抓得到（預期紅）；SITE_ENGINE=chromium|webkit 只跑一個引擎。
// SITE_E2E_URL＝真實副本：沒 hash 進哪一場、展開區列數、每場舊網址；SITE_RESULTS＝另存截圖（私人，不進 git）。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
if(process.env.SITE_REF&&!process.env.SITE_FORCE){console.log('skipped site_latest_entry.mjs: it checks new behaviour, SITE_REF runs the old page');process.exit(0);}
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const sect=async(tag,fn)=>{try{await fn();}catch(e){failures.push(`${tag} 例外：${String(e.message).split('\n')[0]}`);}};

// ---- 合成情境：每場 {id,date,label,players:{名字:拍數}}，players 的順序＝拍子的分配順序 ----
const SC={
 two:[{id:'old',date:'2026-01-01',label:'舊場',players:{amy:10,zed:10}},{id:'new',date:'2026-01-05',label:'新場',players:{amy:5,zed:15}}],  // 新的排在 manifest 後面
 newFirst:[{id:'new',date:'2026-01-05',label:'新場',players:{me:8}},{id:'old',date:'2026-01-01',label:'舊場',players:{me:20}}],  // 新的排在 manifest 前面：不能用清單順序
 tie:[{id:'zzz-small',date:'2026-01-09',label:'同日少',players:{me:10}},{id:'aaa-big',date:'2026-01-09',label:'同日多',players:{me:20}},{id:'ccc-older',date:'2026-01-02',label:'更早',players:{me:25}}],
 amyMore:[{id:'only',date:'2026-01-05',label:'唯一',players:{amy:15,zed:5}}],
 single:[{id:'only',date:'2026-01-05',label:'唯一',players:{me:12}}],
 undated:[{id:'u1',label:'無日期一',players:{me:12}},{id:'u2',label:'無日期二',players:{me:6}}],
};
async function open(browser,{viewport,mobile,scheme,scen,hash=''}={}){
 const context=await browser.newContext({viewport:viewport||{width:1280,height:800},isMobile:!!mobile,hasTouch:!!mobile,colorScheme:scheme||'light'}),page=await context.newPage(),errors=[],clips=[];page.setDefaultTimeout(8000);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/Failed to load resource/.test(m.text()))errors.push('console: '+m.text());});
 page.on('request',r=>{if(/\.mp4/.test(r.url()))clips.push(r.url());});
 if(scen){
  const list=SC[scen];
  await page.route('**/sessions/manifest.js*',route=>route.fulfill({contentType:'text/javascript; charset=utf-8',body:`window.SESSION_IDS=${JSON.stringify(list.map(s=>s.id))};window.SESSION_VER=${JSON.stringify(Object.fromEntries(list.map(s=>[s.id,'t'])))};`}));
  for(const s of list){
   await page.route(`**/sessions/${s.id}/data.js*`,async route=>{
    const base=await (await route.fetch({url:new URL('sessions/synthetic/data.js',f.url).href})).text(),head='window.SESSIONS=[',json=JSON.parse(base.slice(head.length,base.lastIndexOf(']')));
    const names=Object.keys(s.players),total=Object.values(s.players).reduce((a,b)=>a+b,0),own=names.flatMap(n=>Array(s.players[n]).fill(n));
    json.id=s.id;json.label=s.label;if(s.date)json.date=s.date;else delete json.date;json.players=names;json.strokes=json.strokes.slice(0,total);json.strokes.forEach((x,i)=>{x.player=own[i];});
    await route.fulfill({contentType:'text/javascript; charset=utf-8',body:'(window.SESSIONS=window.SESSIONS||[]).push('+JSON.stringify(json)+');'});
   });
   await page.route(`**/sessions/${s.id}/pose/*.js*`,async route=>{
    const text=await (await route.fetch({url:route.request().url().replace(`/sessions/${s.id}/`,'/sessions/synthetic/')})).text();
    await route.fulfill({contentType:'text/javascript; charset=utf-8',body:text.replace('POSE("synthetic"',`POSE("${s.id}"`)});
   });
  }
 }
 await page.goto(f.url+hash);await page.waitForSelector('body.ready');
 return {page,context,errors,clips};
}
const state=page=>page.evaluate(()=>({day:typeof DAY==='undefined'?null:DAY,hash:location.hash,pfilter:typeof pfilter==='undefined'?null:pfilter,home:!$('home').hidden,main:!document.querySelector('main').hidden,hist:history.length,
 pressed:[...document.querySelectorAll('#players button[aria-pressed="true"]')].map(b=>b.textContent.trim()),strokes:[...document.querySelectorAll('#strokes button[data-id]')].map(b=>typeof who==='function'?who(ALL[+b.dataset.id]):'?')}));
const noOverflow=(page,msg)=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth).then(ok=>check(ok,msg));
const contrast=(page,sel)=>page.evaluate(sel=>{
 const rgb=s=>s.match(/[\d.]+/g).map(Number),lum=([r,g,b])=>[r,g,b].map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll(sel)].filter(e=>e.offsetParent&&e.textContent.trim()).map(e=>{
  const fg=rgb(getComputedStyle(e).color);let bg=null,n=e;
  while(n){const c=getComputedStyle(n).backgroundColor,v=rgb(c);if(v.length>=3&&(v.length<4||v[3]>0.99)&&!/rgba\(0, 0, 0, 0\)/.test(c)){bg=v;break;}n=n.parentElement;}
  bg??=[255,255,255];const a=lum(fg),b=lum(bg);return {text:e.textContent.trim().slice(0,16),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
},sel);
const secBtn=page=>page.locator('main .sec .sec-btn',{has:page.locator('.sec-title',{hasText:/^其他場次$/})});

async function synthetic(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`,phone=!!opts.mobile;
 // ---- 沒 hash：進哪一場、哪位球員 ----
 for(const [scen,wantDay,wantP,wantStrokes] of [['two','new','zed',15],['newFirst','new','ALL',8],['tie','aaa-big','ALL',20],['amyMore','only','amy',15],['single','only','ALL',12],['undated','u2','ALL',6]]){
  await sect(`${tag} ${scen}`,async()=>{
   const {page,context,errors}=await open(browser,{...opts,scen});
   await page.waitForFunction(()=>typeof S!=='undefined'&&S);
   const st=await state(page),t=`${tag} 沒 hash（${scen}）`;
   check(st.day===wantDay&&st.main&&!st.home,`${t}：要進 ${wantDay}，得到 ${JSON.stringify(st)}`);
   check(st.hash===`#d${wantDay}`,`${t}：網址要換成 #d${wantDay}：${st.hash}`);
   check(st.hist===2,`${t}：不能多一筆歷史（about:blank＋這頁＝2；用 location.hash 換會變 3，上一頁會繞回空網址）：history.length=${st.hist}`);
   check(st.pfilter===wantP,`${t}：預設球員 ${wantP}，得到 ${st.pfilter}`);
   check(st.strokes.length===wantStrokes&&(wantP==='ALL'||st.strokes.every(x=>x===wantP)),`${t}：拍子列 ${wantStrokes} 拍${wantP==='ALL'?'':'、全是 '+wantP}：${st.strokes.length}`);
   if(wantP!=='ALL')check(st.pressed.length===1&&st.pressed[0].startsWith(wantP),`${t}：球員鈕要按下 ${wantP}：${st.pressed}`);
   await page.waitForTimeout(300);
   check((await state(page)).day===wantDay,`${t}：等一下仍在 ${wantDay}（不能被第二次 route 洗掉）`);
   check(!errors.length,`${t} 頁面錯誤 ${errors}`);
   await context.close();
  });
 }
 // ---- 有 hash 的舊網址照舊 ----
 await sect(`${tag} 舊網址`,async()=>{
  for(const [hash,want] of [['#home','home'],['#bogus','home'],['#dmissing','home'],['#dold','old'],['#dold/video','old'],['#dnew','new']]){
   const {page,context,errors,clips}=await open(browser,{...opts,scen:'two',hash});
   if(want!=='home')await page.waitForFunction(()=>typeof S!=='undefined'&&S);
   const st=await state(page),t=`${tag} ${hash}`;
   if(want==='home'){
    check(st.home&&!st.main,`${t}：照舊是首頁：${JSON.stringify(st)}`);
    check(await page.evaluate(()=>document.querySelectorAll('#home .sess a').length)===4,`${t}：首頁有 4 列（2 位球員 × 2 場）`);
    await page.waitForTimeout(300);check(clips.length===0,`${t}：首頁不抓影片：${clips}`);
   }else{
    check(st.day===want&&st.main&&!st.home&&st.hash===hash,`${t}：照舊進 ${want}，網址不被改：${JSON.stringify(st)}`);
    check(st.pfilter==='ALL',`${t}：有 hash 不套預設球員：${st.pfilter}`);
   }
   check(!errors.length,`${t} 頁面錯誤 ${errors}`);
   await context.close();
  }
 });
 // ---- 其他場次展開區 ----
 await sect(`${tag} 展開區`,async()=>{
  const {page,context,errors}=await open(browser,{...opts,scen:'two'});
  await page.waitForFunction(()=>typeof S!=='undefined'&&S);
  const t=`${tag} 其他場次`;
  check(await page.evaluate(()=>!document.querySelector('#days, .days')),`${t}：舊的日期按鈕列要拿掉`);
  check((await secBtn(page).locator('.sec-meta').textContent()).trim()==='2 場',`${t}：標題旁寫「2 場」`);
  check(await page.evaluate(()=>[...document.querySelectorAll('.sess')].every(e=>!e.offsetParent&&e.closest('#secDaysBody'))),`${t}：收著時列表看不到，頁面上也沒有第二份`);
  await secBtn(page).click();
  const body=page.locator('#secDaysBody');
  const rows=await page.evaluate(()=>[...document.querySelectorAll('#secDaysBody .who .card')].map(c=>({who:c.querySelector('h2').textContent.trim(),rows:[...c.querySelectorAll('.sess a')].map(a=>({href:a.getAttribute('href'),text:a.textContent.replace(/\s+/g,' ').trim(),cur:a.getAttribute('aria-current')}))})));
  check(rows.length===2&&rows[0].who==='zed'&&rows[1].who==='amy',`${t}：每位球員一張卡（拍數多的 zed 在前）：${JSON.stringify(rows.map(r=>r.who))}`);
  check(rows.every(r=>r.rows.length===2&&r.rows[0].href==='#dnew'&&r.rows[1].href==='#dold'),`${t}：每位球員 2 場，日期新的在前：${JSON.stringify(rows)}`);
  check(rows[0].rows[0].text.includes('新場')&&rows[0].rows[0].text.includes('15 拍')&&rows[0].rows[1].text.includes('10 拍')&&rows[1].rows[0].text.includes('5 拍'),`${t}：列上有場次名稱與各人拍數：${JSON.stringify(rows)}`);
  check(rows.every(r=>r.rows[0].cur==='page'&&r.rows[1].cur===null),`${t}：目前這場的列標 aria-current=page：${JSON.stringify(rows)}`);
  check(await page.evaluate(()=>[...document.querySelectorAll('#secDaysBody a[aria-current] .sc b')].every(b=>getComputedStyle(b,'::after').content==='none')&&[...document.querySelectorAll('#secDaysBody a[aria-current]>b')].every(b=>getComputedStyle(b,'::after').content.includes('目前'))),`${t}：「（目前）」只標在場次名稱後面，不能標到分數上`);
  check(await page.evaluate(()=>{const rows=[...document.querySelectorAll('#secDaysBody a[aria-current]')];return rows.length>0&&rows.every(a=>[a,...a.querySelectorAll('*')].filter(e=>getComputedStyle(e,'::after').content.includes('目前')).length===1);}),`${t}：目前這列的「（目前）」只能出現 1 次`);
  const link=body.locator('a.all-link');
  check(await link.count()===1&&(await link.getAttribute('href'))==='#home'&&/所有場次/.test(await link.textContent()),`${t}：要有「所有場次」連結到 #home`);
  // 和首頁同一份：先記下展開區的列，去首頁比
  const same=rows.flatMap(r=>r.rows.map(x=>r.who+'|'+x.href+'|'+x.text));
  await noOverflow(page,`${t} 無水平溢出`);
  const low=(await contrast(page,'#secDaysBody .sess a, #secDaysBody .sess .meta, #secDaysBody .sess .sc, #secDaysBody .all-link, #secDaysBody h2')).filter(r=>r.ratio<4.5);
  check(!low.length,`${t} 對比不足：${JSON.stringify(low)}`);
  if(phone){const small=await page.evaluate(()=>[...document.querySelectorAll('#secDaysBody a')].filter(a=>a.getBoundingClientRect().height<44).map(a=>a.textContent.trim().slice(0,12)));check(!small.length,`${t} 手機點擊目標 ≥ 44 px：${JSON.stringify(small)}`);}
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await body.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.SITE_RESULTS,`synthetic-days-${phone?'phone':'desk'}-${opts.scheme||'light'}.png`)});}
  // 點目前這場的另一位球員：就地切（網址不變）
  const amyNow=body.locator('.who .card',{has:page.locator('h2',{hasText:/^amy$/})}).locator('.sess a[href="#dnew"]');
  await page.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));
  check(await page.evaluate(()=>scrollY>0),`${t}：前提：點之前頁面已捲離頂端`);
  await amyNow.click();
  let st=await state(page);
  check(await page.evaluate(()=>scrollY===0),`${t}：點目前這場的另一位球員 → 回到頂端：scrollY=${await page.evaluate(()=>scrollY)}`);
  check(st.day==='new'&&st.hash==='#dnew'&&st.pfilter==='amy'&&st.strokes.every(x=>x==='amy')&&st.strokes.length===5,`${t}：點目前這場的 amy → 就地切到 amy：${JSON.stringify(st)}`);
  // 點別場的某位球員：換場、球員跟著
  const zedOld=body.locator('.who .card',{has:page.locator('h2',{hasText:/^zed$/})}).locator('.sess a[href="#dold"]');
  await secBtn(page).getAttribute('aria-expanded')==='true'||await secBtn(page).click();
  await page.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));
  check(await page.evaluate(()=>scrollY>0),`${t}：前提：點別場之前頁面已捲離頂端`);
  await zedOld.click();await page.waitForFunction(()=>DAY==='old');await page.waitForTimeout(150);
  check(await page.evaluate(()=>scrollY===0)&&await secBtn(page).getAttribute('aria-expanded')==='false'&&await page.evaluate(()=>document.querySelector('#secDaysBody').hidden),`${t}：點別場 → 換場後回到頂端並收起「其他場次」：${JSON.stringify(await page.evaluate(()=>({y:scrollY,exp:document.querySelector('#secDays .sec-btn').getAttribute('aria-expanded')})))}`);
  await secBtn(page).click();  // 後面的步驟還要用展開區
  // 空白鍵在列表連結上不能當播放（放在換場的捲動檢查之後：Chromium 的空白鍵捲頁動畫會把頁面帶離頂端）
  await body.locator('.sess a').first().focus();await page.keyboard.press(' ');
  check(await page.evaluate(()=>!v._want),`${t}：在列表連結上按空白鍵不能開始播放`);
  st=await state(page);
  check(st.day==='old'&&st.pfilter==='zed'&&st.strokes.length===10&&st.strokes.every(x=>x==='zed'),`${t}：點 old 的 zed → 換到 old、球員 zed：${JSON.stringify(st)}`);
  // 鍵盤：所有場次連結 Enter → 首頁；首頁的列和展開區同一份
  await link.focus();await page.keyboard.press('Enter');await page.waitForFunction(()=>!$('home').hidden);
  const home=await page.evaluate(()=>[...document.querySelectorAll('#home .who .card')].flatMap(c=>[...c.querySelectorAll('.sess a')].map(a=>c.querySelector('h2').textContent.trim()+'|'+a.getAttribute('href')+'|'+a.textContent.replace(/\s+/g,' ').trim())));
  check(JSON.stringify(home)===JSON.stringify(same),`${t}：首頁的列和展開區同一份：\n${JSON.stringify(home)}\n${JSON.stringify(same)}`);
  check(await page.evaluate(()=>location.hash==='#home'),`${t}：所有場次 → #home`);
  // 首頁點回去：球員照舊帶過去
  await page.locator('#home .who .card',{has:page.locator('h2',{hasText:/^amy$/})}).locator('.sess a[href="#dold"]').click();await page.waitForFunction(()=>DAY==='old'&&S&&$('home').hidden);
  st=await state(page);check(st.pfilter==='amy'&&st.pressed[0]?.startsWith('amy')&&st.main&&!st.home,`${t}：首頁點 amy 的 old → 球員 amy：${JSON.stringify(st)}`);
  check(!errors.length,`${t} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

async function real(browser,engine,label,opts){
 const tag=`${engine.name()} ${label}`;
 await sect(tag,async()=>{
  const {page,context,errors}=await open(browser,opts);
  await page.waitForFunction(()=>typeof S!=='undefined'&&S);
  const info=await page.evaluate(()=>({keys:DAY_KEYS,days:DAY_KEYS.map(k=>({id:k,date:isoDate(DAYS[k]),n:DAYS[k].data.length,players:DAYS[k].players,cnt:Object.fromEntries(DAYS[k].players.map(p=>[p,DAYS[k].data.filter(s=>who(s)===p).length]))}))}));
  const dated=info.days.filter(d=>d.date),best=dated.length?dated.filter(d=>d.date===dated.map(x=>x.date).sort().at(-1)).sort((a,b)=>b.n-a.n||info.keys.indexOf(b.id)-info.keys.indexOf(a.id))[0]:info.days.at(-1);
  const st=await state(page);
  check(st.day===best.id&&st.hash==='#d'+encodeURIComponent(best.id)&&st.hist===2,`${tag} 沒 hash 要進最近一場 ${best.id}：${JSON.stringify(st)}`);
  const top=best.players.length>1?best.players.reduce((a,p)=>best.cnt[p]>best.cnt[a]?p:a):'ALL';
  check(st.pfilter===top,`${tag} 預設球員 ${top}：${st.pfilter}`);
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`real-${opts.mobile?'phone':'desk'}-${opts.scheme||'light'}-entry.png`)});}
  await secBtn(page).click();
  const rows=await page.evaluate(()=>[...document.querySelectorAll('#secDaysBody .sess a')].map(a=>a.getAttribute('href')));
  const want=info.days.reduce((n,d)=>n+d.players.length,0);
  check(rows.length===want&&info.keys.every(k=>rows.includes('#d'+encodeURIComponent(k))),`${tag} 展開區每位球員每場一列（${want}）：${rows.length}`);
  check(await page.evaluate(()=>!document.querySelector('#days, .days'))&&(await page.locator('#secDaysBody a.all-link').count())===1,`${tag} 沒有日期按鈕列、有「所有場次」`);
  await noOverflow(page,`${tag} 展開區無水平溢出`);
  if(process.env.SITE_RESULTS&&engine.name()==='chromium'){await page.locator('#secDaysBody').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.SITE_RESULTS,`real-${opts.mobile?'phone':'desk'}-${opts.scheme||'light'}-days.png`)});}
  await page.locator('#secDaysBody a.all-link').click();await page.waitForFunction(()=>!$('home').hidden);
  check(await page.evaluate(()=>document.querySelectorAll('#home .sess a').length)===want,`${tag} 首頁列數同展開區 ${want}`);
  for(const k of info.keys){
   await page.evaluate(k=>{location.hash='#d'+encodeURIComponent(k);},k);await page.waitForFunction(k=>DAY===k&&S&&$('home').hidden,k);
   const s2=await state(page);check(s2.main&&!s2.home,`${tag} 舊網址 #d${k} 照舊`);
  }
  for(const h of ['#home','#bogus']){await page.evaluate(h=>{location.hash=h;},h);await page.waitForFunction(()=>!$('home').hidden);}
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
  await context.close();
 });
}

const VIEWS=[['desktop',{}],['desktop-dark',{scheme:'dark'}],['phone',{viewport:{width:390,height:844},mobile:true}],['phone-dark',{viewport:{width:390,height:844},mobile:true,scheme:'dark'}]];
try{
 for(const engine of [chromium,webkit].filter(e=>!process.env.SITE_ENGINE||e.name()===process.env.SITE_ENGINE)){
  const browser=await engine.launch();
  try{for(const [label,opts] of VIEWS){if(REAL)await real(browser,engine,label,opts);else await synthetic(browser,engine,label,opts);}}
  finally{await browser.close();}
 }
}finally{await f.close();}
if(failures.length){console.error(failures.join('\n'));console.error(`site_latest_entry：${failures.length} 條失敗`);process.exit(1);}
console.log(`site_latest_entry ok（${REAL?'真實副本':'合成'}）`);
