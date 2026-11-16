// #106：同場抽樣區間、誤差條與中性變化文字；瀏覽器使用全新隔離 context。
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
     const d=DAYS[DAY_KEYS[0]],u=(v,s=.3)=>({ci:[v-.6,v+.6],sem:s,valid:1000,samples:1000});
     const g={player:'me',kind:'FH',n:20,total:7,form:7,consistency:7,power:null,uncapped:7,knee_src:'knee',score_version:10,
      form_metrics:['knee','prep'],uncertainty:{total:u(7),form:u(7),consistency:u(7)},
      metrics:{knee:{status:'ok',score:8,cons:7,n:20,median:132,uncertainty:{score:u(8),cons:u(7)}},prep:{status:'ok',score:6,cons:7,n:20,median:.5,uncertainty:{score:u(6),cons:u(7)}}}};
     d.scores={groups:[g]};
     const row=(date,total)=>({session:d.id,date,camera:'側面',knee_src:'knee',score_version:10,n:20,comparable:true,items:{total,consistency:7},uncertainty:{total:u(total),consistency:u(7)},cons_set:['knee','prep'],form_metrics:['knee','prep']});
     window.TREND=[{player:'me',kind:'FH',history:[row('2026-01-01',7.5),row('2026-01-02',7)],flags:[{item:'total',flag:'在誤差內',base:7.5,now:7,diff:-.5,threshold:.83}]}];
     drawHome();
    });
    const days=await page.evaluate(()=>DAY_KEYS.filter(k=>DAYS[k].scores?.groups?.length));
    assert(days.length>0,'須有可驗證的評分');
    for(const day of days){
     await page.evaluate(day=>go(day,'overview'),day);
     const expected=await page.evaluate(day=>DAYS[day].scores.groups.flatMap(g=>{
      const values=[[g.total,g.uncertainty?.total],[g.form,g.uncertainty?.form],[g.consistency,g.uncertainty?.consistency],...Object.values(g.metrics).flatMap(m=>[[m.score,m.uncertainty?.score],[m.cons,m.uncertainty?.cons]])];
      return values.filter(([v,u])=>v!=null&&u?.ci).map(([,u])=>u.ci.map(v=>v.toFixed(1)).join('–'));
     }),day);
     const text=await page.locator('#overview').textContent();
     assert(expected.length>0,'至少一個有效區間');
     for(const range of expected)assert(text.includes(range),`總覽缺區間 ${range}`);
     assert(text.includes('同一場內抽樣的誤差，不是跨日重測'),'須交代區間定義');
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'總覽不得水平溢出');
     assert(await page.locator('#overview .ci').evaluateAll(es=>es.every(e=>parseFloat(getComputedStyle(e).fontSize)>=12)),'區間文字至少 12px');
     if(process.env.SITE_RESULTS){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`${engine.name()}-${mobile?'mobile':'desktop'}-overview-${days.indexOf(day)}.png`),fullPage:true});}
    }
    await page.evaluate(()=>{location.hash='#home';route();});
    assert(await page.locator('svg.spark g.error-bar').count()>0,'走勢點須有誤差條');
    assert(await page.locator('svg.spark g.error-bar').evaluateAll(es=>es.every(e=>e.querySelectorAll('line').length===3)),'誤差條須有端帽');
    assert(await page.locator('#home .flags li').filter({hasText:'在誤差內'}).count()>0,'誤差內變化須顯示');
    assert.equal(await page.locator('#home .flags li.up, #home .flags li.down').filter({hasText:'在誤差內'}).count(),0,'誤差內不能用進退步色');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'首頁不得水平溢出');
    if(process.env.SITE_RESULTS)await page.screenshot({path:path.join(process.env.SITE_RESULTS,`${engine.name()}-${mobile?'mobile':'desktop'}-home.png`),fullPage:true});
    const lines=await page.evaluate(()=>{
     const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');document.body.append(svg);
     const row=(version,date)=>({session:'synthetic',date,camera:'側面',knee_src:'knee',score_version:version,n:20,items:{total:7,consistency:7},uncertainty:{total:{ci:[6,8]},consistency:{ci:[6,8]}}});
     drawSpark(svg,{history:[row(9,'2026-01-01'),row(10,'2026-01-02')]});
     const count=svg.querySelectorAll('polyline').length;svg.remove();return count;
    });
    assert.equal(lines,0,'不同版本不連線');
    const segments=await page.evaluate(()=>{
     const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');document.body.append(svg);
     const old={session:'synthetic',date:'2026-01-01',camera:'側面',knee_src:'knee',score_version:10,items:{total:7,consistency:7}};
     const single={...old,date:'2026-01-02',form_n:1,form_metrics:['prep'],score_set:[['prep','total'],['prep']]};
     drawSpark(svg,{history:[old,single]});
     const muted=[...svg.querySelectorAll('polyline')].every(e=>e.getAttribute('stroke')==='var(--muted)');
     svg.replaceChildren();
     drawSpark(svg,{history:[{...single,camera:'前方'}, {...single,score_set:[['knee','total'],['knee']]}]});
     const labelled=[...svg.querySelectorAll('circle')].some(e=>e.getAttribute('aria-label')?.includes('項目不同'));
     const visible=svg.nextElementSibling?.classList.contains('score-notes')&&svg.nextElementSibling.textContent.includes('項目不同');
     svg.nextElementSibling?.classList.contains('score-notes')&&svg.nextElementSibling.remove();svg.remove();return {muted,labelled,visible};
    });
    assert(segments.muted,'舊資料連到單項點時線段須為中性色');
    assert(!segments.labelled&&!segments.visible,'跨鏡頭區段不得標為項目不同');
    assert.deepEqual(errors,[]);
    console.log(`${engine.name()} ${mobile?'iPhone 13':'1280×800'}：區間、誤差條、中性旗標、跨版本與版面通過`);
    await context.close();
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
