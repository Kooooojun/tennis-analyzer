// #106：建議引用的區間、原始統計、可讀文字與讀屏；使用隔離瀏覽器 context。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=process.env.SITE_E2E_URL?{url:process.env.SITE_E2E_URL,close:async()=>{}}:await fixture();
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch({headless:true});
  try{
   for(const mobile of [false,true]){
    const context=await browser.newContext(mobile?devices['iPhone 13']:{viewport:{width:1280,height:800}});
    const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(f.url);await page.waitForSelector('body.ready');
    if(!process.env.SITE_E2E_URL)await page.evaluate(()=>{
     const d=DAYS[DAY_KEYS[0]],u=(a,b)=>({ci:[a,b]});
     d.scores={groups:[{player:'me',kind:'FH',total:7,form:6,consistency:8,power:5,uncapped:7.5,n:20,
      uncertainty:{total:u(6.4,7.6),form:u(5.3,6.8),consistency:u(7.1,8.9),power:u(4.2,5.9),uncapped:u(6.8,8.3)},
      metrics:{knee:{score:6.5,cons:7.2,median:132,n:20,spread:3,status:'ok',uncertainty:{score:u(5.9,7.1),cons:u(6.1,8.4)}}}}]};
     d.findings=[{title:'合成引用',text:'分數與原始統計',cite:[
      ...['total','form','consistency','power','uncapped'].map(metric=>({kind:'FH',metric,value:d.scores.groups[0][metric]})),
      {kind:'FH',metric:'knee',value:6.5},{kind:'FH',metric:'knee',stat:'score',value:6.5},{kind:'FH',metric:'knee',stat:'cons',value:7.2},
      ...['median','n','spread'].map(stat=>({kind:'FH',metric:'knee',stat,value:d.scores.groups[0].metrics.knee[stat]})),
      {kind:'FH',field:'knee',stat:'median',value:132},{stroke:1,field:'knee',value:110}]}];
     drawSummary();
    });
    const days=await page.evaluate(()=>DAY_KEYS.filter(k=>DAYS[k].scores?.groups?.length));
    let scoreCount=0,rawCount=0;
    for(const [i,day] of days.entries()){
     await page.evaluate(day=>{go(day,'advice');route();},day);
     const expected=await page.evaluate(day=>DAYS[day].findings.flatMap(f=>(f.cite||[]).map(c=>{
      const score=c.stroke==null&&c.metric&&(['total','form','consistency','power','uncapped'].includes(c.metric)||['score','cons'].includes(c.stat||'score'));
      const g=DAYS[c.day||day].scores?.groups.find(g=>g.player===(c.player||'me')&&g.kind===c.kind);
      const u=Object.hasOwn(g||{},c.metric)?g.uncertainty?.[c.metric]:g?.metrics[c.metric]?.uncertainty?.[c.stat||'score'];
      return {score,range:u?.ci?`（${u.ci.map(x=>x.toFixed(1)).join('–')}）`:'（區間不足）'};
     })),day);
     const cites=page.locator('#findings .cite > span').filter({hasNotText:/^未核對$/});
     const actual=await cites.allTextContents();assert.equal(actual.length,expected.length,'每筆引用保留');
     const spoken=await page.locator('.card[data-tab="advice"]').first().ariaSnapshot();
     for(const [j,e] of expected.entries()){
      if(e.score){scoreCount++;assert(actual[j].includes(e.range),`建議分數引用缺區間：第 ${j+1} 筆`);assert(spoken.includes(e.range),'讀屏須包含引用區間');}
      else{rawCount++;assert(!/（(?:區間不足|\d+\.\d–\d+\.\d)）/.test(actual[j]),'非分數引用不加區間');}
     }
     assert(spoken.includes('同一場內抽樣的誤差，不是跨日重測'),'建議讀屏須交代抽樣範圍');
     assert((await page.locator('.card[data-tab="advice"]').first().innerText()).includes('同一場內抽樣的誤差，不是跨日重測'),'建議區須有可見說明');
     assert(await cites.evaluateAll(es=>es.every(e=>parseFloat(getComputedStyle(e).fontSize)>=12)),'引用至少 12px');
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'建議頁不得水平溢出');
     if(process.env.SITE_RESULTS){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`${engine.name()}-${mobile?'mobile':'desktop'}-advice-${i}.png`),fullPage:true});}
    }
    assert(scoreCount>0&&rawCount>0,'分數與非分數都要驗證');
    const edge=await page.evaluate(()=>{
     const d=DAYS[DAY],old=d.scores,ci={ci:[1.2,3.4]},c={kind:'FH',metric:'knee',value:2};
     const base={player:'me',kind:'FH',metrics:{knee:{uncertainty:{score:ci,cons:{ci:[2.3,4.5]}}}}};
     try{
      d.scores={groups:[base,{...base,kind:'BH',uncertainty:{total:{ci:[4.5,6.7]}}},{...base,player:'other',uncertainty:{total:{ci:[7.8,9.0]}}}]};
      const exact=[citeText(c),citeText({...c,stat:'cons'}),citeText({kind:'BH',metric:'total',value:5}),citeText({player:'other',kind:'FH',metric:'total',value:8})];
      const missing=[citeText({kind:'FH',metric:'total',value:2}),citeText({kind:'OH',metric:'total',value:2})];
      base.uncertainty=null;base.metrics.knee.uncertainty=null;missing.push(citeText(c),citeText({kind:'FH',metric:'total',value:2}));
      base.metrics.knee.uncertainty={score:{ci:null}};missing.push(citeText(c));
      return {exact,missing};
     }finally{d.scores=old;}
    });
    ['（1.2–3.4）','（2.3–4.5）','（4.5–6.7）','（7.8–9.0）'].forEach((s,i)=>assert(edge.exact[i].includes(s),'引用須對應正確項目、球員與拍種'));
    assert(edge.missing.every(s=>s.includes('（區間不足）')),'缺估計、null 與閘門不足須一致');
    assert.deepEqual(errors,[]);
    console.log(`${engine.name()} ${mobile?'iPhone 13':'1280×800'}：${scoreCount} 筆分數區間、${rawCount} 筆原始引用、讀屏、方法說明與版面通過`);
    await context.close();
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
