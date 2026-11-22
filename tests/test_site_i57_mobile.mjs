// Playwright E2E tests for #57 PR 3 (mobile portrait player space, compare select optgroups, "use current stroke" buttons).
// Run against local server: SITE_E2E_URL=... PLAYWRIGHT_MODULE=... node tests/test_site_i57_mobile.mjs
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const { chromium, webkit, devices } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const URL = process.env.SITE_E2E_URL;
assert(URL, "SITE_E2E_URL is required");

function parseRgb(str) {
  const m = str && str.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/);
  if (!m) return null;
  return { r: +m[1], g: +m[2], b: +m[3], a: m[4] !== undefined ? +m[4] : 1 };
}
function relLum({ r, g, b }) {
  const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function contrast(fg, bg) {
  const l1 = relLum(fg), l2 = relLum(bg);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

// 1. WebKit 390x844 portrait: scrolling to compare & stroke list leaves .player height <= 60% vh (for 16:9), no horizontal overflow;
//    and WebKit 844x390 landscape keeps exact main layout dimensions.
{
  const browser = await webkit.launch({ headless: true });
  try {
    const iPhone = devices["iPhone 13"];
    const ctx = await browser.newContext({ ...iPhone, viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.goto(URL, { waitUntil: "networkidle" });
    await page.waitForSelector("body.ready");

    // Choose the session with the most strokes
    const richDay = await page.evaluate(() => [...DAY_KEYS].sort((a, b) => DAYS[b].data.length - DAYS[a].data.length)[0]);
    await page.evaluate(k => go(k, "video"), richDay);
    await page.waitForFunction(() => S && v.readyState >= 2);

    // Portrait .controls: all visible buttons fit within viewport without horizontal scroll, and speed select works (4 selections = back to start)
    const ctlCheck = await page.evaluate(() => {
      const ctl = document.querySelector(".player .controls");
      const btns = [...ctl.querySelectorAll("button")].filter(b => getComputedStyle(b).display !== "none" && b.offsetParent !== null);
      const out = btns.map(b => {
        const r = b.getBoundingClientRect();
        return { id: b.id || b.textContent, left: r.left, right: r.right, width: r.width };
      }).filter(x => x.left < -0.5 || x.right > window.innerWidth + 0.5);
      return {
        scrollW: ctl.scrollWidth,
        clientW: ctl.clientWidth,
        outOfView: out,
        btnCount: btns.length,
      };
    });
    assert(ctlCheck.scrollW <= ctlCheck.clientW,
      `portrait .controls must not scroll horizontally: scrollWidth=${ctlCheck.scrollW} > clientWidth=${ctlCheck.clientW}`);
    assert.equal(ctlCheck.outOfView.length, 0,
      `portrait .controls buttons must all be inside viewport: ${JSON.stringify(ctlCheck.outOfView)}`);

    // 速度是一顆下拉（UI 方案 A 第 3 步取代 4 顆鈕與輪流切換鈕）：4 個值各選一次，playbackRate 要跟著，最後回到起點
    const speed = page.locator("#speed");
    assert.equal(await speed.count(), 1, "#speed select must exist");
    assert(await speed.isVisible(), "#speed must be visible in mobile portrait");
    const initRate = await page.evaluate(() => v.playbackRate);
    const initVal = await speed.inputValue();
    const seenRates = [];
    for (const val of ["0.1", "0.5", "1", initVal]) {
      await speed.selectOption(val);
      seenRates.push(await page.evaluate(() => v.playbackRate));
    }
    assert.equal(new Set(seenRates).size, 4, `4 selections on #speed must give 4 distinct rates, got ${JSON.stringify(seenRates)}`);
    assert.equal(seenRates[3], initRate, `last selection must return playbackRate to ${initRate}, got ${seenRates[3]}`);
    assert.equal(await speed.inputValue(), initVal, `#speed must return to ${initVal}`);

    // Scroll to compare section (#selA / #vA)
    await page.evaluate(() => document.getElementById("selA").closest(".card").scrollIntoView({ block: "start" }));
    await page.waitForTimeout(200);
    const cmpPort = await page.evaluate(() => {
      const p = document.querySelector(".player");
      const r = p.getBoundingClientRect();
      const visH = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0));
      return {
        pos: getComputedStyle(p).position,
        is169: !!(S.size && S.size[0] / S.size[1] >= 1.7),
        top: r.top,
        bottom: r.bottom,
        h: r.height,
        visH,
        vh: window.innerHeight,
        ratio: r.height / window.innerHeight,
        scrollW: document.documentElement.scrollWidth,
        vw: window.innerWidth,
      };
    });
    assert(cmpPort.scrollW <= cmpPort.vw, `portrait video tab horizontal overflow: ${cmpPort.scrollW} > ${cmpPort.vw}`);
    assert.equal(cmpPort.pos, "sticky", `portrait .player must be sticky, got ${cmpPort.pos}`);
    assert(cmpPort.top >= -1 && cmpPort.bottom > 0 && cmpPort.visH > 0,
      `portrait .player must stay visible when scrolled to compare (top=${cmpPort.top}, bottom=${cmpPort.bottom})`);
    if (cmpPort.is169) {
      assert(cmpPort.h <= cmpPort.vh * 0.6,
        `portrait .player height at compare (${cmpPort.h.toFixed(1)}px = ${(cmpPort.ratio * 100).toFixed(1)}%) must be <= 60% of ${cmpPort.vh}px`);
    }

    // Scroll down on stroke tab, check sticky .player <= 60% (for 16:9 clips) and visible, then click 2nd stroke and verify scrollY != 0
    await page.evaluate(k => go(k, "stroke"), richDay);
    await page.waitForTimeout(200);
    await page.evaluate(() => window.scrollTo(0, 120));
    await page.waitForTimeout(200);
    const strokePort = await page.evaluate(() => {
      const p = document.querySelector(".player");
      const r = p.getBoundingClientRect();
      const visH = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0));
      return {
        pos: getComputedStyle(p).position,
        is169: !!(S.size && S.size[0] / S.size[1] >= 1.7),
        top: r.top,
        bottom: r.bottom,
        h: r.height,
        visH,
        vh: window.innerHeight,
        ratio: r.height / window.innerHeight,
        scrollW: document.documentElement.scrollWidth,
        vw: window.innerWidth,
        scrollY: window.scrollY,
      };
    });
    assert(strokePort.scrollW <= strokePort.vw, `portrait stroke tab horizontal overflow: ${strokePort.scrollW} > ${strokePort.vw}`);
    assert.equal(strokePort.pos, "sticky", `portrait .player on stroke tab must be sticky, got ${strokePort.pos}`);
    assert(strokePort.top >= -1 && strokePort.bottom > 0 && strokePort.visH > 0,
      `portrait .player must stay visible at stroke list (top=${strokePort.top}, bottom=${strokePort.bottom})`);
    if (strokePort.is169) {
      assert(strokePort.h <= strokePort.vh * 0.6,
        `portrait .player height at stroke list (${strokePort.h.toFixed(1)}px = ${(strokePort.ratio * 100).toFixed(1)}%) must be <= 60% of ${strokePort.vh}px`);
    }

    // Click 2nd stroke in list (if >= 2 strokes) -> scrollY must NOT reset to 0
    if (await page.locator(".strokes button").count() >= 2) {
      await page.locator(".strokes button").nth(1).click();
      await page.waitForTimeout(350);
      const afterListClickScrollY = await page.evaluate(() => window.scrollY);
      assert(afterListClickScrollY > 0, `clicking 2nd stroke in list must not reset scrollY to 0 (got ${afterListClickScrollY})`);
    }

    // Scroll to #chart on stroke tab (positioned below sticky .player), click to jump -> main video currentTime changes and .player stays visible
    await page.evaluate(() => {
      const el = document.getElementById("chart");
      const pBottom = document.querySelector(".player").getBoundingClientRect().bottom;
      const y = el.getBoundingClientRect().top + window.scrollY - pBottom - 24;
      window.scrollTo(0, Math.max(0, y));
    });
    await page.waitForTimeout(200);
    const beforeJumpT = await page.evaluate(() => v.currentTime);
    const chartBox = await page.locator("#chart").boundingBox();
    assert(chartBox && chartBox.width > 0, "#chart must have bounding box");
    await page.mouse.click(chartBox.x + chartBox.width * 0.2, chartBox.y + chartBox.height * 0.5);
    await page.waitForTimeout(200);
    const afterJump = await page.evaluate(() => {
      const r = document.querySelector(".player").getBoundingClientRect();
      return { t: v.currentTime, top: r.top, bottom: r.bottom, vh: window.innerHeight };
    });
    assert(Math.abs(afterJump.t - beforeJumpT) > 0.01,
      `clicking #chart jump must change v.currentTime (before=${beforeJumpT}, after=${afterJump.t})`);
    assert(afterJump.top >= -1 && afterJump.bottom > 0 && afterJump.bottom <= afterJump.vh,
      `.player must stay in viewport after #chart jump (top=${afterJump.top}, bottom=${afterJump.bottom})`);

    // 2a. WebKit 844x390 landscape: .player and .stage dimensions match main (<= 1px tolerance)
    await page.setViewportSize({ width: 844, height: 390 });
    await page.evaluate(() => go(DAY_KEYS[0], "video"));
    await page.waitForTimeout(250);
    const land = await page.evaluate(() => {
      const p = document.querySelector(".player").getBoundingClientRect();
      const st = document.getElementById("stage").getBoundingClientRect();
      const wide = document.querySelector(".player").classList.contains("wide");
      const sz = S.size || [9, 16];
      const ar = sz[0] / sz[1];
      const expStageH = wide ? Math.min(window.innerWidth * 0.55, (window.innerHeight - 24) * 16 / 9) / ar : window.innerHeight - 24;
      const expStageW = wide ? Math.min(window.innerWidth * 0.55, (window.innerHeight - 24) * 16 / 9) : expStageH * ar;
      return {
        pos: getComputedStyle(document.querySelector(".player")).position,
        display: getComputedStyle(document.querySelector(".player")).display,
        pw: p.width, sw: st.width, sh: st.height,
        expStageW, expStageH,
        scrollW: document.documentElement.scrollWidth,
        vw: window.innerWidth,
      };
    });
    assert.equal(land.pos, "static", "landscape .player must stay static");
    assert.equal(land.display, "grid", "landscape .player must stay grid");
    assert(Math.abs(land.sw - land.expStageW) <= 1, `landscape .stage width ${land.sw} != expected ${land.expStageW}`);
    assert(Math.abs(land.sh - land.expStageH) <= 1, `landscape .stage height ${land.sh} != expected ${land.expStageH}`);
    assert(land.scrollW <= land.vw, `landscape horizontal overflow: ${land.scrollW} > ${land.vw}`);

    // 3 & 4. Check #selA/#selB optgroups & "帶入目前這一拍" buttons on mobile
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => go(DAY_KEYS[0], "video"));
    await page.waitForFunction(() => S && v.readyState >= 2);
    await page.locator("#vA").scrollIntoViewIfNeeded();
    await page.waitForFunction(() => vA.readyState >= 2 && vB.readyState >= 2);

    const selInfo = await page.evaluate(() => {
      const expected = DAY_KEYS.map(k => ({
        label: DAYS[k].label,
        values: DAYS[k].data.map(s => sKey(s)),
      }));
      const readSel = id => [...document.getElementById(id).querySelectorAll("optgroup")].map(og => ({
        label: og.label,
        values: [...og.querySelectorAll("option")].map(o => o.value),
      }));
      return { expected, selA: readSel("selA"), selB: readSel("selB") };
    });
    for (const key of ["selA", "selB"]) {
      assert.equal(selInfo[key].length, selInfo.expected.length, `${key} optgroup count mismatch`);
      for (let i = 0; i < selInfo.expected.length; i++) {
        assert.equal(selInfo[key][i].label, selInfo.expected[i].label, `${key} optgroup ${i} label mismatch`);
        assert.deepEqual(selInfo[key][i].values, selInfo.expected[i].values, `${key} optgroup ${i} option values mismatch`);
      }
    }

    // Touch height >= 44px and distinct aria-label for useCurA / useCurB on iPhone 13
    const btnA = page.locator("#useCurA");
    const btnB = page.locator("#useCurB");
    assert.equal(await btnA.count(), 1, "#useCurA button must exist");
    assert.equal(await btnB.count(), 1, "#useCurB button must exist");
    const ariaA = await btnA.getAttribute("aria-label");
    const ariaB = await btnB.getAttribute("aria-label");
    assert(ariaA && ariaA.includes("左"), `#useCurA aria-label must mention 左邊, got ${ariaA}`);
    assert(ariaB && ariaB.includes("右"), `#useCurB aria-label must mention 右邊, got ${ariaB}`);
    const boxA = await btnA.boundingBox();
    const boxB = await btnB.boundingBox();
    assert(boxA && boxA.height >= 43.5, `#useCurA touch height must be >= 44px, got ${boxA?.height}`);
    assert(boxB && boxB.height >= 43.5, `#useCurB touch height must be >= 44px, got ${boxB?.height}`);

    // Switch main player to a stroke different from A and B, click #useCurA and #useCurB
    const targetIdx = await page.evaluate(() => {
      const idx = ALL.findIndex(s => s !== A && s !== B);
      return idx >= 0 ? idx : ALL.length - 1;
    });
    await page.evaluate(i => load(i, false), targetIdx);
    await page.waitForFunction(() => v.readyState >= 2 && !v._fetching);
    const curKey = await page.evaluate(() => sKey(S));

    await btnA.scrollIntoViewIfNeeded();
    await btnA.click();
    await page.waitForFunction(() => A === S && vA.readyState >= 2 && !vA._fetching);
    assert.equal(await page.evaluate(() => document.getElementById("selA").value), curKey, "#selA value must match current stroke S");

    // Pick another stroke for B
    const targetIdxB = await page.evaluate(() => {
      const idx = ALL.findIndex(s => s !== A && s !== B);
      return idx >= 0 ? idx : 0;
    });
    await page.evaluate(i => load(i, false), targetIdxB);
    await page.waitForFunction(() => v.readyState >= 2 && !v._fetching);
    const curKeyB = await page.evaluate(() => sKey(S));

    await btnB.scrollIntoViewIfNeeded();
    await btnB.click();
    await page.waitForFunction(() => B === S && vB.readyState >= 2 && !vB._fetching);
    assert.equal(await page.evaluate(() => document.getElementById("selB").value), curKeyB, "#selB value must match current stroke S");

    assert.deepEqual(errors, [], `unexpected page errors: ${errors.join("; ")}`);
  } finally {
    await browser.close();
  }
}

// 2b. Chromium 1440x900 desktop: .player and .stage dimensions match main (<= 1px), and light/dark contrast >= 4.5:1
{
  const browser = await chromium.launch({ headless: true });
  try {
    for (const scheme of ["light", "dark"]) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
      const page = await ctx.newPage();
      await page.goto(URL, { waitUntil: "networkidle" });
      await page.waitForSelector("body.ready");
      await page.evaluate(() => go(DAY_KEYS[0], "video"));
      await page.waitForFunction(() => S && v.readyState >= 2);

      const desk = await page.evaluate(() => {
        const p = document.querySelector(".player").getBoundingClientRect();
        const st = document.getElementById("stage").getBoundingClientRect();
        const wide = document.querySelector(".player").classList.contains("wide");
        const sz = S.size || [9, 16];
        const ar = sz[0] / sz[1];
        const expPlayerW = wide
          ? Math.min(parseFloat(getComputedStyle(document.querySelector("main")).gridTemplateColumns), Math.max(360, (window.innerHeight - 400) * 16 / 9), 900)  // the player's own grid column: the whole row, or 3fr beside the resident 3D (UI 方案 A 第 4 步)
          : Math.min(420, Math.max(260, (window.innerHeight - 290) * 9 / 16));
        const expStageW = wide ? expPlayerW : Math.min(expPlayerW, Math.max(200, (window.innerHeight - 460) * 9 / 16));
        const expStageH = expStageW / ar;
        const csA = getComputedStyle(document.getElementById("useCurA"));
        const csB = getComputedStyle(document.getElementById("useCurB"));
        return {
          pw: p.width, sw: st.width, sh: st.height,
          expPlayerW, expStageW, expStageH,
          fgA: csA.color, bgA: csA.backgroundColor,
          fgB: csB.color, bgB: csB.backgroundColor,
        };
      });
      assert(Math.abs(desk.pw - desk.expPlayerW) <= 1, `desktop (${scheme}) .player width ${desk.pw} != expected ${desk.expPlayerW}`);
      assert(Math.abs(desk.sw - desk.expStageW) <= 1, `desktop (${scheme}) .stage width ${desk.sw} != expected ${desk.expStageW}`);
      assert(Math.abs(desk.sh - desk.expStageH) <= 1, `desktop (${scheme}) .stage height ${desk.sh} != expected ${desk.expStageH}`);

      for (const [label, fg, bg] of [["#useCurA", desk.fgA, desk.bgA], ["#useCurB", desk.fgB, desk.bgB]]) {
        const ratio = contrast(parseRgb(fg), parseRgb(bg));
        assert(ratio >= 4.5, `${scheme} ${label} contrast ${ratio.toFixed(2)} < 4.5 (${fg} on ${bg})`);
      }
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
}

// 5. WebKit 4 phone profiles + iPad mini: controls >= 44x44 & wrap, iPhone 13 stage >= 340px & player <= 60%, .vid-msg/.pose-msg inside .stage, iPad mini matches main
{
  const browser = await webkit.launch({ headless: true });
  try {
    const specs = [
      { name: "iPhone 13", maxPortraitRatio: 0.6, minStageW: 340 },
      { name: "iPhone 13 landscape", maxPortraitRatio: null, minStageW: null },
      { name: "iPhone SE", maxPortraitRatio: null, minStageW: null },
      { name: "iPhone SE landscape", maxPortraitRatio: null, minStageW: null },
    ];
    for (const spec of specs) {
      const ctx = await browser.newContext({ ...devices[spec.name] });
      const page = await ctx.newPage();
      await page.goto(URL, { waitUntil: "networkidle" });
      await page.waitForSelector("body.ready");
      await page.evaluate(() => go(DAY_KEYS[0], "video"));
      await page.waitForFunction(() => S && v.readyState >= 2);

      const layout = await page.evaluate(() => {
        const p = document.querySelector(".player").getBoundingClientRect();
        const st = document.getElementById("stage").getBoundingClientRect();
        const ctl = document.querySelector(".player .controls");
        const btns = [...ctl.querySelectorAll("button")].filter(b => getComputedStyle(b).display !== "none" && b.offsetParent !== null);
        const out = btns.map(b => {
          const r = b.getBoundingClientRect();
          return { id: b.id || b.textContent, left: r.left, right: r.right };
        }).filter(x => x.left < -0.5 || x.right > window.innerWidth + 0.5);
        const small = btns.map(b => {
          const r = b.getBoundingClientRect();
          return { id: b.id || b.textContent, w: r.width, h: r.height };
        }).filter(x => x.w < 43.5 || x.h < 43.5);
        const cyc = document.getElementById("speed");
        return {
          pH: p.height,
          stW: st.width,
          stH: st.height,
          wide: document.querySelector(".player").classList.contains("wide"),
          is169: !!(S.size && S.size[0] / S.size[1] >= 1.7),
          vh: window.innerHeight,
          ratio: p.height / window.innerHeight,
          ctlScrollW: ctl.scrollWidth,
          ctlClientW: ctl.clientWidth,
          outOfView: out,
          smallBtns: small,
          cycVisible: getComputedStyle(cyc).display !== "none" && cyc.offsetParent !== null,
        };
      });
      assert(layout.cycVisible, `${spec.name}: #speed must be visible`);
      assert(layout.ctlScrollW <= layout.ctlClientW,
        `${spec.name}: .controls scrollWidth (${layout.ctlScrollW}) > clientWidth (${layout.ctlClientW})`);
      assert.equal(layout.outOfView.length, 0,
        `${spec.name}: .controls buttons out of viewport: ${JSON.stringify(layout.outOfView)}`);
      assert.equal(layout.smallBtns.length, 0,
        `${spec.name}: .controls buttons < 44x44: ${JSON.stringify(layout.smallBtns)}`);
      if (spec.name === "iPhone 13") {
        console.log(`iPhone 13 portrait: .stage=${layout.stW.toFixed(1)}x${layout.stH.toFixed(1)}px, .player=${layout.pH.toFixed(1)}/${layout.vh}px (${(layout.ratio * 100).toFixed(1)}%)`);
      }
      if (spec.maxPortraitRatio !== null && layout.is169) {
        assert(layout.ratio <= spec.maxPortraitRatio,
          `${spec.name}: .player height ${(layout.ratio * 100).toFixed(1)}% > ${(spec.maxPortraitRatio * 100)}%`);
      }
      if (spec.minStageW !== null) {
        if (layout.wide) {
          assert(layout.stW >= spec.minStageW,
            `${spec.name}: wide .stage width ${layout.stW.toFixed(1)}px < ${spec.minStageW}px`);
        } else {
          assert(Math.abs(layout.stH - layout.vh * 0.38) <= 2,
            `${spec.name}: portrait .stage height ${layout.stH.toFixed(1)}px != 38svh (${(layout.vh * 0.38).toFixed(1)}px)`);
        }
      }

      // Force skeleton loading message (.pose-msg) and verify it stays inside .stage
      const poseBox = await page.evaluate(() => {
        const pm = document.querySelector("#stage .pose-msg");
        const prevText = pm.textContent, prevHidden = pm.hidden;
        pm.textContent = "骨架資料載入中，請稍候…";
        pm.hidden = false;
        const st = document.getElementById("stage").getBoundingClientRect();
        const m = pm.getBoundingClientRect();
        pm.textContent = prevText;
        pm.hidden = prevHidden;
        return {
          st: { left: st.left, right: st.right, top: st.top, bottom: st.bottom },
          m: { left: m.left, right: m.right, top: m.top, bottom: m.bottom },
        };
      });
      assert(
        poseBox.m.left >= poseBox.st.left - 0.5 &&
        poseBox.m.right <= poseBox.st.right + 0.5 &&
        poseBox.m.top >= poseBox.st.top - 0.5 &&
        poseBox.m.bottom <= poseBox.st.bottom + 0.5,
        `${spec.name}: .pose-msg ${JSON.stringify(poseBox.m)} overflows .stage ${JSON.stringify(poseBox.st)}`
      );

      // Force video load failure (404) and verify .vid-msg retry button stays completely inside .stage
      await page.route("**/*.mp4*", route => route.fulfill({ status: 404, body: "" }));
      await page.evaluate(() => {
        S.src = S.src.split("?")[0] + "?fail_probe=" + Date.now();
        load(S.id, false);
      });
      await page.waitForSelector("#stage .vid-msg[data-fail]:not([hidden])");
      const msgBox = await page.evaluate(() => {
        const st = document.getElementById("stage").getBoundingClientRect();
        const m = document.querySelector("#stage .vid-msg").getBoundingClientRect();
        return {
          st: { left: st.left, right: st.right, top: st.top, bottom: st.bottom, w: st.width, h: st.height },
          m: { left: m.left, right: m.right, top: m.top, bottom: m.bottom, w: m.width, h: m.height },
        };
      });
      assert(
        msgBox.m.left >= msgBox.st.left - 0.5 &&
        msgBox.m.right <= msgBox.st.right + 0.5 &&
        msgBox.m.top >= msgBox.st.top - 0.5 &&
        msgBox.m.bottom <= msgBox.st.bottom + 0.5,
        `${spec.name}: .vid-msg ${JSON.stringify(msgBox.m)} overflows .stage ${JSON.stringify(msgBox.st)}`
      );

      await ctx.close();
    }

    // (e) iPhone 13 portrait: simultaneous .pose-msg and .vid-msg on both 16:9 and 9:16 stages must not overlap, stay inside .stage, and wrap <= 3 lines
    {
      const ctx = await browser.newContext({ ...devices["iPhone 13"] });
      const page = await ctx.newPage();
      await page.goto(URL, { waitUntil: "networkidle" });
      await page.waitForSelector("body.ready");
      await page.evaluate(() => go(DAY_KEYS[0], "video"));
      await page.waitForFunction(() => S && v.readyState >= 2);

      for (const mode of [{ label: "16:9", wide: true, ar: "16/9" }, { label: "9:16", wide: false, ar: "9/16" }]) {
        const res = await page.evaluate(({ wide, ar }) => {
          const player = document.querySelector(".player");
          const stage = document.getElementById("stage");
          const pm = stage.querySelector(".pose-msg");
          const vm = stage.querySelector(".vid-msg");
          player.classList.toggle("wide", wide);
          stage.classList.toggle("wide", wide);
          stage.style.aspectRatio = ar;
          pm.textContent = "骨架資料載入中，請稍候…";
          pm.hidden = false;
          vm.textContent = "影片載入失敗（點此重試）";
          vm.hidden = false;
          vm.dataset.fail = "1";
          const st = stage.getBoundingClientRect();
          const pr = pm.getBoundingClientRect();
          const vr = vm.getBoundingClientRect();
          const pcs = getComputedStyle(pm);
          const vcs = getComputedStyle(vm);
          const maxH = cs => (parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3) * 3 + parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) + 2;
          return {
            st: { left: st.left, right: st.right, top: st.top, bottom: st.bottom },
            pr: { left: pr.left, right: pr.right, top: pr.top, bottom: pr.bottom, h: pr.height, maxH: maxH(pcs) },
            vr: { left: vr.left, right: vr.right, top: vr.top, bottom: vr.bottom, h: vr.height, maxH: maxH(vcs), fontSize: parseFloat(vcs.fontSize) },
          };
        }, mode);
        assert(res.vr.fontSize >= 12, `iPhone 13 ${mode.label}: .vid-msg fontSize ${res.vr.fontSize}px < 12px`);
        for (const [name, box] of [[".pose-msg", res.pr], [".vid-msg", res.vr]]) {
          assert(
            box.left >= res.st.left - 0.5 && box.right <= res.st.right + 0.5 &&
            box.top >= res.st.top - 0.5 && box.bottom <= res.st.bottom + 0.5,
            `iPhone 13 ${mode.label}: ${name} ${JSON.stringify(box)} overflows .stage ${JSON.stringify(res.st)}`
          );
          assert(box.h <= box.maxH,
            `iPhone 13 ${mode.label}: ${name} height ${box.h.toFixed(1)}px > 3-line max ${box.maxH.toFixed(1)}px`);
        }
        const disjoint =
          res.pr.bottom <= res.vr.top + 0.5 || res.vr.bottom <= res.pr.top + 0.5 ||
          res.pr.right <= res.vr.left + 0.5 || res.vr.right <= res.pr.left + 0.5;
        assert(disjoint, `iPhone 13 ${mode.label}: .pose-msg ${JSON.stringify(res.pr)} overlaps .vid-msg ${JSON.stringify(res.vr)}`);
      }
      await ctx.close();
    }

    // (d) iPad mini portrait (768x1024): .stage dimensions match main (<= 2px)
    const ipadCtx = await browser.newContext({ ...(devices["iPad Mini"] || {}), viewport: { width: 768, height: 1024 }, hasTouch: true });
    const ipadPage = await ipadCtx.newPage();
    await ipadPage.goto(URL, { waitUntil: "networkidle" });
    await ipadPage.waitForSelector("body.ready");
    await ipadPage.evaluate(() => go(DAY_KEYS[0], "video"));
    await ipadPage.waitForFunction(() => S && v.readyState >= 2);
    const ipad = await ipadPage.evaluate(() => {
      const st = document.getElementById("stage").getBoundingClientRect();
      const wide = document.querySelector(".player").classList.contains("wide");
      const sz = S.size || [9, 16];
      const ar = sz[0] / sz[1];
      const mainW = document.querySelector("main").clientWidth - 32;
      const expW = wide ? mainW : (window.innerHeight * 0.38) * ar;
      const expH = wide ? mainW / ar : window.innerHeight * 0.38;
      return { w: st.width, h: st.height, expW, expH };
    });
    assert(Math.abs(ipad.w - ipad.expW) <= 2, `iPad mini .stage width ${ipad.w} != main ${ipad.expW}`);
    assert(Math.abs(ipad.h - ipad.expH) <= 2, `iPad mini .stage height ${ipad.h} != main ${ipad.expH}`);
    await ipadCtx.close();
  } finally {
    await browser.close();
  }
}

console.log("test_site_i57_mobile.mjs: all assertions passed");
