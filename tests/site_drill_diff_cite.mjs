// PR #159 後續：建議分頁的引用小標籤遇到 drill_diff 引用（docs/scoring.md §8）要顯示白話，不能出現 undefined。
// 合成場次（預設，不讀使用者資料）；SITE_REF=origin/main 預期紅（main 的 citeText 沒有 drill_diff 分支）。SITE_E2E_URL（真實副本）時跳過：真實 notes.json 沒有這種引用。
// tests/test_site_smoke.py 在 SITE_E2E_URL 的區塊裡註冊（只跑合成場次；SITE_REF 時跳過）。PLAYWRIGHT_MODULE 指向本機 playwright-core。多支網頁 E2E 一起跑時用 lockf＋nice 排隊。
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
if(process.env.SITE_E2E_URL){console.log('SITE_E2E_URL：跳過（真實副本沒有 drill_diff 引用）');process.exit(0);}
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture();
try{
for(const engine of [chromium,webkit]){
const browser=await engine.launch({headless:true});
try{
 const page=await (await browser.newContext({viewport:{width:1280,height:800}})).newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(f.url);await page.waitForSelector('body.ready');
 await page.evaluate(()=>{
  const d=DAYS[DAY_KEYS[0]],e=(diff,ci)=>({unit:'肩髖長',feed:{median:0.75,n:12},rally:{median:1,n:12},diff,ci,sem:0.03,valid:1000,samples:1000,reason:null});
  d.scores={groups:[{player:'me',kind:'FH',total:7,form:6,consistency:8,power:5,uncapped:7.5,n:24,uncertainty:{},metrics:{},
   drill_diff:{direction:'自拋 − 對打（feed − rally）',min_n:10,reason:null,metrics:{contact_fwd:e(-0.25,[-0.3,-0.2]),prep:e(0.05,null),knee:e(6.9,[3,21.5])}}},
   {player:'zed',kind:'FH',total:7,form:6,consistency:8,power:5,uncapped:7.5,n:24,uncertainty:{},metrics:{},drill_diff:{metrics:{contact_fwd:e(-0.1,[-0.2,0.1])}}}]};
  const c=(stat,value,extra={})=>({kind:'FH',drill_diff:'contact_fwd',stat,value,...extra});
  d.findings=[{title:'合成引用',text:'自拋減對打',cite:[c('diff',-0.25),c('ci_lo',-0.3),c('ci_hi',-0.2),c('feed',0.75),c('rally',1),
   {...c('diff',0.05),drill_diff:'prep'},{...c('diff',6.9),drill_diff:'knee'},c('diff',-0.1,{player:'zed'}),{kind:'FH',stat:'median',field:'knee',value:132}]}];
  drawSummary();
 });
 await page.evaluate(()=>{go(DAY,'advice');route();});
 const t=await page.locator('#findings .cite > span').filter({hasNotText:/^未核對$/}).allTextContents();
 assert.equal(t.length,9,'每筆引用保留');
 assert(t.every(s=>!/undefined|null|NaN/.test(s)),'不得出現 undefined／null／NaN：'+t.join(' | '));
 assert.equal(t[0],'正拍 自拋−對打 擊球前後 中位數差 -0.25（區間 -0.3 到 -0.2）');
 assert.equal(t[1],'正拍 擊球前後 中位數差的區間下界 -0.3');
 assert.equal(t[2],'正拍 擊球前後 中位數差的區間上界 -0.2');
 assert.equal(t[3],'正拍 擊球前後 自拋中位數 0.75');
 assert.equal(t[4],'正拍 擊球前後 對打中位數 1');
 assert.equal(t[5],'正拍 自拋−對打 準備時間 中位數差 0.05（區間不足）');  // ci 是 null：寫區間不足，不是 undefined
 assert.equal(t[6],'正拍 自拋−對打 膝蓋 中位數差 6.9（區間 3 到 21.5）');
 assert.equal(t[7],'zed・正拍 自拋−對打 擊球前後 中位數差 -0.1（區間 -0.2 到 0.1）');  // 球員要對到那一組
 assert.equal(t[8],'正拍 膝蓋 中位數 132');  // 舊引用格式不變
 assert.deepEqual(errors,[]);
 console.log(`${engine.name()}：drill_diff 引用的小標籤通過`);
}finally{await browser.close();}
}
}finally{await f.close();}
