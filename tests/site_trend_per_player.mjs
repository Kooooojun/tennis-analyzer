// #152：跨場比較表依球員分開。事前預測與失敗方式：testset/results/trend-per-player/pred.md。
// 合成五場（不讀任何使用者資料）：me 單獨（s1、s4，其中 s1 沒有 player 欄＝舊場次）、me＋pal（s2）、pal 單獨（s3）、solo 單獨（s5）。
// SITE_REF=origin/main 預期失敗（main 把同一場所有球員的拍混成一欄）。
// SITE_E2E_URL＝真實副本模式：不用合成場次，每張表每一欄的「拍數（自拋／對打）」要等於該球員在那場 data.js 的實際拍數；
//   SITE_RESULTS＝另存每場一張比較表截圖（私人，不進 git）。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf 排隊。
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};

// ---- 合成場次：每組一組固定值，同組內值相同（膝蓋用 118–122 的小起伏處理 s2 的 me 自拋），所以中位數可手算 ----
const mk=(player,kind,drill,n,knee,h,extra={})=>Array.from({length:n},(_,i)=>({kind,drill,player,knee:typeof knee==='function'?knee(i):knee,contact_h:h,...extra}));
const SESSIONS=[
 {id:'s1',date:'2026-01-01',camera:'機位1',strokes:[...mk(undefined,'FH','feed',5,100,.30),...mk(undefined,'FH','rally',6,110,.40)]},  // 舊場次：沒有 player 欄
 {id:'s2',date:'2026-01-02',camera:'機位2',strokes:[...mk('pal','FH','rally',5,170,.90),  // pal 的拍排在前面，少於 me：不排序的話 pal 會先出現
                                                      ...mk('me','FH','feed',5,i=>[118,120,122,119,121][i],.30),...mk('me','FH','rally',5,130,.40)]},
 {id:'s3',date:'2026-01-03',camera:'機位3',strokes:[...mk('pal','FH','feed',5,150,.20),...mk('pal','FH','rally',5,160,.25)]},
 {id:'s4',date:'2026-01-04',camera:'機位4',strokes:[...mk(null,'FH','feed',7,140,.35),...mk(null,'FH','rally',5,150,.45)]},
 {id:'s5',date:'2026-01-05',camera:'機位5',strokes:[...mk('solo','FH','rally',3,190,.60)]},
];
const IDS=SESSIONS.map(s=>s.id);
const clip=(sec=3)=>({n:sec*60,size:[640,360],prep:.5,open_min:30,vis:1,contact:90,video:'synthetic'});
const sessionJson=s=>({id:s.id,label:s.id,date:s.date,camera:s.camera,sub:'合成資料',showOpen:true,findings:[],presets:[],
 players:[...new Set(s.strokes.map(x=>x.player||'me'))],
 strokes:s.strokes.map((x,id)=>({id,src:`sessions/synthetic/clips/${id}.mp4`,clock:`0:${String(id).padStart(2,'0')}`,...clip(),...x}))});
const poseJs=(day,id)=>`POSE(${JSON.stringify(day)},${id},${JSON.stringify({frames:Array.from({length:180},()=>Array.from({length:17},(_,i)=>[.3+(i%3)*.1,.2+i*.025,.99]))})});`;

// 期望（手算）。每張表：[標題, 欄＝場次 id, 鏡頭列, 自拋膝, 對打膝, 差距, 自拋手腕高, 對打手腕高, 拍數]
const dash='–';
const EXPECT={
 me:{cols:['s1','s2','s4'],cam:['機位1','機位2','機位4'],feedKnee:['2D 100°','2D 120°','2D 140°'],rallyKnee:['2D 110°','2D 130°','2D 150°'],gap:['2D -10°','2D -10°','2D -10°'],
     feedH:['30','30','35'],rallyH:['40','40','45'],count:['5 / 6','5 / 5','7 / 5']},
 pal:{cols:['s2','s3'],cam:['機位2','機位3'],feedKnee:[dash,'2D 150°'],rallyKnee:['2D 170°','2D 160°'],gap:[dash,'2D -10°'],
     feedH:[dash,'20'],rallyH:['90','25'],count:['0 / 5','5 / 5']},
 solo:{cols:['s5'],cam:['機位5'],feedKnee:[dash],rallyKnee:['2D 190°'],gap:[dash],feedH:[dash],rallyH:['60'],count:['0 / 3']},
};
const ROWS={feedKnee:'自拋正拍・準備時膝蓋',rallyKnee:'對打正拍・準備時膝蓋',gap:'膝蓋差距（自拋 − 對打）',feedH:'自拋正拍・擊球時手腕高度（2D）',rallyH:'對打正拍・擊球時手腕高度（2D）',count:'拍數（自拋 / 對打）',cam:'鏡頭'};

// 讀目前頁面所有比較表：標題（新版每張表有自己的標題；舊版是 #trendTitle）、欄標題、各列
const readTables=page=>page.evaluate(()=>[...document.querySelectorAll('table.trend')].map(t=>({
 title:(t.closest('.trend-block')?.querySelector('.trend-title')||document.getElementById('trendTitle'))?.textContent.trim(),
 heads:[...t.querySelectorAll('thead th')].slice(1).map(x=>x.textContent.trim()),
 rows:Object.fromEntries([...t.querySelectorAll('tbody tr')].map(r=>{const c=[...r.children];return [c[0].textContent.replace(/\s+/g,' ').trim(),c.slice(1).map(x=>x.textContent.replace(/\s+/g,' ').trim())];})),
 cur:[...t.querySelectorAll('thead th')].slice(1).map((_,i)=>t.querySelector(`tbody tr td:nth-child(${i+2})`).classList.contains('cur')),
})));

async function open(browser,{viewport}){
 const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>{errors.push(e.message);if(process.env.DBG)console.log('pageerror',e.message);});
 if(!REAL){
  await page.route(/\/sessions\/manifest\.js/,r=>r.fulfill({contentType:'text/javascript; charset=utf-8',body:`window.SESSION_IDS=${JSON.stringify(IDS)};window.SESSION_VER={};`}));
  await page.route(/\/sessions\/s\d\/data\.js/,r=>{const id=new URL(r.request().url()).pathname.split('/').at(-2);
   r.fulfill({contentType:'text/javascript; charset=utf-8',body:`(window.SESSIONS=window.SESSIONS||[]).push(${JSON.stringify(sessionJson(SESSIONS.find(s=>s.id===id)))});`});});
  await page.route(/\/sessions\/s\d\/pose\/\d+\.js/,r=>{const p=new URL(r.request().url()).pathname.split('/');r.fulfill({contentType:'text/javascript; charset=utf-8',body:poseJs(p.at(-3),path.basename(p.at(-1),'.js'))});});
 }
 await page.goto(f.url);await page.waitForSelector('body.ready');
 return {page,context,errors};
}
const goCharts=async(page,day)=>{await page.evaluate(d=>go(d,'charts'),day);try{await page.waitForFunction(d=>DAY===d&&TAB==="charts"&&document.querySelectorAll("table.trend").length>0,day,{timeout:5000});}catch(e){console.log(await page.evaluate(()=>JSON.stringify({DAY,TAB,hash:location.hash,keys:DAY_KEYS,tables:document.querySelectorAll("table.trend").length})));throw e;}};
const pick=(page,prefix)=>page.evaluate(p=>{const b=[...document.querySelectorAll('#tabs button')].find(x=>x.textContent.startsWith(p));b.click();},prefix);

async function synthetic(page,tag,errors){
 // 1) 多人場次 s2、所有人：兩張表，me（20→10 拍）先；pal 第二張。標題加名字。
 await goCharts(page,'s2');
 let t=await readTables(page);
 check(t.length===2,`${tag} s2 所有人：要 2 張表（me、pal），得到 ${t.length} 張：${JSON.stringify(t.map(x=>x.title))}`);
 if(t.length===2){
  check(t[0].title==='我・3 場比較'&&t[1].title==='pal・2 場比較',`${tag} s2 所有人：標題要「我・3 場比較」「pal・2 場比較」（me 拍數多在前），得到 ${JSON.stringify(t.map(x=>x.title))}`);
  tableMatches(t[0],EXPECT.me,tag+' s2 所有人 我');tableMatches(t[1],EXPECT.pal,tag+' s2 所有人 pal');
  check(JSON.stringify(t[0].cur)===JSON.stringify([false,true,false]),`${tag} s2 我的表：目前這場（s2）那欄要標粗，得到 ${JSON.stringify(t[0].cur)}`);
  check(JSON.stringify(t[1].cur)===JSON.stringify([true,false]),`${tag} s2 pal 的表：目前這場要標粗，得到 ${JSON.stringify(t[1].cur)}`);
 }
 // 2) s2 選 pal（先在每一拍分頁點按鈕，再切到圖表分頁）：只有 pal 的表
 await page.evaluate(()=>go('s2','stroke'));await pick(page,'pal');await goCharts(page,'s2');
 t=await readTables(page);
 check(t.length===1&&t[0].title==='pal・2 場比較',`${tag} s2 選 pal：只要 pal 一張表，得到 ${JSON.stringify(t.map(x=>x.title))}`);
 if(t.length===1)tableMatches(t[0],EXPECT.pal,tag+' s2 選 pal');
 // 3) 已經在圖表分頁時改 pfilter 要立刻重畫（按鈕的 onclick 現場呼叫）
 await page.evaluate(()=>{pfilter='ALL';});
 await page.evaluate(()=>{const b=[...document.querySelectorAll('#tabs button')].find(x=>x.textContent.startsWith('我'));b.click();});
 t=await readTables(page);
 check(t.length===1&&t[0].title==='我・3 場比較',`${tag} 圖表分頁內改選「我」要立刻重畫：得到 ${JSON.stringify(t.map(x=>x.title))}`);
 if(t.length===1)tableMatches(t[0],EXPECT.me,tag+' s2 選我（圖表分頁內）');
 await page.evaluate(()=>{const b=[...document.querySelectorAll('#tabs button')].find(x=>x.textContent==='所有人');b.click();});
 t=await readTables(page);
 check(t.length===2,`${tag} 圖表分頁內改回所有人要重畫成 2 張，得到 ${t.length}`);
 // 4) 單人場次（s1：沒有 player 欄＝舊場次；s4：player null）：1 張，標題沒有名字，欄位只有 me 的場次
 for(const day of ['s1','s4']){
  await goCharts(page,day);t=await readTables(page);
  check(t.length===1&&t[0].title==='3 場比較',`${tag} ${day}（單人場次）：1 張、標題「3 場比較」不加名字，得到 ${JSON.stringify(t.map(x=>x.title))}`);
  if(t.length===1)tableMatches(t[0],EXPECT.me,tag+' '+day);
 }
 // 5) pal 在 s3 單獨出現的場次：標題無名字；但 s3 裡沒有別人，表仍只含 pal 出現的場次（s2、s3）
 await goCharts(page,'s3');t=await readTables(page);
 check(t.length===1&&t[0].title==='2 場比較',`${tag} s3（pal 單獨）：標題「2 場比較」，得到 ${JSON.stringify(t.map(x=>x.title))}`);
 if(t.length===1)tableMatches(t[0],EXPECT.pal,tag+' s3');
 // 6) 只出現一場的球員：標題「這場數字」，不加名字
 await goCharts(page,'s5');t=await readTables(page);
 check(t.length===1&&t[0].title==='這場數字',`${tag} s5（solo，只有一場）：標題「這場數字」，得到 ${JSON.stringify(t.map(x=>x.title))}`);
 if(t.length===1)tableMatches(t[0],EXPECT.solo,tag+' s5');
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：圖表分頁不能水平溢出`);
 // 7) 建議分頁的混合中位數沒被改到（#146）：s2 的 MED 仍是整場混合（對打正拍 me130×5＋pal170×5 → 150）
 await page.evaluate(()=>go('s2','stroke'));await page.waitForFunction(()=>DAY==='s2');
 check(await page.evaluate(()=>{pfilter='ALL';return dayStats(mine()).rally.knee===150;}),`${tag}：s2 所有人的 MED 仍是混合中位數 150（不能動）`);
 check(!errors.length,`${tag}：頁面錯誤 ${errors}`);
}
function tableMatches(tb,ex,tag){
 check(tb.heads.length===ex.cols.length,`${tag}：欄數要 ${ex.cols.length}，得到 ${JSON.stringify(tb.heads)}`);
 for(const [key,lab] of Object.entries(ROWS)){
  check(JSON.stringify(tb.rows[lab])===JSON.stringify(ex[key]),`${tag}：「${lab}」要 ${JSON.stringify(ex[key])}，得到 ${JSON.stringify(tb.rows[lab])}`);
 }
}

// ---- 真實副本模式：期望值由 data.js 另外算（不經過網頁的 who／dayStats） ----
async function real(page,tag,errors,shot){
 const ids=await page.evaluate(()=>DAY_KEYS),raw={};
 for(const id of ids){const t=await (await fetch(`${f.url}sessions/${encodeURIComponent(id)}/data.js`)).text();raw[id]=JSON.parse(t.slice(t.indexOf('push(')+5,t.lastIndexOf(')')));}
 const cnt=(id,p)=>{const a=raw[id].strokes.filter(s=>(s.player||'me')===p);return [a.filter(s=>s.kind==='FH'&&s.drill==='feed').length,a.filter(s=>s.kind==='FH'&&s.drill==='rally').length,a.length];};
 const PN=p=>p==='me'?'我':p;
 for(const day of ids){
  const players=[...new Set(raw[day].strokes.map(s=>s.player||'me'))].sort((a,b)=>cnt(day,b)[2]-cnt(day,a)[2]);
  await goCharts(page,day);
  let t=await readTables(page);
  check(t.length===players.length,`${tag} ${day} 所有人：要 ${players.length} 張表，得到 ${t.length}`);
  for(const [i,p] of players.entries()){
   const cols=ids.filter(k=>cnt(k,p)[2]>0),tb=t[i];if(!tb){continue;}
   const want=cols.map(k=>`${cnt(k,p)[0]} / ${cnt(k,p)[1]}`),multi=players.length>1;
   check(JSON.stringify(tb.rows['拍數（自拋 / 對打）'])===JSON.stringify(want),`${tag} ${day} 第 ${i+1} 張表（排名 ${i+1}）：拍數要 ${JSON.stringify(want)}，得到 ${JSON.stringify(tb.rows['拍數（自拋 / 對打）'])}`);
   const title=(multi?PN(p)+'・':'')+(cols.length>1?`${cols.length} 場比較`:'這場數字');
   check(tb.title===title,`${tag} ${day} 第 ${i+1} 張表：標題要「${multi?'〈球員名〉・':''}${cols.length>1?cols.length+' 場比較':'這場數字'}」，得到「${tb.title}」`);
  }
  if(shot&&process.env.SITE_RESULTS)await page.locator('#trend').screenshot({path:path.join(process.env.SITE_RESULTS,`compare-${day.replace(/[^\w-]/g,'_')}-${shot}.png`)});
  if(players.length>1)for(const p of players){  // 選單一球員：只有那位
   await page.evaluate(d=>go(d,'stroke'),day);await pick(page,PN(p));await goCharts(page,day);
   t=await readTables(page);
   check(t.length===1&&JSON.stringify(t[0].rows['拍數（自拋 / 對打）'])===JSON.stringify(ids.filter(k=>cnt(k,p)[2]>0).map(k=>`${cnt(k,p)[0]} / ${cnt(k,p)[1]}`)),`${tag} ${day} 選 ${players.indexOf(p)+1} 號球員：只有他的表，拍數對得上，得到 ${JSON.stringify(t.map(x=>x.rows['拍數（自拋 / 對打）']))}`);
   await page.evaluate(d=>go(d,'stroke'),day);await pick(page,'所有人');
  }
 }
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：圖表分頁不能水平溢出`);
 check(!errors.length,`${tag}：頁面錯誤 ${errors}`);
}

try{
 if(REAL&&process.env.SITE_RESULTS)fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   for(const [label,viewport] of [['桌機',{width:1280,height:800}],['手機 400px',{width:400,height:800}]]){
    const tag=`${engine.name()} ${label}`,{page,context,errors}=await open(browser,{viewport});
    if(REAL)await real(page,tag,errors,engine.name()==='chromium'&&label==='桌機'?'desktop':'');
    else await synthetic(page,tag,errors);
    await context.close();
   }
  }finally{await browser.close();}
 }
}finally{await f.close?.();}
if(failures.length){console.error(failures.join('\n'));process.exit(1);}
console.log('site_trend_per_player ok'+(REAL?'（真實副本）':''));
