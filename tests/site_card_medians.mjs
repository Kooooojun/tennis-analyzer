// #130：單拍卡片的中位數比較組。合成資料，不讀任何使用者資料；SITE_REF=origin/main 可在修改前的網頁上跑。
// PLAYWRIGHT_MODULE 指向本機 playwright-core。三個情境：兩人輪流、某 drill 不到 5 拍、單人單 drill。
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
 meSV:{player:'me',kind:'SV',drill:'feed',knee:150,open_min:25,contact_h:.25,prep:.3,finish:null,reach:.35},
};
const rep=(k,n)=>Array(n).fill(k);
const SCENARIOS={
 // 兩人輪流打，每組 5 拍；反拍我 3、對手 2。
 two:{players:['me','pal'],order:[...Array(5).fill(['meHigh','palHigh','meFeed','palFeed']).flat(),'meBH','palBH','meBH','palBH','meBH']},
 // 對手的高拋只有 3 拍（<5），其餘 5 拍或以上。
 short:{players:['me','pal'],order:[...rep('meHigh',5),...rep('meFeed',5),...rep('palHigh',3),...rep('palFeed',5),...rep('meBH',4),...rep('palBH',3)]},
 // 單人、只有一種 drill、拍數夠。
 single:{players:['me'],order:[...rep('meFeed',15),...rep('meBH',5),...rep('meSV',5)]},
};
// 每個情境要看的拍：[情境, 第幾拍（order 的索引）, 期望]。期望的鍵＝卡片 id；cKnee／cForm1 比對結尾，其餘全等。
const CASES=[
 ['two',0,'我的高拋',{cKnee:'高拋正拍中位數 2D 110°',cOpen:'中位數 15%',cHeight:'中位數 15',cPrep:'高拋正拍中位數 0.20s',cForm1:'中位數 0.25'}],
 ['two',2,'我的自己拋球',{cKnee:'自己拋球正拍中位數 2D 120°',cOpen:'中位數 20%',cHeight:'中位數 20',cPrep:'自己拋球正拍中位數 0.30s',cForm1:'中位數 0.25'}],
 ['two',1,'對手的高拋',{cKnee:'高拋正拍中位數 2D 150°',cOpen:'中位數 35%',cHeight:'中位數 35',cPrep:'高拋正拍中位數 0.20s',cForm1:'中位數 0.25'}],
 ['two',3,'對手的自己拋球',{cKnee:'自己拋球正拍中位數 2D 160°',cOpen:'中位數 40%',cHeight:'中位數 40',cPrep:'自己拋球正拍中位數 0.30s',cForm1:'中位數 0.25'}],
 ['two',20,'我的反拍',{cKnee:'反拍中位數 2D 170°',cOpen:'中位數 50%',cHeight:'中位數 50',cPrep:'反拍中位數 0.50s',cForm1:'中位數 0.60'}],
 ['two',21,'對手的反拍',{cKnee:'反拍中位數 2D 190°',cOpen:'中位數 60%',cHeight:'中位數 60',cPrep:'反拍中位數 0.50s',cForm1:'中位數 0.60'}],
 ['short',0,'我的高拋（5 拍）',{cKnee:'高拋正拍中位數 2D 110°',cOpen:'中位數 15%',cHeight:'中位數 15',cPrep:'高拋正拍中位數 0.10s',cForm1:'中位數 0.20'}],
 ['short',10,'對手的高拋（3 拍）',{cKnee:'高拋正拍中位數 2D 160°',cOpen:'中位數 40%',cHeight:'中位數 40',cPrep:'高拋正拍中位數 0.10s',cForm1:'中位數 0.20'}],
 ['short',13,'對手的自己拋球（5 拍）',{cKnee:'自己拋球正拍中位數 2D 160°',cOpen:'中位數 40%',cHeight:'中位數 40',cPrep:'自己拋球正拍中位數 0.30s',cForm1:'中位數 0.20'}],
 ['short',18,'我的反拍（4 拍）',{cKnee:'反拍中位數 2D 170°',cOpen:'中位數 50%',cHeight:'中位數 50',cPrep:'反拍中位數 0.50s',cForm1:'中位數 0.60'}],
 ['short',22,'對手的反拍（3 拍）',{cKnee:'反拍中位數 2D 190°',cOpen:'中位數 60%',cHeight:'中位數 60',cPrep:'反拍中位數 0.50s',cForm1:'中位數 0.60'}],
 ['single',0,'單人自己拋球',{cKnee:'自己拋球正拍中位數 2D 120°',cOpen:'中位數 20%',cHeight:'中位數 20',cPrep:'自己拋球正拍中位數 0.20s',cForm1:'中位數 0.20'}],
 ['single',15,'單人反拍',{cKnee:'反拍中位數 2D 170°',cOpen:'中位數 50%',cHeight:'中位數 50',cPrep:'反拍中位數 0.50s',cForm1:'中位數 0.60'}],
 ['single',20,'單人發球',{cKnee:'發球中位數 2D 150°',cOpen:'中位數 25%',cHeight:'中位數 25',cPrep:'發球中位數 0.30s',cForm1:'中位數 0.35'}],
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
    for(const [cs,idx,what,want] of CASES.filter(c=>c[0]===name)){
     const got=await page.evaluate(i=>{load(i,false);return Object.fromEntries(['cKnee','cOpen','cHeight','cPrep','cForm1'].map(id=>[id,document.getElementById(id).textContent]));},idx);
     for(const [id,exp] of Object.entries(want)){
      const ok=id==='cKnee'||id==='cForm1'?got[id].endsWith(exp):got[id]===exp;
      check(ok,`${engine.name()} ${cs}／${what}／#${id}：要 ${JSON.stringify(exp)}，實際 ${JSON.stringify(got[id])}`);
     }
    }
   }
   check(errors.length===0,`${engine.name()}：頁面錯誤 ${errors.join('|')}`);
  }finally{await browser.close();}
 }
}finally{await f.close?.();}
if(failures.length){console.error(failures.join('\n'));process.exit(1);}
console.log('site_card_medians ok');
