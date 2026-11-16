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

// 1. WebKit 390x844 portrait: scrolling to compare & stroke list leaves .player visible height <= 40% vh, no horizontal overflow;
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

    // Choose a session (prefer one with multiple strokes)
    await page.evaluate(() => go(DAY_KEYS[0], "video"));
    await page.waitForFunction(() => S && v.readyState >= 2);

    // Scroll to compare section (#selA / #vA)
    await page.evaluate(() => document.getElementById("selA").closest(".card").scrollIntoView({ block: "start" }));
    await page.waitForTimeout(200);
    const cmpPort = await page.evaluate(() => {
      const p = document.querySelector(".player");
      const r = p.getBoundingClientRect();
      const visH = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0));
      return {
        pos: getComputedStyle(p).position,
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
    assert(cmpPort.h <= cmpPort.vh * 0.4,
      `portrait .player height at compare (${cmpPort.h.toFixed(1)}px = ${(cmpPort.ratio * 100).toFixed(1)}%) must be <= 40% of ${cmpPort.vh}px`);

    // Scroll down on stroke tab, check sticky .player <= 40% and visible, then click 2nd stroke and verify scrollY != 0
    await page.evaluate(() => go(DAY_KEYS[0], "stroke"));
    await page.waitForTimeout(200);
    await page.evaluate(() => window.scrollTo(0, 120));
    await page.waitForTimeout(200);
    const strokePort = await page.evaluate(() => {
      const p = document.querySelector(".player");
      const r = p.getBoundingClientRect();
      const visH = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0));
      return {
        pos: getComputedStyle(p).position,
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
    assert(strokePort.h <= strokePort.vh * 0.4,
      `portrait .player height at stroke list (${strokePort.h.toFixed(1)}px = ${(strokePort.ratio * 100).toFixed(1)}%) must be <= 40% of ${strokePort.vh}px`);

    // Click 2nd stroke in list -> scrollY must NOT reset to 0
    await page.locator(".strokes button").nth(1).click();
    await page.waitForTimeout(350);
    const afterListClickScrollY = await page.evaluate(() => window.scrollY);
    assert(afterListClickScrollY > 0, `clicking 2nd stroke in list must not reset scrollY to 0 (got ${afterListClickScrollY})`);

    // Scroll to #chart on stroke tab, click to jump -> main video currentTime changes and .player stays visible
    await page.evaluate(() => {
      const el = document.getElementById("chart");
      const y = el.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.5;
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
    await page.waitForFunction(() => S && v.readyState >= 2 && vA.readyState >= 2 && vB.readyState >= 2);

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
          ? Math.min(document.querySelector("main").clientWidth - 32, Math.max(360, (window.innerHeight - 400) * 16 / 9), 900)
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

console.log("test_site_i57_mobile.mjs: all assertions passed");
