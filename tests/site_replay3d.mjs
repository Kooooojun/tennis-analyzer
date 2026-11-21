// #145：單拍 3D 回放、膝蓋調整示意、角度弧線。失敗方式清單見 testset/results/replay3d/pred.md。
// 預設用合成場次（site_i93_fixture，骨架由本檔產生，不讀使用者資料）；SITE_E2E_URL 指向私人場次副本時改驗真實資料。
// PLAYWRIGHT_MODULE 指向本機 playwright-core；SITE_RESULTS 有設時存截圖。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const real=!!process.env.SITE_E2E_URL;
const f=real?{url:process.env.SITE_E2E_URL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};

// 合成骨架：大腿 0.45 m、小腿 0.42 m，兩膝角隨時間變化；2D＝把 world 正投影到 640×360 的畫面。
// 10、11：自拋正拍、膝很直 → 有示意；13：同樣直但 knee_warn → 沒有示意、弧線寫「看不準」；14：和對打差不到 10° → 沒有；16：沒有 world。
const SYNTH=()=>{
 const L1=.45,L2=.42,deg=Math.PI/180;
 const p10=a=>{const s=a.filter(Number.isFinite).sort((x,y)=>x-y),i=(s.length-1)*.1,k=Math.floor(i);return s[k]+(s[Math.min(k+1,s.length-1)]-s[k])*(i-k);};
 const ang=(A,B,C)=>{const u=A.map((x,i)=>x-B[i]),w=C.map((x,i)=>x-B[i]);return Math.acos(Math.max(-1,Math.min(1,u.reduce((s,x,i)=>s+x*w[i],0)/Math.hypot(...u)/Math.hypot(...w))))/deg;};
 const body=(f,base,id,amp=12)=>{
  const th=[base+amp*Math.sin(f/17+id),base+6+amp*Math.cos(f/23+id)],W=Array(17);
  W[0]=[0,-.68,-.05];W[1]=[-.18,-.5,0];W[2]=[.18,-.5,0];W[3]=[-.25,-.25,-.05];W[4]=[.27,-.3,-.1];W[5]=[-.28,-.02,-.12];W[6]=[.35,-.1,-.25];
  for(const [side,hx] of [[0,-.12],[1,.12]]){
   const t=Math.min(179,th[side])*deg,D=Math.sqrt(L1*L1+L2*L2-2*L1*L2*Math.cos(t)),a=(L1*L1-L2*L2+D*D)/(2*D),h=Math.sqrt(Math.max(0,L1*L1-a*a));
   W[7+side]=[hx,0,0];W[9+side]=[hx-.6*h,a,-.8*h];W[11+side]=[hx,D,0];W[13+side]=[hx,D+.03,.06];W[15+side]=[hx,D+.04,-.15];
  }
  return W;
 };
 window.POSE=()=>{};  // a late fixture pose file must not overwrite the synthetic skeletons
 const special={10:150,11:152,13:150,14:114};
 ALL.forEach(s=>{
  s.kind=s.id%3===0?'BH':'FH';s.drill=s.id in special||s.id===16?'feed':'rally';
  const base=s.kind==='BH'?150:special[s.id]??112+s.id%5,amp=s.drill==='rally'?2:12;  // steady rally knees: a clear median
  s.world=s.id===16?null:Array.from({length:s.n},(_,f)=>body(f,base,s.id,amp));
  s.frames=Array.from({length:s.n},(_,f)=>body(f,base,s.id,amp).map(([x,y])=>[(320+x*200)/640,(180+y*200)/360,.99]));
  if(s.id===11)s.frames.forEach(fr=>{fr[10][0]=fr[12][0]=fr[8][0];});  // 2D right leg dead straight (a pose clamped at the frame edge): no bend direction
  const k3=s.world?p10(Array.from({length:43},(_,j)=>{const w=s.world[s.contact-48+j];return Math.min(ang(w[7],w[9],w[11]),ang(w[8],w[10],w[12]));})):null;
  s.knee3d=k3==null?null:Math.round(k3*10)/10;s.knee2d=k3==null?140:s.knee3d+1;s.knee=s.knee3d??s.knee2d;
  s.knee_warn=s.id===13;s.knee_warn_why=s.id===13?'gap':null;s.lean=s.id===11?null:8.4;
 });
 SER.clear();PLAN.clear();MED=dayStats(mine());drawList();drawChecks();load(S.id,false);
};

// 測試自己的條件與幾何（不呼叫頁面的 demoTarget／kneeIK），在頁面裡跑以便讀 DAYS
const EXPECT=()=>{
 const med=a=>{const s=a.filter(x=>x!=null&&isFinite(x)).sort((x,y)=>x-y),m=s.length>>1;return !s.length?null:s.length%2?s[m]:(s[m-1]+s[m])/2;};
 const out={};
 for(const s of ALL){
  const g=ALL.filter(x=>who(x)===who(s)&&x.kind==='FH'&&x.drill==='rally'),ok=g.filter(x=>!x.knee_warn);
  const three=ok.filter(x=>x.knee3d!=null).length>ok.length/2,val=x=>three?x.knee3d:x.knee3d!=null?x.knee2d:x.knee;
  const m=med(ok.filter(x=>three||x.knee2d_ok!==false).map(val)),k=s.knee_warn||!three&&s.knee2d_ok===false?null:val(s);
  out[s.id]=s.kind==='FH'&&!s.knee_warn&&m!=null&&k!=null&&k-m>=10?m:null;
 }
 return out;
};

// 一拍的幾何不變式：腳不動、骨長不變、示意膝角到目標、權重平順
const GEOM=()=>{
 const p=demoPlan(S),r={target:p?.target,ok:!!p};if(!p)return r;
 const dist=(P,a,b)=>Math.hypot(...P[K[a]].map((x,i)=>x-P[K[b]][i]));
 const deg=Math.PI/180,ang=(P,a,b,c)=>{const u=P[K[a]].map((x,i)=>x-P[K[b]][i]),w=P[K[c]].map((x,i)=>x-P[K[b]][i]);return Math.acos(Math.max(-1,Math.min(1,u.reduce((s,x,i)=>s+x*w[i],0)/Math.hypot(...u)/Math.hypot(...w))))/deg;};
 const p10=a=>{const s=a.filter(Number.isFinite).sort((x,y)=>x-y),i=(s.length-1)*.1,k=Math.floor(i);return s[k]+(s[Math.min(k+1,s.length-1)]-s[k])*(i-k);};
 const three=p.src==='knee3d',get=f=>three?S.world?.[f]:S.frames[f]&&S.frames[f].map(q=>[q[0]*(S.size||[540,960])[0],q[1]*(S.size||[540,960])[1],0]);
 let foot=0,bone=0,bone2=0,foot2=0,jump=0,moved=0;const win=[];
 for(let f=0;f<S.frames.length;f++){
  const w=demoWeight(f,S.contact),pw=f?demoWeight(f-1,S.contact):w;jump=Math.max(jump,Math.abs(w-pw));
  const P=S.world?.[f],Q=P&&demoPts(S,f,true);
  if(P&&Q){
   for(const i of [27,28,29,30,31,32])foot=Math.max(foot,Math.hypot(...P[K[i]].map((x,j)=>x-Q[K[i]][j])));
   for(const [a,b] of [[23,25],[25,27],[24,26],[26,28]])bone=Math.max(bone,Math.abs(dist(Q,a,b)/dist(P,a,b)-1));
   moved=Math.max(moved,Math.abs(Q[K[23]][1]-P[K[23]][1]));
  }
  const fr=S.frames[f],d2=fr&&demo2(S,f);
  if(d2){
   const px=a=>a.map(q=>[q[0]*(S.size||[540,960])[0],q[1]*(S.size||[540,960])[1],0]),A=px(fr),B=px(d2);
   for(const i of [27,28,29,30,31,32])foot2=Math.max(foot2,Math.hypot(...A[K[i]].map((x,j)=>x-B[K[i]][j])));
   for(const [a,b] of [[23,25],[25,27],[24,26],[26,28]])bone2=Math.max(bone2,Math.abs(dist(B,a,b)/dist(A,a,b)-1));
  }
  if(f>=S.contact-48&&f<=S.contact-6){
   const Q2=three?demoPts(S,f,true):(d=>d&&d.map(q=>[q[0]*(S.size||[540,960])[0],q[1]*(S.size||[540,960])[1],0]))(demo2(S,f));
   if(Q2)win.push(Math.min(ang(Q2,23,25,27),ang(Q2,24,26,28)));
   if(Math.abs(demoWeight(f,S.contact)-1)>1e-9)r.windowWeight=false;
  }
 }
 const P0=get(S.contact-20),same=P0&&kneeIK(P0,0).every((q,i)=>q.every((x,j)=>Math.abs(x-P0[i][j])<1e-9));
 const orig=[];for(let f=S.contact-48;f<=S.contact-6;f++){const P=get(f);if(P)orig.push(Math.min(ang(P,23,25,27),ang(P,24,26,28)));}
 return {...r,foot,foot2,bone,bone2,jump,moved,demoKnee:p10(win),origKnee:p10(orig),card:three?S.knee3d:S.knee,same,windowWeight:r.windowWeight!==false};
};

const players=async(page)=>page.evaluate(()=>{for(const vid of document.querySelectorAll('video'))vid.muted=true;});
const playState=page=>page.evaluate(()=>({text:$('play').textContent,cmp:$('cmpPlay').textContent,want:!!v._want,wantA:!!vA._want,wantB:!!vB._want}));

try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   for(const mobile of [false,true]){
    const context=await browser.newContext(mobile?{viewport:{width:400,height:860},isMobile:true,hasTouch:true,deviceScaleFactor:2}:{viewport:{width:1280,height:800}});
    const page=await context.newPage(),tag=`${engine.name()} ${mobile?'400px':'桌機'}`,errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(f.url);await page.waitForSelector('body.ready');await players(page);
    const days=real?await page.evaluate(()=>DAY_KEYS):[await page.evaluate(()=>DAY_KEYS[0])];
    for(const [di,day] of days.entries()){
     await page.evaluate(day=>go(day,'stroke'),day);
     await page.waitForFunction(()=>S?.frames?.length&&v.readyState>=2&&!v._fetching);
     if(!real)await page.evaluate(SYNTH);
     // 面板預設關著：沒有面板、列表沒有示意記號
     check(await page.evaluate(()=>!$('r3d')||$('r3d').hidden),`${tag}：面板預設要關著`);
     check(!(await page.locator('#strokes').textContent()).includes('示意'),`${tag}：關著時列表不能有示意記號`);
     // 開關面板不動播放狀態（播放中、暫停各一次）
     for(const playing of [true,false]){
      if(playing){await page.evaluate(()=>toggle());await page.waitForFunction(()=>v._want);}
      const before=await playState(page);
      await page.locator('#r3dBtn').click();const opened=await playState(page);
      await page.locator('#r3dBtn').click();const closed=await playState(page);
      check(JSON.stringify(before)===JSON.stringify(opened)&&JSON.stringify(before)===JSON.stringify(closed),`${tag}：開關面板改了播放狀態 ${JSON.stringify([before,opened,closed])}`);
      if(playing)await page.evaluate(()=>{if(v._want)toggle();});
     }
     await page.locator('#r3dBtn').click();
     check(await page.evaluate(()=>R3D.on&&!$('r3d').hidden&&$('r3dBtn').getAttribute('aria-pressed')==='true'),`${tag}：按鈕要打開面板`);
     check(await page.evaluate(()=>!!$('r3dCv').getAttribute('aria-label')),`${tag}：canvas 要有 aria-label`);
     const caveats=await page.locator('#r3d').textContent();
     check(caveats.includes('單鏡頭估計的 3D，轉到影片沒拍到的角度會更不準。'),`${tag}：缺 3D 精度說明`);
     check(caveats.includes('藍色是照你自己對打時的膝蓋彎曲畫的示意，只調整膝蓋，不是驗證過的正確動作。'),`${tag}：缺示意說明`);

     // 示意只出現在符合條件的拍；目標＝建議分頁的數字
     const want=await page.evaluate(EXPECT),got=await page.evaluate(()=>Object.fromEntries(ALL.map(s=>[s.id,demoTarget(s)?.target??null])));
     check(JSON.stringify(want)===JSON.stringify(got),`${tag}：示意條件不符 ${JSON.stringify({want,got})}`);
     const eligible=Object.keys(want).filter(k=>want[k]!=null).map(Number);
     if(!real)check(JSON.stringify(eligible)==='[10,11]',`${tag}：合成場次應只有 10、11 有示意 ${eligible}`);
     const marked=await page.locator('#strokes button:has(.r3d-mark)').evaluateAll(bs=>bs.map(b=>+b.dataset.id));
     check(JSON.stringify(marked)===JSON.stringify(eligible),`${tag}：列表記號 ${marked} ≠ ${eligible}`);
     const advice=await page.evaluate(()=>{const out=[];for(const p of DAYS[DAY].players){pfilter=p;MED=dayStats(mine());drawChecks();const m=/約 (3D估|2D) (\d+)°/.exec($('checkFH').textContent);out.push({p,shown:m?+m[2]:null,target:ALL.filter(s=>who(s)===p).map(s=>demoTarget(s)?.target).find(x=>x!=null)??null});}pfilter='ALL';MED=dayStats(mine());drawChecks();return out;});
     for(const a of advice)if(a.target!=null)check(Math.round(a.target)===a.shown,`${tag}：示意目標 ${a.target} 和建議分頁 ${a.shown} 不同`);
     if(di===0)console.log(`${tag}：${day} 示意拍 ${eligible.length}（${eligible.join('、')}）`);

     // 每一拍有示意的拍：幾何不變式
     for(const id of eligible){
      await page.evaluate(id=>load(id,false),id);await page.waitForFunction(()=>S?.frames?.length);
      const r=await page.evaluate(GEOM);
      if(!r.ok){check(false,`${tag}：#${id} 有條件卻沒有示意（缺骨架？）`);continue;}
      check(r.foot===0&&r.foot2===0,`${tag}：#${id} 腳動了 ${r.foot} ${r.foot2}`);
      check(r.bone<.01&&r.bone2<.01,`${tag}：#${id} 骨長變化 ${r.bone} ${r.bone2}`);
      check(Math.abs(r.demoKnee-r.target)<=2,`${tag}：#${id} 示意膝角 ${r.demoKnee} 沒到目標 ${r.target}`);
      check(Math.abs(r.origKnee-r.card)<1,`${tag}：#${id} 重算原始膝角 ${r.origKnee} ≠ 卡片 ${r.card}`);
      check(r.jump<=.05+1e-9&&r.windowWeight,`${tag}：#${id} 權重跳動 ${r.jump}`);
      check(r.same,`${tag}：#${id} 權重 0 時示意要等於原始`);
      check(r.moved>0,`${tag}：#${id} 示意沒有往下移`);
      if(real&&di===0&&id===eligible[0])console.log(`${tag}：#${id} 卡片 ${r.card}° 重算 ${r.origKnee.toFixed(1)}° 示意 ${r.demoKnee.toFixed(1)}° 目標 ${r.target}° 骨長 ${(r.bone*100).toFixed(4)}% 權重最大步 ${r.jump.toFixed(3)}`);
     }
     // 不符合的拍：完全不畫示意
     const others=await page.evaluate(()=>ALL.filter(s=>!demoTarget(s)).slice(0,6).map(s=>s.id));
     for(const id of others){
      await page.evaluate(id=>load(id,false),id);await page.waitForFunction(()=>S?.frames?.length);
      check(await page.evaluate(()=>{goto(S.contact-20);return !R3D.demoDrawn&&!demoPlan(S)&&demo2(S,S.contact-20)==null;}),`${tag}：#${id} 不符合卻畫了示意`);
     }

     // 同步：播放中、seek 後、逐格，3D 的格＝2D 疊圖的格
     const syncId=eligible[0]??others[0];
     await page.evaluate(id=>load(id,false),syncId);await page.waitForFunction(()=>S?.frames?.length&&v.readyState>=2&&!v._fetching);
     await page.evaluate(()=>goto(S.contact-60));await page.evaluate(()=>toggle());await page.waitForFunction(()=>!v.paused);
     const run=await page.evaluate(()=>new Promise(done=>{let n=0,bad=0;const first=R3D.f;const loop=()=>{n++;if(R3D.f!==cur||+$('r3dCv').dataset.frame!==cur)bad++;if(n<90)requestAnimationFrame(loop);else done({bad,adv:R3D.f-first});};requestAnimationFrame(loop);}));
     await page.evaluate(()=>{if(v._want)toggle();});
     check(run.bad===0&&run.adv>3,`${tag}：播放中 3D 與 2D 不同格 ${JSON.stringify(run)}`);
     for(const act of ['seek','next','prev','key']){
      if(act==='seek')await page.evaluate(()=>{seek.value=S.contact-30;seek.dispatchEvent(new Event('input'));});
      else if(act==='key')await page.keyboard.press('ArrowRight');
      else await page.locator('#'+act).click();
      await page.waitForTimeout(80);
      check(await page.evaluate(()=>R3D.f===cur&&+seek.value===cur),`${tag}：${act} 後 3D 與 2D 不同格`);
     }
     check(await page.evaluate(()=>{const c=$('r3dCv'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n>500;}),`${tag}：3D canvas 沒畫東西`);
     if(eligible.length){
      check(await page.evaluate(()=>{goto(S.contact-20);return R3D.demoDrawn;}),`${tag}：示意拍要畫示意`);
      await page.locator('#r3dDemo').click();
      check(await page.evaluate(()=>!R3D.demoDrawn&&$('r3dDemo').getAttribute('aria-pressed')==='false'),`${tag}：示意開關要能隱藏示意`);
      await page.locator('#r3dDemo').click();
     }

     // 弧線：停在膝蓋最彎那格，數字＝卡片；閘門拍只寫看不準；擊球格前傾
     await page.locator('#r3dKnee').click();
     const arc=await page.evaluate(()=>({cur,kf:kneeFrameOf(S),paused:!v._want,labels:R3D.labels,card:$('mKnee').textContent,knee:S.knee}));
     check(arc.cur===arc.kf&&arc.paused,`${tag}：停在膝蓋最彎跳錯格 ${JSON.stringify(arc)}`);
     check(arc.labels.some(t=>t.includes(Math.round(arc.knee)+'°'))&&arc.card.startsWith(String(Math.round(arc.knee))),`${tag}：弧線數字要等於卡片 ${JSON.stringify(arc)}`);
     // 朋友 skill「網頁檢查」：標註不重疊、留在畫面內、不蓋住關節，指示線連到正確關節（較彎那隻膝／髖中心）
     const MARKS=()=>{const c=$('r3dCv').getBoundingClientRect(),P=S.world[cur],bent=(angle3(P,24,26,28)??180)<=(angle3(P,23,25,27)??180)?26:25;
      const hip=P[K[23]].map((x,i)=>(x+P[K[24]][i])/2),want={knee:R3D.proj(P[K[bent]]),lean:R3D.proj(hip)};
      return R3D.marks.map(m=>{const [x,y,w,h]=m.box,J=want[m.kind];return {text:m.text,inside:x>=0&&y>=0&&x+w<=c.width&&y+h<=c.height,covers:m.joint[0]>=x&&m.joint[0]<=x+w&&m.joint[1]>=y&&m.joint[1]<=y+h,joint:Math.hypot(m.joint[0]-J[0],m.joint[1]-J[1]),line:Math.hypot(m.line[2]-J[0],m.line[3]-J[1])};}).concat(R3D.marks.flatMap((a,i)=>R3D.marks.slice(i+1).map(b=>({overlap:!(a.box[0]+a.box[2]<=b.box[0]||b.box[0]+b.box[2]<=a.box[0]||a.box[1]+a.box[3]<=b.box[1]||b.box[1]+b.box[3]<=a.box[1])}))));};
     const km=await page.evaluate(MARKS);
     check(km.length>0&&km.every(m=>m.overlap===false||m.inside&&!m.covers&&m.joint<.5&&m.line<.5),`${tag}：膝角標註位置 ${JSON.stringify(km)}`);
     const warnId=await page.evaluate(()=>ALL.find(s=>s.knee_warn&&s.knee!=null&&s.world!==null)?.id);
     if(warnId!=null){
      await page.evaluate(id=>load(id,false),warnId);await page.waitForFunction(()=>S?.frames?.length);
      await page.locator('#r3dKnee').click();
      const w=await page.evaluate(()=>R3D.labels);
      check(w.some(t=>t.includes('看不準'))&&!w.some(t=>/膝|\d+°/.test(t)&&!t.includes('前傾')),`${tag}：閘門拍只能寫看不準 ${w}`);
     }
     await page.locator('#r3dHit').click();
     const lean=await page.evaluate(()=>({labels:R3D.labels,lean:S.lean,card:$('mLean').textContent,cur,c:S.contact}));
     check(lean.cur===lean.c&&lean.labels.some(t=>t.includes('前傾')&&(lean.lean==null?t.includes('看不準'):t.includes(lean.lean.toFixed(1)+'°'))),`${tag}：擊球格前傾弧線 ${JSON.stringify(lean)}`);
     check(!(await page.evaluate(()=>R3D.labels.join(''))).includes('肘'),`${tag}：不能畫肘角`);
     const lm=await page.evaluate(MARKS);
     check(lm.length>0&&lm.every(m=>m.overlap===false||m.inside&&!m.covers&&m.joint<.5&&m.line<.5),`${tag}：前傾標註位置 ${JSON.stringify(lm)}`);
     // 方法說明：偵測與插值影格數、拍攝角度限制、示意調整了什麼
     const method=await page.evaluate(()=>({text:$('r3dMethod').textContent,n:S.frames.length,ok:S.frames.filter(Boolean).length,w:S.world?S.world.filter(Boolean).length:0}));
     check(method.text.includes(`這拍 ${method.n} 格`)&&method.text.includes(`骨架 ${method.ok} 格`)&&method.text.includes(`3D ${method.w} 格`)&&method.text.includes('插值 0 格')&&/正前、正後方/.test(method.text),`${tag}：方法說明 ${method.text}`);
     // 鍵盤：聚焦 canvas 後方向鍵旋轉、不換格；Home 重設
     await page.locator('#r3dCv').focus();const f0=await page.evaluate(()=>cur);
     await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowUp');
     check(await page.evaluate(f0=>R3D.yaw!==0&&R3D.pitch!==0&&cur===f0,f0),`${tag}：鍵盤要能旋轉且不換格`);
     await page.keyboard.press('Home');
     check(await page.evaluate(()=>R3D.yaw===0&&R3D.pitch===0),`${tag}：Home 重設視角`);
     await page.evaluate(()=>$('r3dCv').blur());
     // prefers-reduced-motion：暫停時不會自己動（沒有動畫迴圈）
     await page.emulateMedia({reducedMotion:'reduce'});
     const pix=()=>page.evaluate(()=>{const c=$('r3dCv'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let h=0;for(let i=0;i<d.length;i+=7)h=(h*31+d[i])|0;return [h,cur,R3D.yaw,R3D.pitch].join();});
     const p0=await pix();await page.waitForTimeout(400);
     check(await pix()===p0,`${tag}：減少動態時面板不能自己動`);
     await page.emulateMedia({reducedMotion:null});

     // 拖曳旋轉、重設視角，不動播放狀態；觸控不捲頁
     const ps=await playState(page),box=await page.locator('#r3dCv').boundingBox();
     if(mobile){
      check(await page.evaluate(()=>getComputedStyle($('r3dCv')).touchAction==='none'),`${tag}：canvas 要 touch-action:none`);
      const y0=await page.evaluate(()=>scrollY);
      await page.evaluate(({x,y})=>{const c=$('r3dCv'),ev=(t,dx,dy)=>c.dispatchEvent(new PointerEvent(t,{pointerId:7,pointerType:'touch',clientX:x+dx,clientY:y+dy,bubbles:true,isPrimary:true}));ev('pointerdown',0,0);ev('pointermove',60,30);ev('pointerup',60,30);},{x:box.x+box.width/2,y:box.y+box.height/2});
      check(await page.evaluate(y0=>scrollY===y0,y0),`${tag}：觸控拖曳捲動了頁面`);
     }else{
      await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+80,box.y+box.height/2+40,{steps:5});await page.mouse.up();
     }
     check(await page.evaluate(()=>R3D.yaw!==0&&R3D.pitch!==0),`${tag}：拖曳沒有旋轉`);
     await page.locator('#r3dReset').click();
     check(await page.evaluate(()=>R3D.yaw===0&&R3D.pitch===0),`${tag}：重設視角`);
     check(JSON.stringify(await playState(page))===JSON.stringify(ps),`${tag}：拖曳／重設改了播放狀態`);

     // 預設視角＝影片方向：3D 投影的左右、上下順序和 2D 一樣（右肩在左肩哪一側、頭在腳上面）
     const dir=await page.evaluate(()=>{const P=S.world?.[cur],F=S.frames[cur];if(!P)return null;return {x:Math.sign(P[K[12]][0]-P[K[11]][0])===Math.sign(F[K[12]][0]-F[K[11]][0]),y:P[0][1]<P[K[27]][1]&&F[0][1]<F[K[27]][1]};});
     if(dir)check(dir.x&&dir.y,`${tag}：預設視角和影片不同向 ${JSON.stringify(dir)}`);

     // 沒有 world 的拍：提示、不丟例外
     const noWorld=await page.evaluate(()=>ALL.find(s=>s.world===null)?.id);
     if(noWorld!=null){await page.evaluate(id=>load(id,false),noWorld);await page.waitForFunction(()=>S?.frames?.length);}
     else await page.evaluate(()=>{window._keepWorld=S.world;S.world=null;render(cur);});
     check((await page.locator('#r3dMsg').textContent()).includes('這拍沒有 3D 資料'),`${tag}：沒有 world 要提示`);
     if(noWorld==null)await page.evaluate(()=>{S.world=_keepWorld;render(cur);});

     // 深淺主題都看得清楚：原始、示意兩色對面板背景對比 ≥ 3
     for(let t=0;t<2;t++){
      const c=await page.evaluate(()=>{const rgb=s=>s.startsWith('#')?[1,3,5].map(i=>parseInt(s.slice(i,i+2),16)):s.match(/[\d.]+/g).slice(0,3).map(Number);const lum=c=>{const [r,g,b]=c.map(x=>{x/=255;return x<=.03928?x/12.92:((x+.055)/1.055)**2.4;});return .2126*r+.7152*g+.0722*b;};const ratio=(a,b)=>{const [h,l]=[lum(a),lum(b)].sort((x,y)=>y-x);return (h+.05)/(l+.05);};const bg=rgb(getComputedStyle($('r3dCv')).backgroundColor);return [ratio(rgb(css('--s1')),bg),ratio(rgb(css('--s2')),bg)];});
      check(c.every(x=>x>=3),`${tag}：主題 ${t} 顏色對比不足 ${c}`);
      await page.locator('#theme').click();
     }

     // 版面：桌機面板在影片旁邊（橫片、直片都是）；手機在影片下方
     for(const portrait of real?[null]:[false,true]){
      await page.evaluate(p=>{if(p!=null){ALL.forEach(s=>{s.size=p?[360,640]:[640,360];});load(S.id,false);}scrollTo(0,0);},portrait);
      const lay=await page.evaluate(()=>{const a=$('stage').getBoundingClientRect(),b=$('r3dCv').getBoundingClientRect();return {beside:b.left>=a.right-1&&b.top<a.bottom,below:b.top>=a.bottom-1};});
      check(mobile?lay.below:lay.beside,`${tag}：${portrait?'直':'橫'}片面板位置 ${JSON.stringify(lay)}`);
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：${portrait?'直':'橫'}片面板打開時水平溢出`);
     }
     if(process.env.SITE_RESULTS){
      fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});
      if(eligible.length){await page.evaluate(id=>{load(id,false);},eligible[0]);await page.waitForFunction(()=>S?.frames?.length);await page.evaluate(()=>{R3D.yaw=.6;R3D.pitch=.35;goto(S.contact-20);});}
      await page.screenshot({path:path.join(process.env.SITE_RESULTS,`replay3d-${engine.name()}-${mobile?'400':'desktop'}-${di}.png`)});
     }
     await page.locator('#r3dBtn').click();
     check(await page.evaluate(()=>!R3D.on&&$('r3d').hidden&&!document.querySelector('.r3d-mark')),`${tag}：關掉面板要收乾淨`);
    }
    check(errors.length===0,`${tag}：前端例外 ${errors}`);
    console.log(`${tag}：3D 回放驗證完成`);await context.close();
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
assert.deepEqual(failures,[]);
console.log('site_replay3d ok');
