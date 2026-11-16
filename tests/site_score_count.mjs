// #105：四組瀏覽器／視窗驗證；SITE_E2E_URL 可指定本機真實場次副本。
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=process.env.SITE_E2E_URL?null:await fixture(), failures=[];
const check=(ok,message)=>{if(!ok)failures.push(message);};
const muted=async locator=>await locator.count()>0&&locator.evaluate(e=>{const span=document.createElement('span');span.style.color='var(--muted)';document.body.append(span);const ok=getComputedStyle(e).color===getComputedStyle(span).color;span.remove();return ok;});
try{
 for(const engine of [chromium,webkit])for(const mobile of [false,true]){
  const browser=await engine.launch();
  try{
   const context=await browser.newContext(mobile?devices['iPhone 13']:{viewport:{width:1280,height:800}}),page=await context.newPage(), tag=`${engine.name()} ${mobile?'手機':'桌機'}`, errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.env.SITE_E2E_URL||f.url);await page.waitForSelector('body.ready');
   if(!f){
    const singles=await page.evaluate(()=>Object.values(DAYS).flatMap(d=>(d.scores?.groups||[]).filter(g=>g.form_n===1).map(g=>({day:d.id,player:g.player,kind:g.kind}))));
    check(singles.length===2,`${tag}：真實副本兩組單項`);
    for(const [i,s] of singles.entries()){await page.evaluate(s=>{go(s.day,'overview');route();},s);const card=page.locator('.score').filter({hasText:`只根據 1 項：準備時間`});check(await card.count()===1&&await muted(card.locator('.total')),`${tag}：真實單項灰色與名稱`);if(process.env.SITE_RESULTS)await page.screenshot({path:`${process.env.SITE_RESULTS}-${engine.name()}-${mobile?'mobile':'desktop'}-real-${i+1}.png`,fullPage:true});}
   }
   await page.evaluate(()=>{
    const d=DAYS[DAY_KEYS[0]],mk=(keys)=>({player:d.players[0],kind:'FH',n:20,total:7,form:6,consistency:10,capped:true,power:5.8,uncapped:7.5,knee_src:'knee',score_version:10,form_metrics:keys,form_n:keys.length,metrics:{prep:{score:6,cons:10,n:20,status:'ok'}},score_set:[['consistency',...keys,'total'].sort(),['prep']]});
    d.scores={groups:[mk(['prep']),{...mk(['knee','prep']),kind:'BH'}]};
    window.countDay=d.id;window.countGroup=d.scores.groups[0];
    window.TREND=[{player:d.players[0],kind:'FH',history:[{...countGroup,session:d.id,date:'2026-01-01',camera:'側面',comparable:true,items:{total:7,consistency:10}},{...countGroup,session:d.id,date:'2026-01-02',camera:'側面',comparable:true,items:{total:8,consistency:10}}],flags:[{item:'total',flag:'進步',base:7,now:8,diff:1}]}];
    go(d.id,'overview');route();drawOverview();
   });
   const single=page.locator('.score').first();
   check((await single.textContent()).includes('只根據 1 項：準備時間'),`${tag}：總覽名稱`);
   check(await muted(single.locator('.total')),`${tag}：總分灰色`);
   check(await muted(single.locator('.form-value')),`${tag}：技術分灰色`);
   check(!await muted(page.locator('.score').nth(1).locator('.total'))&&!(await page.locator('.score').nth(1).textContent()).includes('只根據'),`${tag}：兩項總分維持原樣`);
   check((await single.ariaSnapshot()).includes('只根據 1 項：準備時間'),`${tag}：總覽讀屏`);
   check(await single.locator('.flags .single-metric').count()>0,`${tag}：旗標總分灰色`);
   await page.evaluate(()=>{DAYS[DAY].findings=[{title:'合成引用',text:'分數',cite:[{player:countGroup.player,kind:'FH',metric:'total',stat:'score',value:7},{player:countGroup.player,kind:'FH',metric:'form',stat:'score',value:6},{player:countGroup.player,kind:'FH',metric:'uncapped',stat:'score',value:7.5}]}];drawSummary();go(DAY,'advice');route();});
   check(await page.locator('.cite .single-metric').count()===3&&(await page.locator('.cite').ariaSnapshot()).includes('只根據 1 項：準備時間'),`${tag}：建議引用的總分、技術分與未壓前總分`);
   const cited=await page.locator('.cite').textContent();check(cited.includes('未壓前總分')&&!cited.includes('uncapped'),`${tag}：未壓前總分引用顯示中文`);
   await page.evaluate(()=>{go(null);route();});
   const home=page.locator('#home');
   check(await home.locator('.sess .single-metric').count()>0,`${tag}：首頁總分灰色`);
   check((await home.ariaSnapshot()).includes('只根據 1 項：準備時間'),`${tag}：首頁讀屏`);
   const dot=home.locator('svg circle[aria-label*="只根據 1 項：準備時間"]').first();
   check(await dot.count()>0&&await dot.getAttribute('fill')==='var(--muted)',`${tag}：走勢點灰色、讀屏名稱`);
   check((await home.locator('.score-notes').allTextContents()).join('').includes('只根據 1 項：準備時間'),`${tag}：走勢旁可見文字`);
   await page.evaluate(()=>{const t=TREND[0];window.countHistory=t.history;t.history=[...countHistory,{...countHistory[1],date:'undated',comparable:false,form_metrics:['knee','prep'],form_n:2}];drawHome();});
   check(await muted(home.locator('.flags .single-metric'))&&(await home.locator('.flags').ariaSnapshot()).includes('只根據 1 項：準備時間'),`${tag}：有日期單項旗標不受無日期兩項尾筆影響`);
   await page.evaluate(()=>{const t=TREND[0];t.history=[...countHistory.map(r=>({...r,form_metrics:['knee','prep'],form_n:2})),{...countHistory[1],date:'undated',comparable:false}];drawHome();});
   check(await home.locator('.flags .single-metric').count()===0&&!(await home.locator('.flags').textContent()).includes('只根據'),`${tag}：有日期兩項旗標不誤用無日期單項尾筆`);
   await page.evaluate(()=>{TREND[0].history=countHistory;drawHome();});
   const changed=await page.evaluate(()=>{
    const t=TREND[0],a=t.history[0];t.history[1]={...a,date:'2026-01-02',form_metrics:['knee'],score_set:[['consistency','knee','total'],['prep']],items:{total:9,consistency:10}};t.flags=[];drawHome();
    return {lines:$('home').querySelectorAll('svg polyline').length,text:$('home').textContent,aria:[...$('home').querySelectorAll('svg circle')].map(c=>c.getAttribute('aria-label'))};
   });
   check(changed.lines===0&&changed.text.includes('項目不同')&&changed.aria.some(t=>t?.includes('項目不同')),`${tag}：同數量不同指標不連線、項目不同`);
   const gap=await page.evaluate(()=>{const t=TREND[0];t.history.splice(1,0,{session:countDay,date:'2026-01-01',camera:'側面',items:{total:null,consistency:null}});drawHome();return [...$('home').querySelectorAll('svg circle')].some(c=>c.getAttribute('aria-label')?.includes('項目不同'));});
   check(gap,`${tag}：跳過無總分的舊場次後仍比較相鄰有效點`);
   if(process.env.SITE_RESULTS)await page.screenshot({path:`${process.env.SITE_RESULTS}-${engine.name()}-${mobile?'mobile':'desktop'}-changed.png`,fullPage:true});
   await page.evaluate(()=>{go(countDay,'video');route();cmpLoad({...ALL[0],kind:'FH',player:countGroup.player},{...ALL[1],kind:'BH',player:countGroup.player});});
   check(!(await page.locator('#capA').textContent()).includes('項目不同')&&!(await page.locator('#capB').textContent()).includes('項目不同'),`${tag}：單拍比較不顯示總分採計差異提示`);
   await page.evaluate(()=>{delete countGroup.form_metrics;delete countGroup.form_n;delete countGroup.score_set;go(countDay,'overview');route();drawOverview();drawHome();});
   check(!(await page.locator('.score').first().textContent()).includes('只根據'),`${tag}：舊分數不亂標`);
   check(!await muted(page.locator('.score').first().locator('.total')),`${tag}：舊總分維持顏色`);
   const legacy=await page.evaluate(()=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');document.body.append(svg);const a={session:countDay,date:'2026-01-01',camera:'側面',items:{total:7,consistency:10}};drawSpark(svg,{history:[a,{...a,date:'2026-01-02'}]});const n=svg.querySelectorAll('polyline').length;svg.remove();return n;});
   check(legacy===2,`${tag}：舊走勢維持連線`);
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：無橫向溢出`);
   check(errors.length===0,`${tag}：無前端例外 ${errors.join(',')}`);
   console.log(`${tag}：指標採計驗證完成`);
  }finally{await browser.close();}
 }
}finally{await f?.close();}
assert.deepEqual(failures,[]);
