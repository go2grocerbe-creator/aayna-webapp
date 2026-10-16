// Static product photo delivery checks (lean MVP, Option B) on a PRODUCTION build.
//
//   PRODUCTS_JSON=fixture.json BASE_URL=http://localhost:3000 node scripts/verify/static_product_images.js <outDir>
//
// fixture.json (test database products):
//   {slug, sku, group, n, variations, category, kind:"static"}  - mapped SKU, no DB images
//   {slug, sku, kind:"db"}    - has its own DB image -> must keep it (DB wins)
//   {slug, sku, kind:"none"}  - unmapped SKU, no images -> fallback frame, no photo
// Checks on desktop and mobile: home, shop, categories, every product page, cart.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.argv[2] || "static-images-out";
const fixture = JSON.parse(fs.readFileSync(process.env.PRODUCTS_JSON, "utf8"));
const bySlug = Object.fromEntries(fixture.map((p) => [p.slug, p]));
const byName = {};
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};
const groupOf = (src) => ((src || "").match(/\/product-images\/([a-z0-9-]+)\//) || [])[1];
const varOf = (src) => Number(((src || "").match(/-(\d{2})-\d+\.webp/) || [])[1]);

// every product photo inside a link to /product/<slug> must belong to that slug's group
async function ownership(page, label) {
  const imgs = await page.$$eval('a[href^="/product/"] img', (els) => els.map((e) => ({
    href: e.closest("a").getAttribute("href"), src: e.currentSrc || e.getAttribute("src"),
    srcset: e.getAttribute("srcset"), loaded: e.complete && e.naturalWidth > 0, alt: e.alt })));
  let wrong = [], checked = 0;
  for (const i of imgs) {
    const p = bySlug[i.href.replace("/product/", "")];
    if (!p) continue;
    checked++;
    if (p.kind === "static" && (groupOf(i.src) !== p.group || !i.srcset || /\.(png|webp)$/i.test(i.alt))) wrong.push(`${p.slug}<-${i.src}`);
    if (p.kind !== "static" && groupOf(i.src)) wrong.push(`${p.slug} must not show static photo ${i.src}`);
    if (/crystal-stone-cuff-golden-04|naira/i.test(i.src || "")) wrong.push(`excluded photo ${i.src}`);
  }
  rec(`${label}: every product photo belongs to its own product (${checked} checked)`, wrong.length === 0, wrong.slice(0, 3).join("; "));
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  for (const vp of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.name === "mobile" ? 2 : 1 });
    const page = await ctx.newPage();
    const bad = [], fetched = [];
    page.on("response", (r) => {
      if (r.url().includes("/product-images/")) {
        fetched.push(r.url());
        if (r.status() !== 200 || !(r.headers()["content-type"] || "").includes("image/webp")) bad.push(`${r.status()} ${r.url()}`);
      }
    });
    const scrollAll = async () => { await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } }); await page.waitForTimeout(600); };

    // home: the visitor picks a category ("Your Edit"); on desktop, hovering shows a preview panel
    for (const label of ["Earrings", "Necklaces", "Rings"]) {
      await page.goto(BASE + "/", { waitUntil: "networkidle" });
      const btn = page.getByRole("button", { name: new RegExp(`^${label}$`) }).first();
      if (vp.name === "desktop") {
        await btn.hover();
        await page.waitForTimeout(800);
        const prev = await page.evaluate(() => {
          const name = document.querySelector(".animate-fade-up p.font-display")?.textContent?.trim();
          const img = document.querySelector(".animate-fade-up img");
          return { name, src: img?.getAttribute("src"), cur: img?.currentSrc, loaded: !!img && img.complete && img.naturalWidth > 0 };
        });
        const owner = Object.values(bySlug).find((p) => prev.name && prev.name.toLowerCase() === ("qa " + (p.group || "").replace(/-/g, " ")).toLowerCase());
        rec(`desktop home hover ${label}: preview photo belongs to the previewed product`,
          !prev.src || !groupOf(prev.src) || (owner && groupOf(prev.src) === owner.group && prev.loaded), `${prev.name} <- ${(prev.cur || prev.src || "").split("/").pop()}`);
      }
      await btn.click();
      await page.waitForTimeout(1200);
      await scrollAll();
      await ownership(page, `${vp.name} home "${label}" edit`);
      const shown = await page.$$eval('a[href^="/product/qa-"] img', (els) => els.length);
      rec(`${vp.name} home "${label}" edit: QA product photos rendered`, shown > 0, `${shown} photos`);
      if (label === "Earrings") await page.screenshot({ path: path.join(OUT, `home-${vp.name}.png`), fullPage: false });
      await page.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
    }
    for (const [label, url] of [["shop", "/shop"]]) {
      await page.goto(BASE + url, { waitUntil: "networkidle" });
      await scrollAll();
      await ownership(page, `${vp.name} ${label}`);
      await page.screenshot({ path: path.join(OUT, `${label}-${vp.name}.png`), fullPage: false });
    }
    for (const cat of [...new Set(fixture.filter((p) => p.category).map((p) => p.category))]) {
      await page.goto(`${BASE}/category/${cat}`, { waitUntil: "networkidle" });
      await scrollAll();
      await ownership(page, `${vp.name} /category/${cat}`);
      const notLoaded = await page.$$eval('a[href^="/product/qa-"] img', (els) => els.filter((e) => !(e.complete && e.naturalWidth > 0)).length);
      rec(`${vp.name} /category/${cat}: every QA card photo loaded`, notLoaded === 0, `${notLoaded} not loaded`);
    }

    for (const p of fixture) {
      await page.goto(`${BASE}/product/${p.slug}`, { waitUntil: "networkidle" });
      const name = (await page.textContent("h1")).trim();
      byName[name] = p;
      const main = page.getByTestId("product-main-image");
      if (p.kind === "none") {
        rec(`${vp.name} ${p.slug}: unmapped product shows the fallback frame, no photo`, (await main.count()) === 0);
        continue;
      }
      await main.waitFor();
      const m = await main.evaluate((el) => ({ src: el.getAttribute("src"), cur: el.currentSrc, w: el.naturalWidth, alt: el.alt }));
      if (p.kind === "db") {
        rec(`${vp.name} ${p.slug}: database image wins over the static gallery`, m.src === "/favicon.svg" && !groupOf(m.cur), m.src);
        continue;
      }
      const thumbs = await page.$$eval('[data-testid^="product-thumb-"] img', (els) => els.map((e) => e.getAttribute("src")));
      const order = thumbs.length ? thumbs.map(varOf) : [varOf(m.src)];
      rec(`${vp.name} ${p.sku}: main photo = first mapped variation, loads, own group, good alt`,
        groupOf(m.cur) === p.group && varOf(m.src) === p.variations[0] && m.w > 0 && m.alt.includes(name) && !/\.(png|webp)$/i.test(m.alt),
        `cur=${(m.cur || "").split("/").pop()} alt="${m.alt}"`);
      rec(`${vp.name} ${p.sku}: gallery order exactly ${p.variations.join(",")} and only its own photos`,
        JSON.stringify(order) === JSON.stringify(p.variations) && thumbs.every((s) => groupOf(s) === p.group)
        && (p.n > 1 ? thumbs.length === p.n : true), `order=${order}`);
    }

    // cart: add two mapped products, the cart shows each one's own primary photo
    const picks = fixture.filter((p) => p.kind === "static").slice(0, 2);
    for (const p of picks) {
      await page.goto(`${BASE}/product/${p.slug}`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: /^add to cart$/i }).first().click();
      await page.waitForTimeout(300);
    }
    await page.goto(`${BASE}/cart`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const cart = await page.$$eval("img", (els) => els.filter((e) => (e.getAttribute("src") || "").includes("/product-images/"))
      .map((e) => ({ src: e.getAttribute("src"), alt: e.alt, loaded: e.complete && e.naturalWidth > 0 })));
    const cartOk = cart.length === picks.length && cart.every((c) => byName[c.alt] && groupOf(c.src) === byName[c.alt].group && c.loaded
      && varOf(c.src) === byName[c.alt].variations[0]);
    rec(`${vp.name} cart: each item shows its own primary photo`, cartOk, cart.map((c) => `${c.alt}<-${(c.src || "").split("/").pop()}`).join("; "));
    await page.screenshot({ path: path.join(OUT, `cart-${vp.name}.png`), fullPage: false });
    await page.evaluate(() => localStorage.clear());

    rec(`${vp.name}: every /product-images request 200 image/webp`, bad.length === 0, `${fetched.length} fetched; bad: ${bad.slice(0, 3)}`);
    rec(`${vp.name}: no excluded photo requested (Naira, Crystal Stone Cuff 4)`, !fetched.some((u) => /naira|crystal-stone-cuff-golden-04/i.test(u)));
    const small = fetched.filter((u) => /-480\.webp/.test(u)).length, large = fetched.filter((u) => /-1200\.webp/.test(u)).length;
    rec(`${vp.name}: responsive renditions used (480w and 1200w both requested)`, small > 0 && large > 0, `480w=${small} 1200w=${large}`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    rec(`${vp.name}: no horizontal scroll on cart`, overflow <= 1, `${overflow}px`);
    await ctx.close();
  }
  await browser.close();
  const passed = results.filter(Boolean).length;
  console.log(`\n${passed}/${results.length} checks passed`);
  process.exit(passed === results.length ? 0 : 1);
})();
