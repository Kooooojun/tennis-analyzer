// #130／#150：用合成資料驗證單拍卡片的中位數與標籤。PLAYWRIGHT_MODULE 指向本機 playwright-core。
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(),failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
// 每組一組固定值：knee, open_min, contact_h, prep, finish（發球用 reach）。同組內值相同，所以中位數就是組值。
const G={
 meHigh:{player:'me',kind:'FH',drill:'high',knee:100,open_min:10,contact_h:.10,prep:.1,finish:.10},
 meFeed:{player:'me',kind:'FH',drill:'feed',knee:120,open_min:20,contact_h:.20,prep:.2,finish:.20},
 palHigh:{player:'pal',kind:'FH',drill:'high',knee:140,open_min:30,contact_h:.30,prep:.3,finish:.30},
 palFeed:{player:'pal',kind:'FH',drill:'feed',knee:160,open_min:40,contact_h:.40,prep:.4,finish:.50},
 meBH:{player:'me',kind:'BH',drill:'feed',knee:170,open_min:50,contact_h:.50,prep:.5,finish:.60},
 palBH:{player:'pal',kind:'BH',drill:'feed',knee:190,open_min:60,contact_h:.60,prep:.6,finish:.70},
 meRally:{player:'me',kind:'FH',drill:'rally',knee:130,open_min:70,contact_h:.70,prep:.7,finish:.80},
 meFeedLow:{player:'me',kind:'FH',drill:'feed',knee:120,open_min:20,contact_h:.20,prep:.9,prep_trunc:true,finish:.20},
 meSV:{player:'me',kind:'SV',drill:'feed',knee:150,open_min:25,contact_h:.25,prep:.3,finish:null,reach:.35},
};
G.meFeedEarly={...G.meFeed,prep:.1};
G.meFeedLate={...G.meFeed,prep:.3};
G.palFeedLow={...G.palFeed,knee:150,open_min:35,contact_h:.35,prep:.35,finish:.4};
G.meOH={...G.meSV,kind:'OH',drill:null};
const rep=(k,n)=>Array(n).fill(k);
const SCENARIOS={
 // 兩人輪流打，每組 5 拍；反拍我 3、對手 2。
 two:{players:['me','pal'],order:[...Array(5).fill(['meHigh','palHigh','meFeed','palFeed']).flat(),'meBH','palBH','meBH','palBH','meBH']},
 // 對手的高拋只有 3 拍（<5），其餘 5 拍或以上。
 short:{players:['me','pal'],order:[...rep('meHigh',5),...rep('meFeed',5),...rep('palHigh',3),...rep('palFeed',3),...rep('palFeedLow',2),...rep('meBH',4),...rep('palBH',3)]},
 // 單人混 drill：對打 5 拍、自拋 5 拍（其中 2 拍準備時間只是下限，不計入）、高拋 3 拍（<5，退回全部正拍）。
 misc:{players:['me'],order:['meFeedEarly','meFeed','meFeedLate',...rep('meFeedLow',2),...rep('meRally',5),...rep('meHigh',3),...rep('meBH',12)]},
 // 單人且只有一種正拍 drill 時，拍數夠的組沿用舊版中位數。多 drill 的收拍，以及 ≥5 拍的高拋，改依 drill 分組計算。
 single:{players:['me'],order:[...rep('meFeed',14),...rep('meBH',5),...rep('meSV',5),'meOH']},
};
// 每格：[情境, 第幾拍, 說明, 標籤, 膝蓋, 轉肩, 手腕高度, 準備時間, 收拍]。標籤＝卡片上寫的比較組，每張卡都要寫。
const CASES=[
 ['two',0,'我的高拋','我的高拋正拍中位數',100,10,10,'0.10','0.10'],
 ['two',2,'我的自己拋球','我的自己拋球正拍中位數',120,20,20,'0.20','0.20'],
 ['two',1,'對手的高拋','pal的高拋正拍中位數',140,30,30,'0.30','0.30'],
 ['two',3,'對手的自己拋球','pal的自己拋球正拍中位數',160,40,40,'0.40','0.50'],
 ['two',20,'我的反拍','我的反拍中位數',170,50,50,'0.50','0.60'],
 ['two',21,'對手的反拍','pal的反拍中位數',190,60,60,'0.60','0.70'],
 ['short',0,'我的高拋（5 拍，剛好夠）','我的高拋正拍中位數',100,10,10,'0.10','0.10'],
 ['short',10,'對手的高拋（3 拍，退回對手的正拍）','pal的正拍中位數（高拋不到 5 拍）',150,35,35,'0.35','0.40'],
 ['short',13,'對手的自己拋球（5 拍）','pal的自己拋球正拍中位數',160,40,40,'0.40','0.50'],
 ['short',18,'我的反拍（4 拍）','我的反拍中位數',170,50,50,'0.50','0.60'],
 ['short',22,'對手的反拍（3 拍）','pal的反拍中位數',190,60,60,'0.60','0.70'],
 ['misc',5,'對打（5 拍）','我的對打正拍中位數',130,70,70,'0.70','0.80'],
 ['misc',0,'自拋（含 2 拍 prepLow，準備時間不計）','我的自己拋球正拍中位數',120,20,20,'0.20','0.20'],
 ['misc',10,'單人高拋 3 拍，退回全部正拍','我的正拍中位數（高拋不到 5 拍）',120,20,20,'0.30','0.20'],
 ['single',0,'單人自己拋球','我的自己拋球正拍中位數',120,20,20,'0.20','0.20'],
 ['single',14,'單人反拍','我的反拍中位數',170,50,50,'0.50','0.60'],
 ['single',19,'單人發球','我的發球中位數',150,25,25,'0.30','0.35'],
];
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   const page=await (await browser.newContext({viewport:{width:1280,height:800}})).newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(f.url);await page.waitForSelector('body.ready');
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
   await page.waitForFunction(()=>S?.frames?.length);
   for(const [name,sc] of Object.entries(SCENARIOS)){
    // 把 25 拍的合成場次改寫成這個情境；網頁其餘部分不動。
    await page.evaluate(({sc,G})=>{
     DAYS[DAY].players=sc.players;
     ALL.forEach((s,i)=>{Object.assign(s,{finish:null,reach:null,vis:1,knee_warn:false,prep_trunc:false,knee3d:null,knee2d_ok:true},G[sc.order[i]]);});
     pfilter='ALL';MED=dayStats(mine());
    },{sc,G});
    for(const [cs,idx,what,lbl,knee,open,h,prep,fin] of CASES.filter(c=>c[0]===name)){
     const got=await page.evaluate(i=>{load(i,false);return Object.fromEntries(['cKnee','cOpen','cHeight','cPrep','cForm1'].map(id=>[id,document.getElementById(id).textContent]));},idx);
     // 在 #146 前的頁面，85 個數值中有 28 個不同。分開檢查數值和標籤才能看到這些差異。
     const numbers={cKnee:`2D ${knee}°`,cOpen:`${open}%`,cHeight:String(h),cPrep:`${prep}s`,cForm1:fin};
     for(const [id,exp] of Object.entries(numbers)){
      const [,label='',actual]=got[id].match(/^(.*中位數(?:（[^）]*）)?) (.*)$/)??[];
      const at=`${engine.name()} ${cs}／${what}／#${id}`;
      check(actual===exp,`${at} 數字：要 ${exp}，實際 ${actual}`);
      const ok=id==='cKnee'?label.endsWith(lbl):id==='cForm1'?label.endsWith('；'+lbl):label===lbl;
      check(ok,`${at} 標籤：要 ${lbl}，實際 ${label}`);
     }
    }
   }
   const overhead=await page.evaluate(()=>{
    load(24,false);
    return {label:strokeLabel(S),median:$('cKnee').textContent,formHidden:$('kForm1').parentElement.hidden};
   });
   assert.match(overhead.label,/高壓/);
   assert.match(overhead.median,/我的高壓中位數/);
   assert.equal(overhead.formHidden,true);
   check(errors.length===0,`${engine.name()}：頁面錯誤 ${errors.join('|')}`);
  }finally{await browser.close();}
 }
}finally{await f.close?.();}
if(failures.length){console.error(failures.join('\n'));process.exit(1);}
console.log('site_card_medians ok');
