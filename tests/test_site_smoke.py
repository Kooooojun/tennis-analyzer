# Playwright E2E runs locally only; the three-OS CI runs the synthetic build smoke without SITE_E2E_URL.
# Local E2E requires Node, playwright-core with Chromium/WebKit installed, and private session fixtures.
# Start: python tests/site_cache_server.py --root "$SITE_FIXTURE_ROOT" --log "$SITE_SERVER_LOG"
# Run: SITE_E2E_URL="$SITE_URL" PLAYWRIGHT_MODULE="$PW_MODULE" python tests/test_site_smoke.py
# Manual only (Chromium needs a headed window, so they cannot run unattended):
# Background: add SITE_SERVER_LOG="$SITE_SERVER_LOG"; run node tests/site_cache_background.mjs,
# then repeat with SITE_ENGINE=webkit (Chromium needs a headed browser or SITE_CHROMIUM_EXECUTABLE).
# Playing background: same env plus SITE_CHROMIUM_EXECUTABLE if needed; run
# node tests/site_cache_playing_background.mjs (25 s per policy and engine, includes native-pause simulation).
# Drip (1 KiB / 2 s native fallback, about 60 s) runs below when SITE_SERVER_LOG is set, because it reads that log.
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
    assert(await page.evaluate(()=>v.playbackRate===rate),'loading a source must preserve the selected speed');
    const first=await page.evaluate(()=>S.id);
    await page.evaluate(()=>step(1)); await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
    await page.waitForFunction(id=>CLIPS.get(clipSrc(ALL[id]))?.url,first);
    const target=await page.evaluate(id=>new URL(clipSrc(ALL[id]),location.href).href,first), before=requests.filter(u=>u===target).length;
    await page.evaluate(()=>step(-1)); await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
    assert.equal(requests.filter(u=>u===target).length,before,'revisit must not fetch the clip');
    const advance=await page.evaluate(async()=>{v.currentTime=0;v.playbackRate=1;v._want=v._resume=true;await v.play();const t=v.currentTime;await new Promise(r=>setTimeout(r,250));v.pause();return v.currentTime-t;});
    assert(advance>0,'cached clip must play');
    await page.evaluate(()=>go(DAY,'video')); await page.locator('#vA').scrollIntoViewIfNeeded();
    await page.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
    await page.evaluate(async()=>{for(const s of ALL.slice(0,4))await clipFetch(clipSrc(s),true);});
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
    await page.route('**/*.mp4*',async route=>{await new Promise(r=>setTimeout(r,800));await route.continue().catch(()=>{});});
    await page.evaluate(()=>{S.src+='?cache-smoke=pending';load(S.id,false);});
    assert.equal(await page.locator('#play').textContent(),'▶ 播放','reset must update the button before async media events');
    await page.evaluate(()=>{toggle();toggle();});
    assert.equal(await page.evaluate(()=>v._want),false,'a second tap must cancel queued playback');
    await page.evaluate(()=>{toggle();goto(25);});
    assert.equal(await page.locator('#play').textContent(),'▶ 播放','seek must clear the queued-play button before a source exists');
    if(await page.locator('#speedCyc').isVisible()){for(let k=0;k<4&&await page.evaluate(()=>rate!==1);k++)await page.locator('#speedCyc').click();}
    else{await page.locator('#speeds button').last().click();}
    await page.waitForFunction(()=>v.readyState>=2&&!v._fetching);
    assert(await page.evaluate(()=>v.playbackRate===rate&&rate===1&&v.paused),'loading must use the latest speed and cancelled playback intent');
    await page.unroute('**/*.mp4*');
    await page.evaluate(()=>{window.frameCallbacks=new Set();const request=v.requestVideoFrameCallback?.bind(v),cancel=v.cancelVideoFrameCallback?.bind(v);if(request){v.requestVideoFrameCallback=fn=>{const id=request((...args)=>{frameCallbacks.delete(id);fn(...args);});frameCallbacks.add(id);return id;};v.cancelVideoFrameCallback=id=>{frameCallbacks.delete(id);cancel(id);};}toggle();});
    await page.waitForTimeout(100);
    await page.evaluate(()=>{v.dispatchEvent(new Event('playing'));v.dispatchEvent(new Event('playing'));});
    assert(await page.evaluate(()=>frameCallbacks.size<=1),'playing events must not multiply frame loops');
    await page.evaluate(()=>v.pause()); await page.waitForTimeout(50);
    assert.equal(await page.evaluate(()=>v._want),false,'native pause must clear viewer intent');
    await page.evaluate(()=>{filter='SV';pfilter='__empty_test__';preloadNeighbors(S);step(1);step(-1);});
    await page.waitForTimeout(50);
    assert.deepEqual(errors,[]);

    const fallback=await context.newPage();
    const sameClip=(url,target)=>{const u=new URL(url);u.searchParams.delete('_retry');return u.href===target;};
    await fallback.addInitScript(()=>{window.fetch=()=>Promise.reject(new TypeError('test fallback'));});
    await fallback.goto(process.env.SITE_E2E_URL);
    await fallback.evaluate(()=>go(DAY_KEYS[0],'stroke')); await fallback.waitForFunction(()=>v.readyState>=2);
    const failedURL=await fallback.evaluate(()=>{const list=visible(),i=list.findIndex(s=>s===S);return new URL(clipSrc(list[(i+1)%list.length]),location.href).href;});
    let release=false;
    await fallback.route('**/*.mp4*',async route=>{if(!release&&sameClip(route.request().url(),failedURL))await route.fulfill({status:503,body:''});else await route.continue();});
    await fallback.evaluate(()=>step(1)); await fallback.waitForFunction(()=>!!v.error); release=true;
    await fallback.waitForFunction(()=>v.readyState>=2&&!v.error);
    assert(await fallback.evaluate(()=>Math.abs(v.currentTime-(S.contact-48+.5)/FPS)<1/FPS),'automatic reload must preserve initial alignment');
    await fallback.unroute('**/*.mp4*');
    await fallback.route('**/*.mp4*',async route=>{await new Promise(r=>setTimeout(r,1000));await route.continue().catch(()=>{});});
    await fallback.evaluate(()=>step(1)); await fallback.waitForTimeout(100);
    await fallback.evaluate(()=>{toggle();go(DAY,'advice');}); await fallback.waitForTimeout(1400);
    assert(await fallback.evaluate(()=>v.paused&&!v._want),'leaving a tab must cancel pending playback before metadata');
    await fallback.unroute('**/*.mp4*');
    await fallback.evaluate(()=>go(DAY,'video')); await fallback.locator('#vA').scrollIntoViewIfNeeded();
    await fallback.waitForFunction(()=>vA.readyState>=2&&vB.readyState>=2);
    const failedB=await fallback.evaluate(()=>new URL(clipSrc(ALL[4]),location.href).href);let retryB=false;
    await fallback.route('**/*.mp4*',async route=>{if(!retryB&&sameClip(route.request().url(),failedB))await route.fulfill({status:503,body:''});else await route.continue();});
    await fallback.evaluate(()=>cmpLoad(ALL[3],ALL[4]));
    await fallback.waitForFunction(()=>!!vB.parentElement.querySelector('.vid-msg[data-fail]'));retryB=true;
    await fallback.locator('#cmpPlay').click(); await fallback.waitForFunction(()=>vB.readyState>=2&&!vB._reloading);
    assert(await fallback.evaluate(()=>vA.paused&&vB.paused&&Math.abs(vA.currentTime-(A.contact-48+.5)/FPS)<1/FPS),'paused comparison retry must finish initial alignment');
    await fallback.locator('#cmpPlay').click(); await fallback.waitForFunction(()=>!vA.paused&&!vB.paused);
    await fallback.evaluate(()=>vB.pause());await fallback.waitForTimeout(50);
    assert(await fallback.evaluate(()=>vA.paused&&vB.paused),'a native pause of B must pause both sides');
    await fallback.close();
    console.log(engine.name()+': clip cache E2E ok');
  }finally{await browser.close();}
}
''', text=True)

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_cache_regressions.mjs")], check=True)

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_cache_round4.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-round4"))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_cache_edges.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-edges"))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_cache_compare_edges.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-compare-edges"))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL"):
    for name in ["site_cache_compare_lifecycle", "site_cache_compare_visibility"]:
        subprocess.run(["node", str(R / "tests" / (name + ".mjs"))], check=True,
                       env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-" + name))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "test_site_i57_css.mjs")], check=True)
    subprocess.run(["node", str(R / "tests" / "test_site_i57_nav.mjs")], check=True)

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_cache_retry.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-retry"))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_i93_stuck.mjs")], check=True,
                   env={**os.environ, "SITE_ENGINES": "chromium,webkit", **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-i93"))} if os.environ.get("SITE_RESULTS") else {})})
    subprocess.run(["node", str(R / "tests" / "site_i97_loader.mjs")], check=True,
                   env={**os.environ, "SITE_ENGINES": "chromium,webkit", **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-i97"))} if os.environ.get("SITE_RESULTS") else {})})
    subprocess.run(["node", str(R / "tests" / "site_cache_keyboard.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-keyboard"))} if os.environ.get("SITE_RESULTS") else {})})
    subprocess.run(["node", str(R / "tests" / "test_site_i57_mobile.mjs")], check=True)
    subprocess.run(["node", str(R / "tests" / "site_contact_height.mjs")], check=True)
    subprocess.run(["node", str(R / "tests" / "site_i57_final.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-i57-final"))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL"):
    subprocess.run(["node", str(R / "tests" / "site_contact_untrusted.mjs")], check=True)
    subprocess.run(["node", str(R / "tests" / "site_i112_web.mjs")], check=True)
    # Without SITE_E2E_URL these build their own synthetic fixture; with it they expect a real two-session copy.
    for name in ["site_advice_uncertainty", "site_score_uncertainty", "site_score_count", "site_knee_estimate"]:
        subprocess.run(["node", str(R / "tests" / (name + ".mjs"))], check=True,
                       env={**{k: v for k, v in os.environ.items() if k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-" + name))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL") and os.environ.get("SITE_SERVER_LOG"):
    subprocess.run(["node", str(R / "tests" / "site_cache_drip.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-drip"))} if os.environ.get("SITE_RESULTS") else {})})
elif os.environ.get("SITE_E2E_URL"):
    print("skipped site_cache_drip.mjs: set SITE_SERVER_LOG to the log passed to site_cache_server.py")
