// Homepage + footer checks for the recovered founder visual edits (rounds 1–3),
// across the full responsive matrix. Compares two builds when BEFORE_URL is set.
// Usage: BASE_URL=http://localhost:3000 [BEFORE_URL=http://localhost:3001] \
//        [CHROMIUM_PATH=...] node scripts/verify/home_footer_layout.js <out-dir>
// Needs a TEST backend; it adds an item to the cart (localStorage only, no order).
const { chromium } = require("playwright");
const fs = require("fs");
const AFTER = process.env.BASE_URL || "http://localhost:3000";
const BEFORE = process.env.BEFORE_URL || null;
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const WIDTHS = [320, 360, 375, 390, 430, 768, 820, 1024, 1280, 1440, 1920];
const SHOT_WIDTHS = [375, 768, 1280];
const results = [];
const rec = (name, ok, detail = "") => { results.push({ name, ok, detail }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`); };

async function measure(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const offenders = [];
    for (const el of document.querySelectorAll("main *, footer *, header *")) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > vw + 1) && !el.closest('[aria-hidden="true"]') && getComputedStyle(el).position !== "fixed") {
        // ignore elements clipped by an overflow-hidden ancestor
        let a = el.parentElement, clipped = false;
        while (a) { const o = getComputedStyle(a).overflowX; if (o === "hidden" || o === "clip") { clipped = true; break; } a = a.parentElement; }
        if (!clipped) offenders.push(`${el.tagName.toLowerCase()}.${(el.className || "").toString().split(" ")[0]}`);
      }
    }
    const h1 = document.querySelector("h1");
    const hr = h1?.getBoundingClientRect();
    const footerLinks = [...document.querySelectorAll('footer nav[aria-label="All pages"] a')];
    return {
      sw: document.documentElement.scrollWidth, cw: vw,
      h1: h1?.innerText.replace(/\s+/g, " ").trim(), h1Clipped: hr ? hr.right > vw + 1 || hr.left < -1 : null,
      offenders: [...new Set(offenders)].slice(0, 5),
      mirrorCats: [...document.querySelectorAll('[data-testid^="mirror-category-"]')].map((b) => b.dataset.testid.replace("mirror-category-", "")),
      smallTargets: [...document.querySelectorAll('[data-testid^="mirror-category-"]')].filter((b) => b.getBoundingClientRect().height < 44).length,
      heroCtaH: Math.round(document.querySelector('[data-testid="hero-shop-now"]')?.getBoundingClientRect().height || 0),
      footerLinks: footerLinks.map((a) => a.getAttribute("href")),
      footerLinkMinH: footerLinks.length ? Math.min(...footerLinks.map((a) => a.getBoundingClientRect().height)) : null,
      footerTagline: document.querySelector("footer")?.innerText.includes("Contemporary, proudly Bangladeshi."),
      sheen: !!document.querySelector(".aayna-mirror-circle"),
      sheenAnim: (() => { const e = document.querySelector(".aayna-mirror-circle"); return e ? getComputedStyle(e).animationName : null; })(),
    };
  });
}

(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const table = [];
  for (const w of WIDTHS) {
    for (const [label, base] of [["after", AFTER], ...(BEFORE ? [["before", BEFORE]] : [])]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: w < 768 ? 812 : w < 1280 ? 1024 : 900 } });
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(base + "/", { waitUntil: "networkidle" });
      await page.waitForTimeout(500);
      const m = await measure(page);
      table.push({ w, label, ...m, errors: errors.length });
      if (label === "after") {
        rec(`[${w}px] no horizontal overflow`, m.sw <= m.cw, `scrollWidth=${m.sw} clientWidth=${m.cw}${m.offenders.length ? " offenders=" + m.offenders.join(",") : ""}`);
        rec(`[${w}px] hero headline not clipped`, m.h1Clipped === false, `"${m.h1}"`);
        rec(`[${w}px] no uncaught errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
      }
      if (SHOT_WIDTHS.includes(w)) {
        await page.screenshot({ path: `${OUT}/home_${label}_${w}.png`, fullPage: true });
        await page.locator("footer").screenshot({ path: `${OUT}/footer_${label}_${w}.png` });
      }
      await ctx.close();
    }
  }

  // ---- recovered-content assertions (after build) ----
  const a375 = table.find((t) => t.w === 375 && t.label === "after");
  rec("hero headline is 'Reflect Your Aura.'", a375.h1 === "Reflect Your Aura.", a375.h1);
  rec("Bracelets present in Digital Mirror categories", a375.mirrorCats.includes("bracelets"), a375.mirrorCats.join(","));
  rec("mirror category tap targets >= 44px", a375.smallTargets === 0, `${a375.smallTargets} below 44px`);
  const b375 = table.find((t) => t.w === 375 && t.label === "before");
  rec("INFO hero 'shop now' CTA height (pre-existing, Phase 3)", true, `after ${a375.heroCtaH}px, before ${b375 ? b375.heroCtaH + "px" : "n/a"}`);
  rec("footer bottom nav links all 8 pages", JSON.stringify(a375.footerLinks) === JSON.stringify(["/", "/shop", "/track-order", "/contact", "/delivery-policy", "/returns", "/privacy", "/terms"]), a375.footerLinks.join(" "));
  rec("footer tagline 'Contemporary, proudly Bangladeshi.'", a375.footerTagline);
  rec("mirror sheen applied and animating", a375.sheen && a375.sheenAnim === "aayna-mirror-sheen", a375.sheenAnim);
  if (a375.footerLinkMinH < 44) rec("INFO footer nav link tap height", true, `min ${a375.footerLinkMinH.toFixed(0)}px (<44px; Phase 3 item)`);

  // reduced motion
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto(AFTER + "/", { waitUntil: "networkidle" });
    const anim = await page.evaluate(() => getComputedStyle(document.querySelector(".aayna-mirror-circle")).animationName);
    rec("mirror sheen disabled under prefers-reduced-motion", anim === "none", `animation-name=${anim}`);
    await ctx.close();
  }

  // footer links navigate
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await ctx.newPage();
    await page.goto(AFTER + "/", { waitUntil: "networkidle" });
    await page.locator('footer nav[aria-label="All pages"] a[href="/returns"]').click();
    await page.waitForURL("**/returns");
    rec("footer nav link navigates (Returns)", page.url().endsWith("/returns"));
    await ctx.close();
  }

  // Preview panel is md+ only (hidden md:flex, by design). Tablet touch: tap, no hover.
  {
    const ctx = await browser.newContext({ viewport: { width: 1024, height: 1366 }, hasTouch: true, isMobile: true });
    const page = await ctx.newPage();
    await page.goto(AFTER + "/", { waitUntil: "networkidle" });
    await page.locator('[data-testid="mirror-category-bracelets"]').tap();
    const add = page.locator('[data-testid="mirror-preview-add"]');
    await add.waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
    const visible = await add.isVisible();
    rec("[1024 touch] tapping Bracelets shows preview with Add to Cart (no hover)", visible);
    if (visible) {
      const label = await add.innerText();
      await add.tap();
      await page.waitForTimeout(600);
      const badge = await page.locator('[data-testid="cart-count-badge"]').innerText().catch(() => "");
      const cart = JSON.parse(await page.evaluate(() => localStorage.getItem("aayna_cart")) || "[]");
      rec("[1024 touch] preview Add to Cart adds the previewed product", badge.trim() === "1" && cart.length === 1, `label="${label}" badge="${badge}" item=${cart[0]?.slug}`);
      await page.screenshot({ path: `${OUT}/mirror_preview_add_1024.png` });
    }
    await ctx.close();
  }
  // Mobile: preview panel hidden by design; tapping commits the category for the Your Edit section.
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    const page = await ctx.newPage();
    await page.goto(AFTER + "/", { waitUntil: "networkidle" });
    await page.locator('[data-testid="mirror-category-bracelets"]').tap();
    await page.waitForTimeout(1500);
    const pref = await page.evaluate(() => localStorage.getItem("aayna.selectedCategory"));
    const bracelet = await page.locator('main a[href^="/product/"]').evaluateAll((as) => as.map((a) => a.getAttribute("href")).filter((h) => /bracelet/.test(h)).length);
    rec("[390 touch] tapping Bracelets selects it and shows bracelet products", /bracelets/.test(pref || "") && bracelet > 0, `pref=${pref} braceletLinks=${bracelet}`);
    await page.screenshot({ path: `${OUT}/mirror_select_390.png`, fullPage: true });
    await ctx.close();
  }

  await browser.close();
  fs.writeFileSync(`${OUT}/layout_table.json`, JSON.stringify(table, null, 2));
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  console.log("\nwidth  label   overflow  h1");
  for (const t of table) console.log(`${String(t.w).padEnd(6)} ${t.label.padEnd(7)} ${t.sw > t.cw ? "+" + (t.sw - t.cw) + "px" : "none".padEnd(8)}  ${t.h1}`);
})();
