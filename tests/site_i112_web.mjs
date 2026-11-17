// #112：兩處顯示回歸；只用合成資料，截圖選擇性留在本機。
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './site_i93_fixture.mjs';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const f=await fixture(), failures=[], part=process.env.SITE_I112_PART;
try{
 for(const engine of [chromium,webkit])for(const mobile of [false,true]){
  const browser=await engine.launch();
  try{
   const context=await browser.newContext(mobile?devices['iPhone 13']:{viewport:{width:1280,height:800}}),page=await context.newPage(),tag=`${engine.name()} ${mobile?'手機':'桌機'}`,errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(f.url);await page.waitForSelector('body.ready');
   if(part!=='arm'){
    const results=await page.evaluate(()=>{
     const old={session:DAY_KEYS[0],date:'2026-01-01',camera:'側面',knee_src:'knee',score_version:10,items:{total:6,consistency:7}},
       single={...old,date:'2026-01-02',form_n:1,form_metrics:['prep'],score_set:[['prep','total'],['prep']],items:{total:8,consistency:8}},
       normal={...single,form_n:2,form_metrics:['knee','prep'],score_set:[['knee','prep','total'],['prep']]};
     const cases=[
      ['舊→單項',[old,single],1,true],['單項→舊',[single,{...old,date:'2026-01-03'}],1,true],
      ['單項→單項',[single,{...single,date:'2026-01-03'}],1,true],
      ['不同集合',[normal,{...single,date:'2026-01-03'}],0,true],
      ['多項→多項',[normal,{...normal,date:'2026-01-03'}],1,false],
      ['空值間隔',[old,{...old,items:{total:null,consistency:null}},single],1,true],
      ['不同機位',[old,{...single,camera:'另一機位'}],0,true],
      ['不同版本',[old,{...single,score_version:9}],0,true]
     ];
     $('home').innerHTML='';
     return cases.map(([label,history,count,neutral])=>{
      const card=document.createElement('div');card.className='card';card.innerHTML=`<h2>${label}</h2><svg class="spark"></svg>`;$('home').append(card);
      const svg=card.querySelector('svg');drawSpark(svg,{history});
      const lines=[...svg.querySelectorAll('polyline')].filter(p=>p.getAttribute('stroke-width')==='2.5');
      return {label,count,neutral,colors:lines.map(p=>p.getAttribute('stroke')),notes:card.textContent};
     });
    });
    for(const r of results){
     if(r.colors.length!==r.count||r.colors.some(c=>c!==(r.neutral?'var(--muted)':'var(--accent)')))failures.push(`${tag} ${r.label}：預期 ${r.count} 條${r.neutral?'中性':'原色'}總分線，實際 ${r.colors}`);
     if(r.label==='不同集合'&&!r.notes.includes('項目不同'))failures.push(`${tag}：缺採計差異提示`);
    }
    if(process.env.SITE_RESULTS)await page.screenshot({path:`${process.env.SITE_RESULTS}-${engine.name()}-${mobile?'mobile':'desktop'}-trend.png`,fullPage:true});
   }
   if(part!=='trend'){
    const cases=[
     ['接觸不可信',{contact_untrusted:true,serve_arm_conf:null},'擊球格不可信'],
     ['接觸不可信優先於殘留值',{contact_untrusted:true,serve_arm_conf:.9,serve_arm_straight:true},'擊球格不可信'],
     ['未知舊資料',{},'沒有資料'],
     ['只有殘留判定沒有信心',{serve_arm_straight:true},'沒有資料'],
     ['已知缺3D',{world:null,serve_arm_conf:0},'缺 3D 骨架'],
     ['片段不足',{contact:0,n:2,serve_arm_conf:0},'資料不足'],
     ['品質閘門未存原因',{serve_arm_conf:.2},'沒有資料'],
     ['不確定帶未存原因',{serve_arm_conf:.9},'沒有資料'],
     ['正常伸直',{serve_arm_conf:.9,serve_arm_straight:true},'手臂看起來接近伸直'],
     ['正常偏彎',{serve_arm_conf:.9,serve_arm_straight:false},'手臂看起來偏彎']
    ];
    for(const [label,fields,expected] of cases){
     await page.evaluate(fields=>{
      const s=ALL[0];for(const k of ['contact_untrusted','serve_arm_conf','serve_arm_straight','world','frames','bh_elbow_conf'])delete s[k];
      Object.assign(s,{kind:'SV',contact:90,n:180,serve_arm_straight:null},fields);
      go(DAY_KEYS[0],'stroke');load(0,false);
     },fields);
     const text=(await page.locator('#mElbow').textContent())+' '+(await page.locator('#cElbow').textContent());
     if(!text.includes(expected)||text.includes('視角不夠'))failures.push(`${tag} ${label}：預期 ${expected}，實際 ${text}`);
     if(label==='接觸不可信'&&process.env.SITE_RESULTS){
      await page.locator('#mElbow').evaluate((e,mobile)=>window.scrollTo(0,e.closest('.metric').getBoundingClientRect().top+scrollY-(mobile?document.querySelector('.player').getBoundingClientRect().height+16:120)),mobile);
      await page.screenshot({path:`${process.env.SITE_RESULTS}-${engine.name()}-${mobile?'mobile':'desktop'}-arm.png`});
     }
    }
    await page.evaluate(()=>{Object.assign(ALL[0],{kind:'FH',serve_arm_conf:null,contact_untrusted:false});load(0,false);});
    if(!(await page.locator('#cElbow').textContent()).includes('正手與雙手反拍不評手肘'))failures.push(`${tag}：正手說明退步`);
   }
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))failures.push(`${tag}：水平溢出`);
   if(errors.length)failures.push(`${tag}：前端例外 ${errors}`);
   console.log(`${tag}：${part||'走勢與手臂'} 驗證完成`);
  }finally{await browser.close();}
 }
}finally{await f.close();}
assert.deepEqual(failures,[]);
