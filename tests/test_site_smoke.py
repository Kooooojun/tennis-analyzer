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
(D / "notes.json").write_text(json.dumps(dict(label="中文標題", date="2020-01-02", caveat="備註：只有合成資料", findings=[dict(title="重心", text="膝蓋再彎一點")],
                                         overall=[dict(player="小明", insufficient=dict(title="資料不足以給方向"), film_next="側面拍")]),
                                         ensure_ascii=False), encoding="utf-8")

for env in ({}, {"PYTHONIOENCODING": "cp1252"}):
    e = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}; e.update(env)
    r = subprocess.run([sys.executable, str(T / "tools" / "build_site.py")], capture_output=True, env=e)
    assert r.returncode == 0, (env, r.stderr.decode("utf-8", "replace"))
    b = (D / "data.js").read_bytes()
    assert b"\r" not in b
    js = b.decode("utf-8"); assert "中文標題" in js and "膝蓋再彎一點" in js and "小明" in js
    assert json.loads(js[js.index("push(") + 5:-2])["date"] == "2020-01-02"  # the page titles and spaces sessions by this date
    assert json.loads(js[js.index("push(") + 5:-2])["overall"][0]["film_next"] == "側面拍"  # notes.json overall goes to data.js as is (docs/advice.md)
    h = hashlib.sha1(b)
    for x in strokes: h.update((D / "pose" / f"{x['id']}.js").read_bytes())
    man = (T / "web" / "sessions" / "manifest.js").read_text(encoding="utf-8")
    ver = json.loads(re.search(r"SESSION_VER=(\{.*?\});", man).group(1))
    assert ver[s] == h.hexdigest()[:10], (ver, h.hexdigest())

# methodVer (prep's versions.txt -> the page's method note): no file = null (old session, "未記錄"), never a crash
def built_ver():
    r = subprocess.run([sys.executable, str(T / "tools" / "build_site.py")], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    js = (D / "data.js").read_text(encoding="utf-8")
    return json.loads(js[js.index("push(") + 5:-2])["methodVer"]
assert built_ver() is None
vid = lambda n, txt: ((T / "work" / s / n).mkdir(), (T / "work" / s / n / "versions.txt").write_text(txt, encoding="utf-8"))
base = "mediapipe=1.1.1\npose_model=pose_heavy.task\npose_model_sha256=" + "ab" * 32 + "\npose_model_url=https://example.invalid/m.task\npose_method=4\n"
vid("v1", base + "pose_frames=100\npose_detected=80\npose_interpolated=10\n")
(T / "work" / s / "v2").mkdir(); (T / "work" / s / "v2" / "versions.txt").write_text("garbage\n\n=\npose_frames=abc\n", encoding="utf-8")  # unreadable: counts as not recorded
m = built_ver()
assert m == dict(mediapipe="1.1.1", model="pose_heavy.task", sha256="ab" * 32, url="https://example.invalid/m.task", method="4",
                 frames=100, detected=80, interpolated=10, videos=2, recorded=1), m
vid("v3", base.replace("1.1.1", "1.2.0") + "pose_frames=50\npose_detected=40\npose_interpolated=0\n")
m = built_ver()
assert (m["mediapipe"], m["frames"], m["detected"], m["interpolated"], m["videos"], m["recorded"]) == ("1.1.1 / 1.2.0", 150, 120, 10, 3, 2), m
# a versions.txt that is not UTF-8 (saved by another tool) is "not recorded", never a crash of the whole build; videos.json decides which folders count
(T / "work" / s / "v2" / "versions.txt").write_bytes(b"\xff\xfem\x00e\x00")
(T / "work" / s / "old").mkdir(); (T / "work" / s / "videos.json").write_text('["v1", "v2", "v3"]', encoding="utf-8")  # "old" is a folder of a removed video
m = built_ver()
assert (m["videos"], m["recorded"]) == (3, 2), m
# a count that only looks like digits (superscript two: str.isdigit() is True, int() raises) is "not recorded", never a crash of the whole build
good3 = (T / "work" / s / "v3" / "versions.txt").read_text(encoding="utf-8")
(T / "work" / s / "v3" / "versions.txt").write_text(good3.replace("pose_interpolated=0", "pose_interpolated=\u00b2"), encoding="utf-8")
m = built_ver(); assert (m["videos"], m["recorded"], m["frames"]) == (3, 1, 100), m
(T / "work" / s / "v1" / "versions.txt").write_text(base + "pose_frames=100\npose_detected=\u00b2\npose_interpolated=10\n", encoding="utf-8")
assert built_ver() is None  # no readable record left
(T / "work" / s / "v3" / "versions.txt").write_text(good3, encoding="utf-8")
# an empty or broken videos.json does not stop the build either: the page folders are counted instead (v1 is still unreadable, v2 non-UTF-8, v3 fine)
for bad in ("", "{not json", "\xff"):
    (T / "work" / s / "videos.json").write_text(bad, encoding="utf-8", errors="surrogateescape")
    m = built_ver(); assert (m["videos"], m["recorded"]) == (4, 1), (bad, m)  # v1, v2, v3 and the leftover "old"
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
    await page.locator('#speed').selectOption('1');
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
    await fallback.evaluate(()=>{toggle();location.hash='#home';}); await fallback.waitForTimeout(1400);
    assert(await fallback.evaluate(()=>v.paused&&!v._want),'leaving the session page must cancel pending playback before metadata');  // one page (UI A5): the player only leaves the screen on #home
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
    # site_card_medians 驗新行為，在 SITE_REF（修改前的網頁）上本來就會失敗，所以只在跑工作區網頁時執行。
    # site_method_notes 同理（#146 的做法）：驗方法說明與單拍格數的新行為，舊網頁上必紅。
    # site_trend_per_player 同理（#152）：每位球員各一張比較表，舊網頁混在一起，必紅。
    # site_drill_diff_cite 同理（#159）：drill_diff 引用的小標籤，舊網頁顯示 undefined，必紅；只跑合成場次（真實副本沒有這種引用）。
    if os.environ.get("SITE_REF"): print("skipped site_card_medians.mjs, site_method_notes.mjs, site_trend_per_player.mjs, site_drill_diff_cite.mjs: they check new behaviour, SITE_REF runs the old page")
    for name in ["site_advice_uncertainty", "site_score_uncertainty", "site_score_count", "site_knee_estimate"] + ([] if os.environ.get("SITE_REF") else ["site_card_medians", "site_method_notes", "site_trend_per_player", "site_drill_diff_cite"]):
        subprocess.run(["node", str(R / "tests" / (name + ".mjs"))], check=True,
                       env={**{k: v for k, v in os.environ.items() if k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-" + name))} if os.environ.get("SITE_RESULTS") else {})})
    # 3D replay (#145): synthetic skeletons first, then the real session copy at SITE_E2E_URL; like site_card_medians, not on SITE_REF (the page before it).
    if os.environ.get("SITE_REF"): print("skipped site_replay3d.mjs: it checks new behaviour, SITE_REF runs the old page")
    for real in () if os.environ.get("SITE_REF") else (False, True):
        subprocess.run(["node", str(R / "tests" / "site_replay3d.mjs")], check=True,
                       env={**{k: v for k, v in os.environ.items() if real or k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + ("-replay3d-real" if real else "-replay3d")))} if os.environ.get("SITE_RESULTS") else {})})
    # 整體建議卡片（UI 方案 A1）：先合成場次，再跑真實副本（有 overall 的場次顯示卡片、沒有的不顯示）；舊網頁（SITE_REF）沒有卡片，必紅，所以跳過。
    if os.environ.get("SITE_REF"): print("skipped site_overall_card.mjs: it checks new behaviour, SITE_REF runs the old page")
    for real in () if os.environ.get("SITE_REF") else (False, True):
        subprocess.run(["node", str(R / "tests" / "site_overall_card.mjs")], check=True,
                       env={**{k: v for k, v in os.environ.items() if real or k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + ("-overall-card-real" if real else "-overall-card")))} if os.environ.get("SITE_RESULTS") else {})})
    # 拍子列只列相關拍（UI 方案 A 第 2 步）：同上，合成場次先、真實副本後；舊網頁（SITE_REF）沒有開關，必紅，所以跳過。
    if os.environ.get("SITE_REF"): print("skipped site_stroke_row.mjs: it checks new behaviour, SITE_REF runs the old page")
    for real in () if os.environ.get("SITE_REF") else (False, True):
        subprocess.run(["node", str(R / "tests" / "site_stroke_row.mjs")], check=True,
                       env={**{k: v for k, v in os.environ.items() if real or k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + ("-stroke-row-real" if real else "-stroke-row")))} if os.environ.get("SITE_RESULTS") else {})})
    # 控制列收斂（UI 方案 A 第 3 步）：同上，合成場次先、真實副本後；舊網頁（SITE_REF）沒有新控制項，必紅，所以跳過。
    if os.environ.get("SITE_REF"): print("skipped site_controls.mjs: it checks new behaviour, SITE_REF runs the old page")
    for real in () if os.environ.get("SITE_REF") else (False, True):
        subprocess.run(["node", str(R / "tests" / "site_controls.mjs")], check=True,
                       env={**{k: v for k, v in os.environ.items() if real or k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + ("-controls-real" if real else "-controls")))} if os.environ.get("SITE_RESULTS") else {})})
    # 一場一頁（UI 方案 A 第 5 步）：同上，合成場次先、真實副本後；舊網頁（SITE_REF）還有分頁，必紅，所以跳過。
    if os.environ.get("SITE_REF"): print("skipped site_one_page.mjs: it checks new behaviour, SITE_REF runs the old page")
    for real in () if os.environ.get("SITE_REF") else (False, True):
        subprocess.run(["node", str(R / "tests" / "site_one_page.mjs")], check=True,
                       env={**{k: v for k, v in os.environ.items() if real or k != "SITE_E2E_URL"}, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + ("-one-page-real" if real else "-one-page")))} if os.environ.get("SITE_RESULTS") else {})})
    if not os.environ.get("SITE_REF"):  # 真實副本：每張表每一欄的拍數對 data.js（這支另外用 SITE_E2E_URL 跑一次）
        subprocess.run(["node", str(R / "tests" / "site_trend_per_player.mjs")], check=True,
                       env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-site_trend_per_player-real"))} if os.environ.get("SITE_RESULTS") else {})})

if os.environ.get("SITE_E2E_URL") and os.environ.get("SITE_SERVER_LOG"):
    subprocess.run(["node", str(R / "tests" / "site_cache_drip.mjs")], check=True,
                   env={**os.environ, **({"SITE_RESULTS": str(Path(os.environ["SITE_RESULTS"]).with_stem(Path(os.environ["SITE_RESULTS"]).stem + "-drip"))} if os.environ.get("SITE_RESULTS") else {})})
elif os.environ.get("SITE_E2E_URL"):
    print("skipped site_cache_drip.mjs: set SITE_SERVER_LOG to the log passed to site_cache_server.py")
