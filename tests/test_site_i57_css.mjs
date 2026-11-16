// Playwright CSS regression check for #57 PR 1 (landscape breakpoint, WCAG contrast, touch target size).
// Run against local server: SITE_E2E_URL=... PLAYWRIGHT_MODULE=... node tests/test_site_i57_css.mjs
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

// 1. Mobile WebKit 844x390 landscape: play button must be inside first screen, no horizontal overflow
{
  const browser = await webkit.launch({ headless: true });
  try {
    const iPhone = devices["iPhone 13"];
    const ctx = await browser.newContext({ ...iPhone, viewport: { width: 844, height: 390 } });
    const page = await ctx.newPage();
    await page.goto(URL, { waitUntil: "networkidle" });
    await page.waitForSelector("body.ready");
    await page.evaluate(() => go(DAY_KEYS[0], "video"));
    await page.waitForTimeout(300);

    const layout = await page.evaluate(() => {
      const play = document.getElementById("play").getBoundingClientRect();
      const stage = document.getElementById("stage").getBoundingClientRect();
      const kbdHint = getComputedStyle(document.querySelector(".kbd-hint")).display;
      return {
        vw: window.innerWidth,
        vh: window.innerHeight,
        scrollWidth: document.documentElement.scrollWidth,
        playTop: play.top,
        playBottom: play.bottom,
        playLeft: play.left,
        stageRight: stage.right,
        kbdHint,
      };
    });
    assert(layout.scrollWidth <= layout.vw, `landscape overflow: ${layout.scrollWidth} > ${layout.vw}`);
    assert(layout.playTop >= 0 && layout.playBottom <= layout.vh,
      `#play must be inside 844x390 viewport, got top=${layout.playTop} bottom=${layout.playBottom}`);
    assert(layout.playLeft >= layout.stageRight - 1,
      `#play must sit beside stage in landscape, got playLeft=${layout.playLeft} stageRight=${layout.stageRight}`);

    // Touch targets on advice tab >= 44px height & .tag single-line on stroke tab
    await page.evaluate(() => go(DAY_KEYS[0], "advice"));
    await page.waitForTimeout(200);
    const smallLinks = await page.evaluate(() =>
      [...document.querySelectorAll(".links a")].map(a => ({
        text: a.textContent.slice(0, 20),
        h: a.getBoundingClientRect().height,
      })).filter(x => x.h < 43.5)
    );
    assert.equal(smallLinks.length, 0, `advice links < 44px: ${JSON.stringify(smallLinks)}`);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => go(DAY_KEYS[0], "stroke"));
    await page.waitForTimeout(200);
    const wrappedTags = await page.evaluate(() =>
      [...document.querySelectorAll(".strokes button .tag")].slice(0, 20).map(t => ({
        text: t.textContent,
        h: t.getBoundingClientRect().height,
        ws: getComputedStyle(t).whiteSpace,
      })).filter(x => x.ws !== "nowrap" || x.h > 26)
    );
    assert.equal(wrappedTags.length, 0, `.tag must not wrap: ${JSON.stringify(wrappedTags)}`);
  } finally {
    await browser.close();
  }
}

// 2. Short desktop Chromium window (1280x480) must NOT trigger mobile layout; light/dark WCAG contrast >= 4.5
{
  const browser = await chromium.launch({ headless: true });
  try {
    const ctxShort = await browser.newContext({ viewport: { width: 1280, height: 480 } });
    const pageShort = await ctxShort.newPage();
    await pageShort.goto(URL, { waitUntil: "networkidle" });
    await pageShort.waitForSelector("body.ready");
    await pageShort.evaluate(() => go(DAY_KEYS[0], "stroke"));
    await pageShort.waitForTimeout(200);
    const shortDisplay = await pageShort.evaluate(() => ({
      playerDisplay: getComputedStyle(document.querySelector(".player")).display,
      kbdDisplay: getComputedStyle(document.querySelector(".kbd-hint")).display,
    }));
    assert.notEqual(shortDisplay.playerDisplay, "grid", "short desktop window must not use mobile landscape grid");
    assert.notEqual(shortDisplay.kbdDisplay, "none", "short desktop window must keep desktop kbd-hint");
    await ctxShort.close();

    for (const scheme of ["light", "dark"]) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
      const page = await ctx.newPage();
      await page.goto(URL, { waitUntil: "networkidle" });
      await page.waitForSelector("body.ready");
      await page.evaluate(() => go(DAY_KEYS[0], "stroke"));
      await page.waitForTimeout(200);
      const tagPairs = await page.evaluate(() => {
        const pairs = ["FH", "BH", "SV"].map(k => {
          const el = document.querySelector(`.tag.${k}`);
          if (!el) return null;
          const cs = getComputedStyle(el);
          return { k, fg: cs.color, bg: cs.backgroundColor };
        }).filter(Boolean);
        const oh = document.createElement("span");
        oh.className = "tag OH";
        oh.textContent = "OH";
        const host = document.querySelector(".strokes button:not(.cur)") || document.body;
        host.append(oh);
        const fgOh = getComputedStyle(oh).color;
        const bgOh = getComputedStyle(host).backgroundColor;
        oh.remove();
        pairs.push({ k: "OH", fg: fgOh, bg: bgOh });
        return pairs;
      });
      for (const p of tagPairs) {
        const ratio = contrast(parseRgb(p.fg), parseRgb(p.bg));
        assert(ratio >= 4.5, `${scheme} .tag.${p.k} contrast ${ratio.toFixed(2)} < 4.5`);
      }

      if (scheme === "light") {
        await page.evaluate(() => go(DAY_KEYS[0], "advice"));
        await page.waitForTimeout(200);
        const advicePairs = await page.evaluate(() =>
          [...document.querySelectorAll(".check li .you")].slice(0, 6).map(el => {
            const cs = getComputedStyle(el);
            const liBg = getComputedStyle(el.closest("li")).backgroundColor;
            return { cls: el.className, fg: cs.color, bg: liBg };
          })
        );
        for (const p of advicePairs) {
          const ratio = contrast(parseRgb(p.fg), parseRgb(p.bg));
          assert(ratio >= 4.5, `light .${p.cls} on --chip contrast ${ratio.toFixed(2)} < 4.5`);
        }
      }
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
}

console.log("test_site_i57_css.mjs: all assertions passed");
