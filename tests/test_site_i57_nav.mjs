// Playwright E2E test for #57 PR2 (stroke progress "第 X／共 Y 拍", #nowTitle no truncation on 390px, #homeLink button style & contrast).
// Run against local server: SITE_E2E_URL=... PLAYWRIGHT_MODULE=... node tests/test_site_i57_nav.mjs
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

async function checkProgressAndFilter(page, label) {
  // Click the first stroke in the unfiltered list so we start at stroke 1 of N
  await page.evaluate(() => document.querySelector("#strokes button")?.click());
  await page.waitForTimeout(100);

  // 1. Unfiltered: title contains "第 1／共 N 拍", N = stroke list length
  const init = await page.evaluate(() => {
    const total = document.querySelectorAll("#strokes button").length;
    return {
      total,
      now: document.getElementById("nowTitle").textContent,
      detail: document.getElementById("detailTitle").textContent,
    };
  });
  assert(init.total >= 2, `${label}: expected >= 2 strokes, got ${init.total}`);
  const expectedInit = `第 1／共 ${init.total} 拍`;
  assert(init.now.includes(expectedInit), `${label}: #nowTitle "${init.now}" missing "${expectedInit}"`);
  assert(init.detail.includes(expectedInit), `${label}: #detailTitle "${init.detail}" missing "${expectedInit}"`);

  // 1b. If we filter to a kind that excludes the current stroke, title must NOT show a wrong "第 X／共 Y 拍"
  const excludedCheck = await page.evaluate(() => {
    const curKind = S?.kind;
    const kindBtns = [...document.querySelectorAll("#tabs button")].filter(b => /^(正拍|反拍|發球)\s+\d+$/.test(b.textContent));
    const other = kindBtns.find(b => !b.textContent.includes(NAMES[curKind] || curKind) && parseInt(b.textContent.match(/(\d+)/)[1], 10) >= 1);
    if (!other) return null;
    other.click();
    return {
      now: document.getElementById("nowTitle").textContent,
      detail: document.getElementById("detailTitle").textContent,
      globalNo: `#${String(S.id + 1).padStart(2, "0")}`,
    };
  });
  if (excludedCheck) {
    assert(!/第 \d+／共/.test(excludedCheck.now), `${label}: excluded stroke #nowTitle must not show progress, got "${excludedCheck.now}"`);
    assert(excludedCheck.now.includes(excludedCheck.globalNo), `${label}: excluded stroke #nowTitle missing global ${excludedCheck.globalNo}, got "${excludedCheck.now}"`);
    assert(!/第 \d+／共/.test(excludedCheck.detail), `${label}: excluded stroke #detailTitle must not show progress, got "${excludedCheck.detail}"`);
  }

  // 2. Filter to a single stroke kind (pick first kind tab with count >= 2, or >= 1) and click #nextS
  const filterInfo = await page.evaluate(() => {
    const kindBtns = [...document.querySelectorAll("#tabs button")].filter(b => /^(正拍|反拍|發球)\s+\d+$/.test(b.textContent));
    const target = kindBtns.find(b => parseInt(b.textContent.match(/(\d+)/)[1], 10) >= 2)
      || kindBtns.find(b => parseInt(b.textContent.match(/(\d+)/)[1], 10) >= 1);
    if (!target) return null;
    target.click();
    return {
      label: target.textContent,
      filteredCount: document.querySelectorAll("#strokes button").length,
      nowAfterFilter: document.getElementById("nowTitle").textContent,
    };
  });
  assert(filterInfo && filterInfo.filteredCount >= 1, `${label}: no single-kind filter tab with strokes found`);
  await page.click("#nextS");
  await page.waitForTimeout(150);

  const afterNext = await page.evaluate(() => ({
    now: document.getElementById("nowTitle").textContent,
    detail: document.getElementById("detailTitle").textContent,
    filteredCount: document.querySelectorAll("#strokes button").length,
  }));
  // After clicking #nextS while filtered, we must be in the filtered list with X / filteredCount
  const parseProg = text => {
    const m = text.match(/第 (\d+)／共 (\d+) 拍/);
    return m ? { x: Number(m[1]), y: Number(m[2]) } : null;
  };
  const nowProg = parseProg(afterNext.now);
  assert(nowProg && nowProg.y === afterNext.filteredCount && nowProg.x >= 1 && nowProg.x <= afterNext.filteredCount,
    `${label}: after filter (${filterInfo.label}) + #nextS, #nowTitle "${afterNext.now}" invalid for count ${afterNext.filteredCount}`);
  const detailProg = parseProg(afterNext.detail);
  assert(detailProg && detailProg.y === afterNext.filteredCount && detailProg.x >= 1 && detailProg.x <= afterNext.filteredCount,
    `${label}: after filter (${filterInfo.label}) + #nextS, #detailTitle "${afterNext.detail}" invalid for count ${afterNext.filteredCount}`);

  // If filteredCount >= 2, clicking #nextS again should advance X by 1 (wrapping mod filteredCount)
  if (afterNext.filteredCount >= 2) {
    const firstX = nowProg.x;
    await page.click("#nextS");
    await page.waitForTimeout(150);
    const secondTitle = await page.evaluate(() => document.getElementById("nowTitle").textContent);
    const expectedSecondX = (firstX % afterNext.filteredCount) + 1;
    assert(secondTitle.includes(`第 ${expectedSecondX}／共 ${afterNext.filteredCount} 拍`),
      `${label}: expected 第 ${expectedSecondX}／共 ${afterNext.filteredCount} 拍, got "${secondTitle}"`);
  }

  // Reset filter back to ALL
  await page.evaluate(() => document.querySelector("#tabs button")?.click());
  await page.waitForTimeout(100);
}

// A. Mobile WebKit 390x844 portrait
{
  const browser = await webkit.launch({ headless: true });
  try {
    const iPhone = devices["iPhone 13"];
    const ctx = await browser.newContext({ ...iPhone, viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();
    await page.goto(URL, { waitUntil: "networkidle" });
    await page.waitForSelector("body.ready");
    await page.evaluate(() => go(DAY_KEYS[0], "stroke"));
    await page.waitForTimeout(300);

    await checkProgressAndFilter(page, "webkit-390x844");

    // 3. On 390px width: #nowTitle scrollWidth <= clientWidth, no horizontal page overflow
    const overflow = await page.evaluate(() => {
      const t = document.getElementById("nowTitle");
      const cs = getComputedStyle(t);
      return {
        titleScrollW: t.scrollWidth,
        titleClientW: t.clientWidth,
        textOverflow: cs.textOverflow,
        whiteSpace: cs.whiteSpace,
        docScrollW: document.documentElement.scrollWidth,
        vw: window.innerWidth,
      };
    });
    assert(overflow.titleScrollW <= overflow.titleClientW,
      `390px #nowTitle truncated/overflows: scrollWidth=${overflow.titleScrollW} > clientWidth=${overflow.titleClientW}`);
    assert(overflow.docScrollW <= overflow.vw,
      `390px page horizontal overflow: scrollWidth=${overflow.docScrollW} > vw=${overflow.vw}`);

    // 4. #homeLink height >= 44px and has non-transparent border or background
    const homeBox = await page.evaluate(() => {
      const el = document.getElementById("homeLink");
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        h: r.height,
        bg: cs.backgroundColor,
        bw: parseFloat(cs.borderTopWidth),
        bc: cs.borderTopColor,
      };
    });
    assert(homeBox.h >= 44, `webkit 390px #homeLink height ${homeBox.h.toFixed(1)} < 44`);
    const bgA = parseRgb(homeBox.bg)?.a ?? 0;
    const bcA = parseRgb(homeBox.bc)?.a ?? 0;
    assert(bgA > 0 || (homeBox.bw > 0 && bcA > 0),
      `webkit 390px #homeLink must have non-transparent border or background (bg=${homeBox.bg}, bw=${homeBox.bw}, bc=${homeBox.bc})`);

    await ctx.close();
  } finally {
    await browser.close();
  }
}

// B. Desktop Chromium 1440x900 (light & dark themes)
{
  const browser = await chromium.launch({ headless: true });
  try {
    for (const scheme of ["light", "dark"]) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
      const page = await ctx.newPage();
      await page.goto(URL, { waitUntil: "networkidle" });
      await page.waitForSelector("body.ready");
      await page.evaluate(() => go(DAY_KEYS[0], "stroke"));
      await page.waitForTimeout(250);

      if (scheme === "light") {
        await checkProgressAndFilter(page, "chromium-1440x900");

        // Portrait clip on desktop (1440x900): #nowTitle must display full stroke # and kind without ellipsis truncation
        const desktopPortrait = await page.evaluate(() => {
          const player = document.querySelector(".player");
          const main = document.querySelector("main");
          const wasWide = player.classList.contains("wide");
          if (wasWide) {
            player.classList.remove("wide");
            main.classList.remove("wideplayer");
          }
          const t = document.getElementById("nowTitle");
          const cs = getComputedStyle(t);
          const res = {
            playerWidth: player.getBoundingClientRect().width,
            text: t.textContent,
            scrollW: t.scrollWidth,
            clientW: t.clientWidth,
            textOverflow: cs.textOverflow,
            whiteSpace: cs.whiteSpace,
          };
          if (wasWide) {
            player.classList.add("wide");
            main.classList.add("wideplayer");
          }
          return res;
        });
        assert(/#\d+/.test(desktopPortrait.text) && /(正拍|反拍|發球)/.test(desktopPortrait.text),
          `chromium-1440x900 portrait #nowTitle missing stroke # or kind: "${desktopPortrait.text}"`);
        assert(desktopPortrait.textOverflow !== "ellipsis" && desktopPortrait.scrollW <= desktopPortrait.clientW,
          `chromium-1440x900 portrait #nowTitle truncated (playerW=${desktopPortrait.playerWidth.toFixed(0)}, textOverflow=${desktopPortrait.textOverflow}, scrollW=${desktopPortrait.scrollW}, clientW=${desktopPortrait.clientW}, text="${desktopPortrait.text}")`);
      }

      // 4 & 5. #homeLink height >= 44px, non-transparent border/background, contrast >= 4.5:1
      const hl = await page.evaluate(() => {
        const el = document.getElementById("homeLink");
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        let bg = cs.backgroundColor;
        let cur = el;
        const isTransparent = s => !s || s === "transparent" || /rgba\([^)]+,\s*0\s*\)/.test(s);
        while (cur && isTransparent(bg)) {
          cur = cur.parentElement;
          if (cur) bg = getComputedStyle(cur).backgroundColor;
        }
        return {
          h: r.height,
          fg: cs.color,
          selfBg: cs.backgroundColor,
          effectiveBg: bg,
          bw: parseFloat(cs.borderTopWidth),
          bc: cs.borderTopColor,
        };
      });
      assert(hl.h >= 44, `${scheme} #homeLink height ${hl.h.toFixed(1)} < 44`);
      const bgA = parseRgb(hl.selfBg)?.a ?? 0;
      const bcA = parseRgb(hl.bc)?.a ?? 0;
      assert(bgA > 0 || (hl.bw > 0 && bcA > 0),
        `${scheme} #homeLink must have non-transparent border or background (bg=${hl.selfBg}, bw=${hl.bw}, bc=${hl.bc})`);

      const ratio = contrast(parseRgb(hl.fg), parseRgb(hl.effectiveBg));
      assert(ratio >= 4.5, `${scheme} #homeLink contrast ${ratio.toFixed(2)} < 4.5 (fg=${hl.fg}, bg=${hl.effectiveBg})`);

      await ctx.close();
    }
  } finally {
    await browser.close();
  }
}

console.log("test_site_i57_nav.mjs: all assertions passed");
