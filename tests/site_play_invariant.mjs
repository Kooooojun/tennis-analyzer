// #142：不依賴瀏覽器時序，檢查紀錄器零取樣、最後一次取樣及按鈕寫入。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {watchPlay,playMismatch} from './site_i93_fixture.mjs';

function fixture(){
 const elements={play:{textContent:'▶ 播放'},cmpPlay:{textContent:'▶ 同步播放'},v:{},vA:{}};
 let frame;
 const raf=fn=>{frame=fn;};
 raf.toString=()=> 'function requestAnimationFrame() { [native code] }';
 const ctx=vm.createContext({document:{getElementById:id=>elements[id]},requestAnimationFrame:raf,performance:{now:()=>0}});
 ctx.window=ctx;
 const evaluate=fn=>vm.runInContext(`(${fn})()`,ctx);
 return {elements,ctx,page:{addInitScript:evaluate,evaluate},sample:()=>frame()};
}

test('沒有排程取樣的紀錄會失敗',async()=>{
 const f=fixture();await watchPlay(f.page);
 await assert.rejects(async()=>playMismatch(f.page),/取樣/);
});

test('讀取時抓到上一個影格後才出現的比較鈕不一致',async()=>{
 const f=fixture();await watchPlay(f.page);f.sample();
 f.elements.vA._want=true;
 const play=await playMismatch(f.page);
 assert.equal(play.count,1);
 assert.equal(play.first[0].button,'cmpPlay');
});

test('同步播放鈕只改寫變更的文字',()=>{
 const {elements,ctx}=fixture(),writes=[];
 for(const id of ['play','cmpPlay']){
  let text=elements[id].textContent;
  Object.defineProperty(elements[id],'textContent',{get:()=>text,set:value=>{text=value;writes.push([id,value]);}});
 }
 Object.assign(ctx,{v:elements.v,$:id=>elements[id]});
 const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
 vm.runInContext(html.slice(html.indexOf('const syncPlay='),html.indexOf('const hold=vid')),ctx);
 vm.runInContext('syncPlay()',ctx);
 assert.deepEqual(writes,[]);
 elements.vA._want=true;
 vm.runInContext('syncPlay();syncPlay()',ctx);
 assert.deepEqual(writes,[['cmpPlay','⏸ 暫停']]);
 elements.v._want=true;
 vm.runInContext('syncPlay()',ctx);
 assert.deepEqual(writes.at(-1),['play','⏸ 暫停']);
 assert.equal(writes.length,2);
});
