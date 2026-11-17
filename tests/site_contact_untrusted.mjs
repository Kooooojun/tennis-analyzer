// 合成場次：接觸格不可信的原因須在單拍、列表與比較區一致顯示。
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(), failures=[];
const message='擊球格不可信，這拍不量';
try{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch();
  try{
   const page=await browser.newPage(), errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(f.url);await page.waitForSelector('body.ready');
   await page.evaluate(()=>{
    const s=ALL[0];s.knee=s.knee3d=s.knee2d=null;s.contact_untrusted=true;s.knee_warn=true;s.knee_warn_why='contact';
    go(DAY,'stroke');load(s.id,false);drawList();
   });
   const detail=await page.locator('#cKnee').textContent();
   const list=await page.locator('#strokes button[data-id="0"]').textContent();
   await page.evaluate(()=>{go(DAY,'video');cmpLoad(ALL[0],ALL[1]);});
   const compare=await page.locator('#capA').textContent();
   for(const [surface,text] of [['單拍',detail],['列表',list],['比較',compare]]){
    if(!text.includes(message)||text.includes('差太多')||text.includes('不準'))failures.push(`${engine.name()} ${surface}: ${text}`);
   }
   const old=await page.evaluate(()=>({normal:kneeWarn({}),view:kneeWarn({knee_warn:true,knee_warn_why:'view'}),gap:kneeWarn({knee_warn:true,knee_warn_why:'gap',knee3d:120,knee2d:150})}));
   assert.equal(old.normal,'');assert(old.view.includes('鏡頭在正前或正後方'));assert(old.gap.includes('3D估 120° 與 2D 150° 差太多'));
   assert.deepEqual(errors,[]);
   console.log(engine.name()+': 接觸格原因三處DOM已檢查');
  }finally{await browser.close();}
 }
}finally{await f.close();}
assert.deepEqual(failures,[]);
