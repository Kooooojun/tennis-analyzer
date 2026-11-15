# Run: .venv/bin/python tests/test_site_smoke.py   (plain asserts; cases follow testset/results/cross-platform_pred.md)
# Builds a synthetic session (Chinese name and notes, no real data) with build_site.py in a scratch copy of tools/, under the
# default locale and again with a cp1252 stdout, and checks data.js is UTF-8 with LF only and the ?v= hash matches the file bytes.
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

R = Path(__file__).resolve().parent.parent
T = Path(tempfile.mkdtemp()) / "根目錄"; shutil.copytree(R / "tools", T / "tools", ignore=shutil.ignore_patterns("__pycache__"))
s = "練習-1"; D = T / "web" / "sessions" / s; D.mkdir(parents=True); (T / "work" / s).mkdir(parents=True)
fr = [[[0.5, 0.5, 0.9]] * 17] * 3
strokes = [dict(id=i, video="v1", src="clips/s.mp4", frames=fr, world=fr, kind="FH", player="小明") for i in (1, 2)]
(D / "strokes.json").write_text(json.dumps(strokes, ensure_ascii=False), encoding="utf-8")
(D / "notes.json").write_text(json.dumps(dict(label="中文標題", date="2020-01-02", caveat="備註：只有合成資料", findings=[dict(title="重心", text="膝蓋再彎一點")]),
                                         ensure_ascii=False), encoding="utf-8")

for env in ({}, {"PYTHONIOENCODING": "cp1252"}):
    e = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}; e.update(env)
    r = subprocess.run([sys.executable, str(T / "tools" / "build_site.py")], capture_output=True, env=e)
    assert r.returncode == 0, (env, r.stderr.decode("utf-8", "replace"))
    b = (D / "data.js").read_bytes()
    assert b"\r" not in b
    js = b.decode("utf-8"); assert "中文標題" in js and "膝蓋再彎一點" in js and "小明" in js
    assert json.loads(js[js.index("push(") + 5:-2])["date"] == "2020-01-02"  # the page titles and spaces sessions by this date
    h = hashlib.sha1(b)
    for x in strokes: h.update((D / "pose" / f"{x['id']}.js").read_bytes())
    man = (T / "web" / "sessions" / "manifest.js").read_text(encoding="utf-8")
    ver = json.loads(re.search(r"SESSION_VER=(\{.*?\});", man).group(1))
    assert ver[s] == h.hexdigest()[:10], (ver, h.hexdigest())
shutil.rmtree(T.parent)
print("ok")

# Optional real-clip E2E: set SITE_E2E_URL and PLAYWRIGHT_MODULE; the normal build smoke stays dependency-free.
if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", "--input-type=module", "-"], check=True, input=r'''
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {chromium,webkit,devices}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
for(const engine of [chromium,webkit]){
  const browser=await engine.launch({headless:true});
  try{
    const context=await browser.newContext(engine===webkit?devices['iPhone 13']:{});
    const page=await context.newPage(), requests=[], errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('.mp4')) requests.push(r.url());});
    await page.addInitScript(()=>{
      window.liveClips=new Map(); window.revokedActive=0;
      const create=URL.createObjectURL,revoke=URL.revokeObjectURL;
      URL.createObjectURL=b=>{const u=create(b); liveClips.set(u,b.size); return u;};
      URL.revokeObjectURL=u=>{if([...document.querySelectorAll('video')].some(v=>v.src===u)) revokedActive++; liveClips.delete(u); revoke(u);};
    });
    if(engine===chromium){const cdp=await context.newCDPSession(page); await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:50,downloadThroughput:1250000,uploadThroughput:1250000});}
    await page.goto(process.env.SITE_E2E_URL);
    await page.evaluate(()=>go(DAY_KEYS.reduce((a,b)=>DAYS[a].data.length>DAYS[b].data.length?a:b),'stroke'));
    await page.waitForFunction(()=>S&&v.readyState>=2&&!v._fetching);
    const first=await page.evaluate(()=>S.id);
    await page.evaluate(()=>step(1)); await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
    await page.waitForTimeout(1000);
    const target=await page.evaluate(id=>new URL(clipSrc(ALL[id]),location.href).href,first), before=requests.filter(u=>u===target).length;
    await page.evaluate(()=>step(-1)); await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
    assert.equal(requests.filter(u=>u===target).length,before,'revisit must not fetch the clip');
    const advance=await page.evaluate(async()=>{const t=v.currentTime;await v.play();await new Promise(r=>setTimeout(r,250));v.pause();return v.currentTime-t;});
    assert(advance>0,'cached clip must play');
    await page.evaluate(()=>go(DAY,'video')); await page.locator('#vA').scrollIntoViewIfNeeded();
    await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
    await page.evaluate(()=>cmpLoad(ALL[0],ALL[1])); await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
    await page.evaluate(()=>cmpLoad(ALL[2],ALL[3])); await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
    const cmpBefore=requests.length;
    await page.evaluate(()=>cmpLoad(ALL[0],ALL[1])); await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
    assert.equal(requests.length,cmpBefore,'cached comparison must not fetch either clip');
    for(let i=0;i<40;i++){
      await page.evaluate(i=>load(i%ALL.length,false),i); await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
      assert(await page.evaluate(()=>[...liveClips.values()].reduce((n,b)=>n+b,0)<=CLIP_LIMIT),'live blob bytes exceed budget');
    }
    assert.equal(await page.evaluate(()=>revokedActive),0,'active clip was revoked');
    assert.deepEqual(errors,[]);
    console.log(engine.name()+': clip cache E2E ok');
  }finally{await browser.close();}
}
''', text=True)
