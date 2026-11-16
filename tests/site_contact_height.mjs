// #101：沿用合成場次，驗證手腕高度名稱、中性參考、品質閘門與跨版本連線。
// Run: PLAYWRIGHT_MODULE=... node tests/site_contact_height.mjs
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(), failures=[];
const check=(ok,message)=>{if(!ok)failures.push(message);};
const neutral=color=>{const rgb=color.startsWith('#')?color.slice(1).match(/../g).map(x=>parseInt(x,16)):color.match(/[\d.]+/g)?.slice(0,3).map(Number);return rgb?.length===3&&Math.max(...rgb)-Math.min(...rgb)<30;};
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   const page=await browser.newPage({viewport:{width:1280,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(f.url);await page.waitForSelector('body.ready');
   await page.evaluate(()=>go(DAY_KEYS[0],'stroke'));
   await page.waitForFunction(()=>S?.frames?.length);
   const colors=await page.evaluate(()=>{
    const g=$('cv').getContext('2d'),arc=g.arc,rect=g.fillRect,colors={low:[],high:[],band:[]};
    let target=colors.low;
    g.arc=function(...args){if(args[2]===11)target.push(this.strokeStyle);return arc.apply(this,args);};
    g.fillRect=function(...args){colors.band.push(this.fillStyle);return rect.apply(this,args);};
    const saved=S.vis;
    try{for(const vis of [.4,.5]){S.vis=vis;target=vis<.5?colors.low:colors.high;paint($('cv'),v,S,S.contact,{guides:true});}}
    finally{g.arc=arc;g.fillRect=rect;S.vis=saved;}
    return colors;
   });
   check(colors.low.length===0||colors.low.every(neutral),`${engine.name()}: 低可見度圈須中性或省略`);
   check(colors.high.length===1&&colors.high.every(neutral),`${engine.name()}: 高度圈不判好壞`);
   check(colors.band.length>0&&colors.band.every(neutral),`${engine.name()}: 影片參考帶須中性`);
   await page.evaluate(()=>{ALL.forEach((s,i)=>{s.contact_h=.53;s.contact_fwd=.4;s.vis=i===0?.4:.9;});MED=dayStats(mine());drawChecks();go(DAY,'charts');drawCharts();});
   check(await page.locator('#stripHeight .lbl').textContent().then(t=>t.includes('擊球時手腕高度（2D）')&&t.includes('五格中位數')),`${engine.name()}: 圖表名稱與五格定義`);
   check(await page.locator('#stripHeight circle[data-id="0"]').getAttribute('data-hollow')==='1',`${engine.name()}: 低可見度空心點`);
   const band=await page.locator('#contactPlot rect').getAttribute('fill');
   check(band==='var(--muted)'||neutral(band),`${engine.name()}: 散佈圖參考帶須中性`);
   check((await page.locator('#contactPlot').textContent()).includes('參考（暫定）'),`${engine.name()}: 散佈圖標示暫定參考`);
   await page.evaluate(()=>go(DAY,'advice'));
   check(!(await page.locator('.check').allTextContents()).join('').includes('腰到胸'),`${engine.name()}: 教學不再要求腰到胸`);
   const heightRow=page.locator('.check li').filter({hasText:'擊球時手腕高度（2D）'});
   check(await heightRow.count()>0&&await heightRow.locator('.you.ok').count()===0,`${engine.name()}: 教學高度不標綠色通過`);
   const series=await page.evaluate(()=>{
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');document.body.append(svg);
    const row=(version,total,date)=>({session:'synthetic',date,camera:'側面',knee_src:'knee',score_version:version,items:{total,consistency:7}});
    drawSpark(svg,{history:[row(9,7,'2026-01-01'),row(10,8,'2026-01-02')]});
    const count=svg.querySelectorAll('polyline').length;svg.remove();return count;
   });
   check(series===0,`${engine.name()}: 版本 9／10 不連線`);
   for(const width of [390,1280]){await page.setViewportSize({width,height:900});await page.evaluate(()=>go(DAY,'stroke'));check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${engine.name()}: ${width}px 無橫向溢出`);}
   check(errors.length===0,`${engine.name()}: 無前端例外 ${errors.join(',')}`);
   console.log(engine.name()+': 手腕高度驗證完成');
  }finally{await browser.close();}
 }
}finally{await f.close();}
assert.deepEqual(failures,[]);
console.log('site_contact_height.mjs: all assertions passed');
