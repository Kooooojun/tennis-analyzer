// #119：來源標示與精度說明；SITE_REF=origin/main 可取得修改前失敗證據。
// PLAYWRIGHT_MODULE 指向本機 playwright-core；SITE_E2E_URL 可指定兩場正式資料副本。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=process.env.SITE_E2E_URL?{url:process.env.SITE_E2E_URL,close:async()=>{}}:await fixture();
const failures=[],check=(ok,msg)=>{if(!ok)failures.push(msg);};
async function overlayLabels(page,compare=false){
 return page.evaluate(compare=>{
 const [cv,vid,s]=compare?[$('cvA'),vA,A]:[$('cv'),v,S],g=cv.getContext('2d'),fill=g.fillText,arc=g.arc,texts=[];let knee;
 g.arc=function(x,y,r,...args){if(r===10||r===15)knee=x;return arc.call(this,x,y,r,...args);};
 g.fillText=function(t,x,y,...args){if(/°/.test(t)){const w=this.measureText(t).width;texts.push({text:t,clear:x>knee+3.2||x+w<knee-3.2});}return fill.call(this,t,x,y,...args);};
 try{paint(cv,vid,s,Math.max(0,s.contact-30),{skel:true,guides:true,zoom:compare});}finally{g.fillText=fill;g.arc=arc;}
 return texts;
 },compare);
}
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   for(const mobile of [false,true]){
    const context=await browser.newContext(mobile?devices['iPhone 13']:{viewport:{width:1280,height:800}}),page=await context.newPage(),tag=`${engine.name()} ${mobile?'手機':'桌機'}`,errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(f.url);await page.waitForSelector('body.ready');
    const days=await page.evaluate(()=>DAY_KEYS);
    for(const [di,day] of days.entries()){
     await page.evaluate(day=>go(day,'stroke'),day);
     await page.waitForFunction(()=>S?.frames?.length);
     if(!process.env.SITE_E2E_URL)await page.evaluate(()=>{
      ALL.forEach(s=>{s.knee2d=s.knee;s.knee3d=128;s.knee=128;s.knee_warn=false;});
      const world=Array.from({length:17},(_,i)=>[i%2*.2,i*.025,0]);
      for(const [i,p] of [[23,[0,0,0]],[25,[0,.5,0]],[27,[.4,.8,0]],[24,[.2,0,0]],[26,[.2,.5,0]],[28,[.2,1,0]]])world[K[i]]=p;
      ALL.forEach(s=>{s.world=Array.from({length:s.n},()=>world);});SER.clear();MED=dayStats(mine());load(S.id,false);drawList();
     });
     const ids=await page.evaluate(()=>({three:ALL.find(s=>s.knee3d!=null)?.id,two:ALL.find(s=>s.knee3d==null&&s.knee!=null)?.id}));
     for(const [source,id] of Object.entries(ids)){
      if(id==null)continue;
      await page.evaluate(id=>load(id,false),id);await page.waitForFunction(()=>S?.frames?.length&&v.readyState>=2&&!v._fetching);
      const label=await page.locator('#mKnee').textContent(),title=await page.locator('#mKnee').getAttribute('title');
      if(source==='three'){
       check(/3D.*估/.test(label),`${tag}：3D 單拍須標估計`);
       check(/估計.*單鏡頭.*僅供參考/.test(title),`${tag}：3D title 須完整說明`);
       check(/中位數.*3D.*估/.test(await page.locator('#cKnee').textContent()),`${tag}：3D 群組中位數須標估計`);
       check(/3D.*估/.test(await page.locator('#legKnee').textContent()),`${tag}：曲線來源須標估計`);
       check(/膝 3D.*估/.test(await page.locator(`#strokes button[data-id="${id}"]`).textContent()),`${tag}：列表須標估計`);
      }else check(/2D/.test(label)&&!/估|單鏡頭/.test(label+title),`${tag}：2D 拍不可誤標 3D 估計`);
      const before=await page.evaluate(()=>({knee:S.knee,knee3d:S.knee3d}));
      const overlay=await overlayLabels(page);
      check(overlay.length>0,`${tag}：須實際畫角度標籤`);
      check(overlay.every(({text:t})=>source==='three'?/°3D.*估/.test(t):/°2D/.test(t)&&!/估/.test(t)),`${tag}：骨架來源標示 ${JSON.stringify(overlay)}`);
      check(overlay.every(t=>t.clear),`${tag}：骨架標籤不可蓋住膝關節`);
      if(!process.env.SITE_E2E_URL)check(overlay[0]?.text==='127°3D估',`${tag}：三位數左膝短標`);
      await page.evaluate(()=>{go(DAY,'video');cmpLoad(S,ALL.find(s=>s!==S));});
      await page.locator('#vA').scrollIntoViewIfNeeded();await page.waitForFunction(()=>A?.frames?.length&&vA.readyState>=2);
      const compareOverlay=await overlayLabels(page,true);
      check(compareOverlay.length>0&&compareOverlay.every(t=>t.clear),`${tag}：窄幅比較短標不可蓋住膝關節`);
      check(source==='three'?/膝 3D.*估/.test(await page.locator('#capA').textContent()):!/估|單鏡頭/.test(await page.locator('#capA').textContent()),`${tag}：比較標題來源`);
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：比較無水平溢出`);
      await page.evaluate(()=>go(DAY,'stroke'));
      check(!(await page.locator('#mElbow').textContent()).includes('°'),`${tag}：手肘不顯示角度`);
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：單拍無水平溢出`);
      assert.deepEqual(await page.evaluate(()=>({knee:S.knee,knee3d:S.knee3d})),before);
      if(process.env.SITE_RESULTS){fs.mkdirSync(process.env.SITE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SITE_RESULTS,`${engine.name()}-${mobile?'mobile':'desktop'}-${di}-${source}.png`),fullPage:true});}
     }
     await page.evaluate(()=>go(DAY,'overview'));
     if(!process.env.SITE_E2E_URL)await page.evaluate(()=>{
      DAYS[DAY].scores={groups:[{player:'me',kind:'FH',n:20,total:7,form:7,consistency:7,knee_src:'knee3d',metrics:{knee3d:{status:'ok',median:128,n:20,score:7,cons:7}}}]};drawOverview();
     });
     await page.evaluate(()=>go(DAY,'charts'));
     const chartLabel=await page.locator('#stripKnee .lbl').textContent(),dots=await page.locator('#stripKnee circle title').allTextContents();
     check(!/3D(?!估)/.test(chartLabel+dots.join('')),`${tag}：圖表與圓點來源須標估計`);
     check(!/3D(?!估)/.test(await page.locator('#trend').textContent()),`${tag}：跨場中位數與差距來源須標估計`);
     check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：圖表無水平溢出`);
     const titles=await page.locator('#overview .bars .num[title*="膝角來源"]').evaluateAll(es=>es.map(e=>e.title));
     check(titles.length>0&&titles.every(t=>!/來源 3D(?!.*估計.*單鏡頭)/.test(t)),`${tag}：評分膝角來源須說明估計與單鏡頭`);
    }
    const caveat=await page.locator('.caveat').allTextContents();
    check(caveat.some(t=>t.includes('1° 不代表準到 1°')&&t.includes('無法判定進退步')&&t.includes('不是多機校正')),`${tag}：精度與誤差內說明`);
    if(!process.env.SITE_E2E_URL){
     await page.evaluate(()=>{ALL.forEach(s=>{delete s.knee3d;s.knee=s.knee2d;});MED=dayStats(mine());load(S.id,false);drawList();});
     check(!/估|單鏡頭/.test((await page.locator('#mKnee').textContent())+(await page.locator('#mKnee').getAttribute('title'))),`${tag}：2D 回退不可標為 3D 估計`);
     const twoOverlay=await page.evaluate(()=>{
      S.world=null;SER.delete(S);const g=$('cv').getContext('2d'),fill=g.fillText,texts=[];
      g.fillText=function(t,...args){texts.push(t);return fill.call(this,t,...args);};
      try{paint($('cv'),v,S,S.contact-30,{skel:true,guides:true});}finally{g.fillText=fill;}
      return texts.filter(t=>/°/.test(t));
     });
     check(twoOverlay.length>0&&twoOverlay.every(t=>/°2D/.test(t)&&!/估/.test(t)),`${tag}：2D 骨架不可標估計`);
     check(!/估|單鏡頭/.test(await page.locator('#cKnee').textContent()),`${tag}：2D 群組不可標估計`);
     await page.evaluate(()=>{go(DAY,'overview');DAYS[DAY].scores.groups[0].knee_src='knee';drawOverview();});
     check(!/估|單鏡頭/.test(await page.locator('#overview .bars .num').getAttribute('title')),`${tag}：2D 評分來源不可標估計`);
     await page.evaluate(()=>go(DAY,'stroke'));
     for(const why of ['view','gap']){
      await page.evaluate(why=>{S.knee_warn=true;S.knee_warn_why=why;load(S.id,false);},why);
      check((await page.locator('#cKnee').textContent()).includes(why==='view'?'膝角看不準':'這拍角度不準'),`${tag}：保留 ${why} 警示`);
     }
    }
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${tag}：總覽無水平溢出`);
    check(errors.length===0,`${tag}：無前端例外 ${errors}`);
    console.log(`${tag}：來源標示驗證完成`);await context.close();
   }
  }finally{await browser.close();}
 }
}finally{await f.close();}
assert.deepEqual(failures,[]);
