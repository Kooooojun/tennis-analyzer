// A5 後續：快捷鍵只在看得到播放器時有效。播放器（.player）有一部分在畫面內：空白＝播放、←→＝逐格、↑↓＝上／下一拍；
// 完全捲出畫面：空白與方向鍵不攔，交給瀏覽器捲動（空白／↓ 往下、↑ 往上）。N（開筆記）與 Esc 不受影響。
// 事前預測與失敗方式：testset/results/keys-visible/pred.md（私人，不進 git）。
// 合成模式（預設）：合成場次，不讀使用者資料；SITE_REF=origin/main 時跳過（舊網頁整頁都攔）；SITE_FORCE=1 SITE_REF=origin/main 硬跑舊網頁，證明這支測試抓得到（預期紅）。
// SITE_ENGINE=chromium|webkit 只跑一個引擎。SITE_E2E_URL＝真實副本：每一場都跑「看得到有效、離開放行、捲回來又有效」。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
if(process.env.SITE_REF&&!process.env.SITE_FORCE){console.log('skipped site_keys_visible.mjs: it checks new behaviour, SITE_REF runs the old page');process.exit(0);}
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const REAL=process.env.SITE_E2E_URL,f=REAL?{url:REAL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
const sect=async(tag,fn)=>{try{await fn();}catch(e){failures.push(`${tag} 例外：${String(e.message).split('\n')[0]}`);}};
const exe=process.env.SITE_CHROMIUM_EXECUTABLE;

async function open(browser,{viewport,mobile,portrait},hash){
 const context=await browser.newContext({viewport,isMobile:!!mobile,hasTouch:!!mobile}),page=await context.newPage(),errors=[];page.setDefaultTimeout(8000);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/Failed to load resource/.test(m.text()))errors.push('console: '+m.text());});
 if(portrait)await page.route('**/sessions/synthetic/data.js*',async route=>{  // 合成片是橫式；版面（sticky 與否）看 size，改成直式才量得到桌機的 sticky
  const text=await (await route.fetch()).text(),head='window.SESSIONS=[',json=JSON.parse(text.slice(head.length,text.lastIndexOf(']')));
  json.strokes.forEach(x=>{x.size=[360,640];});await route.fulfill({contentType:'text/javascript; charset=utf-8',body:head+JSON.stringify(json)+'];'});
 });
 await page.goto(f.url+hash);await page.waitForSelector('body.ready');await page.waitForFunction(()=>typeof S!=='undefined'&&S);
 // 頁尾多給一大段捲動空間（在 main 外面），讓每個尺寸的播放器都有機會捲到看不到；sticky 的播放器會在 main 結束時被推出去
 await page.evaluate(()=>{const d=document.createElement('div');d.id='keysSpacer';d.style.height='4000px';document.body.append(d);});
 return {page,context,errors};
}
// 同一個定義放在頁內：有一部分在畫面內（bottom>0 且 top<innerHeight）＝看得到
const vis=page=>page.evaluate(()=>{const r=document.querySelector('.player').getBoundingClientRect();return r.bottom>0&&r.top<innerHeight;});
const st=page=>page.evaluate(()=>({id:S.id,cur,want:!!v._want,y:scrollY,vis:(()=>{const r=document.querySelector('.player').getBoundingClientRect();return r.bottom>0&&r.top<innerHeight;})()}));
const toTop=async page=>{await page.evaluate(()=>{scrollTo(0,0);document.activeElement?.blur?.();});await page.waitForFunction(()=>scrollY===0);};
const press=async(page,key)=>{await page.evaluate(()=>document.activeElement?.blur?.());await page.keyboard.press(key);await page.waitForTimeout(250);};
async function firstHiddenY(page){  // 往下掃：第一個讓播放器完全離開畫面的 scrollY；沒有就回 null
 return page.evaluate(()=>{const max=document.documentElement.scrollHeight-innerHeight;for(let y=0;y<=max;y+=20){scrollTo(0,y);const r=document.querySelector('.player').getBoundingClientRect();if(!(r.bottom>0&&r.top<innerHeight))return scrollY;}return null;});
}
const scrollTo_=(page,y)=>page.evaluate(y=>{scrollTo(0,y);document.activeElement?.blur?.();},y).then(()=>page.waitForTimeout(100));

async function scenario(browser,tag,opts,hash,sticky){
 const {page,context,errors}=await open(browser,opts,hash);
 try{
  await toTop(page);
  // ---- 看得到：照舊 ----
  let a=await st(page);check(a.vis,`${tag} 起點播放器要看得到`);
  await press(page,' ');let b=await st(page);check(b.want,`${tag} 看得到：空白要播放`);
  await press(page,' ');b=await st(page);check(!b.want,`${tag} 看得到：再按空白要停`);
  await press(page,'ArrowDown');b=await st(page);check(b.id!==a.id,`${tag} 看得到：↓ 要換拍（${a.id}→${b.id}）`);
  await press(page,'ArrowUp');b=await st(page);check(b.id===a.id,`${tag} 看得到：↑ 要換回（${b.id}）`);
  await press(page,'ArrowRight');b=await st(page);check(b.cur!==a.cur,`${tag} 看得到：→ 要逐格（${a.cur}→${b.cur}）`);
  await press(page,'ArrowLeft');b=await st(page);check(b.cur===a.cur,`${tag} 看得到：← 要逐格退回（${b.cur}）`);
  // ---- 例外：輸入框裡的空白不播放 ----
  await page.evaluate(()=>{setOpen($('secNotes'),true);$('noteIn').focus();});await page.keyboard.press(' ');await page.waitForTimeout(150);
  check(!(await st(page)).want,`${tag} 輸入框裡的空白不能播放`);
  await page.evaluate(()=>{$('noteIn').value='';$('noteIn').blur();setOpen($('secNotes'),false);});
  await toTop(page);

  // ---- 捲出畫面：放行 ----
  // ---- sticky 的播放器：捲了一段還黏在上面，快捷鍵照舊（看得到就有效）；static 的不查 ----
  const pos=await page.evaluate(()=>getComputedStyle(document.querySelector('.player')).position);
  if(sticky!==null)check((pos==='sticky')===sticky,`${tag} 播放器 position 預期${sticky?'sticky':'非 sticky'}，實際 ${pos}`);
  if(pos==='sticky'){
   const ay=await page.evaluate(()=>document.querySelector('.player').getBoundingClientRect().top+scrollY);  // 播放器原本在頁面上的位置（上面有主軸卡）；捲過它 100px 才會黏住
   await scrollTo_(page,ay+100);const m0=await st(page);
   check(m0.vis&&await page.evaluate(()=>document.querySelector('.player').getBoundingClientRect().top<30),`${tag} sticky：捲過原位 100px 後播放器要還黏在上面`);
   await press(page,' ');const m1=await st(page);check(m1.want,`${tag} sticky：捲了一段，空白仍要播放`);
   await press(page,' ');await toTop(page);
  }
  // ---- 捲出畫面：放行（頁尾有空白，sticky 的播放器會在 main 結束時被推出去） ----
  const y=await firstHiddenY(page);
  check(y!==null,`${tag} 播放器捲到底都還看得到，沒法測放行`);
  if(y!==null){
   await scrollTo_(page,y);
   let c=await st(page);check(!c.vis,`${tag} 前提：播放器要完全離開畫面`);
   let d;for(let i=0;i<3;i++){await press(page,' ');d=await st(page);if(d.y>c.y)break;if(d.want||d.id!==c.id)break;}  // WebKit 的鍵盤捲動動畫偶爾吃掉程式剛捲完的第一下；要查的是頁面沒攔（沒播放、id 不變），所以最多按 3 下

   check(d.y>c.y,`${tag} 離開後空白要讓頁面往下捲（${c.y}→${d.y}）`);
   check(!d.want&&d.id===c.id,`${tag} 離開後空白不能播放或換拍：want=${d.want} id ${c.id}→${d.id}`);
   await scrollTo_(page,y);
   for(let i=0;i<3;i++){await press(page,'ArrowDown');d=await st(page);if(d.y>c.y||d.id!==c.id)break;}
   check(d.y>c.y&&d.id===c.id,`${tag} 離開後 ↓ 要讓頁面往下捲、不換拍：y ${c.y}→${d.y}，id ${c.id}→${d.id}`);
   await scrollTo_(page,y+200);c=await st(page);
   for(let i=0;i<3;i++){await press(page,'ArrowUp');d=await st(page);if(d.y<c.y)break;}  // WebKit 的鍵盤捲動動畫偶爾吃掉程式剛捲完的第一下；頁面沒攔（id 不變）才是要查的，所以最多按 3 下
   check(d.y<c.y&&d.id===c.id,`${tag} 離開後 ↑ 要讓頁面往上捲、不換拍：y ${c.y}→${d.y}，id ${c.id}→${d.id}`);
   await scrollTo_(page,y);c=await st(page);
   for(const k of ['ArrowRight','ArrowLeft']){await press(page,k);d=await st(page);check(d.cur===c.cur&&d.id===c.id&&!d.want,`${tag} 離開後 ${k} 不逐格：cur ${c.cur}→${d.cur}`);}
   // N 不受影響
   await scrollTo_(page,y);await press(page,'n');
   check(await page.evaluate(()=>document.activeElement===$('noteIn')&&isOpen('secNotes')),`${tag} 離開後 N 照樣開筆記並聚焦輸入框`);
   await page.evaluate(()=>{$('noteIn').blur();setOpen($('secNotes'),false);});
   // 邊界：剩一條邊（bottom 在 (0,2]）算看得到；bottom≤0 算看不到
   {
    const set=bottom=>page.evaluate(bottom=>{const r=document.querySelector('.player').getBoundingClientRect();scrollTo(0,scrollY+r.bottom-bottom);document.activeElement?.blur?.();return document.querySelector('.player').getBoundingClientRect().bottom;},bottom);
    let bt=await set(1);const e0=await st(page);await press(page,'ArrowDown');const e1=await st(page);
    check(bt>0&&bt<=2&&e0.vis,`${tag} 邊界前提：bottom=${bt} 要在 (0,2]`);check(e1.id!==e0.id,`${tag} 只剩一條邊（bottom=${bt}）仍算看得到：↓ 要換拍`);
    await press(page,'ArrowUp');
    bt=await set(0);for(let i=0;i<3&&bt>0;i++)bt=await page.evaluate(()=>{scrollBy(0,1);return document.querySelector('.player').getBoundingClientRect().bottom;});const g0=await st(page);await press(page,'ArrowDown');const g1=await st(page);
    check(bt<=0&&!g0.vis,`${tag} 邊界前提：bottom=${bt} 要 ≤ 0`);check(g1.id===g0.id,`${tag} 剛好離開（bottom=${bt}）：↓ 不換拍`);
   }
   // 按住 ↓：每一下都重新量；離開前每下換拍，離開後每下只捲
   {
    await toTop(page);await page.evaluate(()=>{const r=document.querySelector('.player').getBoundingClientRect();scrollTo(0,scrollY+r.bottom-60);document.activeElement?.blur?.();});
    for(let i=0;i<6;i++){
     const before=await st(page);await page.keyboard.press('ArrowDown');await page.waitForTimeout(250);const after=await st(page);
     if(before.vis)check(after.id!==before.id,`${tag} 連按 ↓ 第 ${i+1} 下：播放器看得到（bottom 剩幾 px），要換拍`);
     else check(after.id===before.id&&after.y>=before.y,`${tag} 連按 ↓ 第 ${i+1} 下：播放器已離開，不換拍、頁面不能往回：id ${before.id}→${after.id}，y ${before.y}→${after.y}`);
    }
   }
   // ---- 捲回來：又有效 ----
   await toTop(page);const r0=await st(page);check(r0.vis,`${tag} 捲回頂端播放器要看得到`);
   await press(page,' ');let r1=await st(page);check(r1.want,`${tag} 捲回來：空白要播放`);
   await press(page,' ');
   await press(page,'ArrowDown');r1=await st(page);check(r1.id!==r0.id,`${tag} 捲回來：↓ 要換拍`);
  }
  check(!errors.length,`${tag} 頁面錯誤 ${errors}`);
 }finally{await context.close();}
}

const VIEWS=[  // [名稱, 選項, 預期 sticky]；portrait＝直式片（版面看 size）
 ['desktop 1280×800 直式片',{viewport:{width:1280,height:800},portrait:true},false],      // 高度 ≤ 820：不 sticky
 ['desktop 1280×1000 直式片',{viewport:{width:1280,height:1000},portrait:true},true],     // 高度夠：sticky
 ['desktop 1280×1000 橫式片',{viewport:{width:1280,height:1000}},false],                  // .wide：一律不 sticky
 ['phone 390×844 直式片',{viewport:{width:390,height:844},mobile:true,portrait:true},true], // 直拿：黏在上面
 ['phone 390×844 橫式片',{viewport:{width:390,height:844},mobile:true},true],
 ['phone landscape 844×390',{viewport:{width:844,height:390},mobile:true},false],         // 橫拿：不 sticky
];
try{
 for(const engine of [chromium,webkit]){
  if(process.env.SITE_ENGINE&&process.env.SITE_ENGINE!==engine.name())continue;
  const browser=await engine.launch(engine===chromium&&exe?{executablePath:exe}:{});
  try{
   for(const [label,opts,sticky] of VIEWS){
    if(!REAL)await sect(`${engine.name()} ${label}`,()=>scenario(browser,`${engine.name()} ${label}`,opts,'#dsynthetic',sticky));
    else{
     const ids=await (async()=>{const {page,context}=await open(browser,opts,'');try{return await page.evaluate(()=>window.SESSION_IDS);}finally{await context.close();}})();
     for(const id of ids)await sect(`${engine.name()} ${label} ${id}`,()=>scenario(browser,`${engine.name()} ${label} 場次 ${id}`,opts,`#d${id}`,null));
    }
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
if(failures.length){console.error(failures.join('\n'));console.error(`site_keys_visible：${failures.length} 條失敗`);process.exit(1);}
console.log(`site_keys_visible ok（${REAL?'真實副本':'合成'}）`);
