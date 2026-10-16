// Product photo checks for cards and the product-page gallery (Playwright, read-only UI).
//
//   PRODUCTS_JSON=fixture.json BASE_URL=http://localhost:3000 node scripts/verify/product_gallery.js <outDir>
//
// fixture.json: [{ "slug", "group", "n", "primary_var", "category" }] - test products whose
// image URLs contain "/<group>/<group>-<NN>.<ext>". For each product, at desktop and mobile:
//   * main photo loads, belongs to this product's group, is the primary (is_main) photo,
//     is shown whole (object-fit: contain) and has descriptive alt text (not a filename)
//   * exactly n thumbnails, all from this product's group, each switches the main photo
//   * thumbnails are >= 44px and keyboard-labelled; no horizontal page scroll
//   * the category card shows this product's primary photo (never another product's)
//   * opening another product after picking a thumbnail starts at that product's primary
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.argv[2] || "gallery-out";
const products = JSON.parse(fs.readFileSync(process.env.PRODUCTS_JSON, "utf8"));
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};
const groupOf = (src) => (src.match(/\/([a-z0-9-]+)\/[a-z0-9-]+-(\d{2})\.\w+$/) || [])[1];
const varOf = (src) => Number((src.match(/-(\d{2})\.\w+$/) || [])[1]);

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  for (const vp of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    for (const p of products) {
      const tag = `${vp.name} ${p.slug}`;
      await page.goto(`${BASE}/product/${p.slug}`, { waitUntil: "networkidle" });
      const main = page.getByTestId("product-main-image");
      await main.waitFor();
      const m = await main.evaluate((el) => ({ src: el.currentSrc || el.src, alt: el.alt, w: el.naturalWidth,
        fit: getComputedStyle(el).objectFit, name: document.querySelector("h1")?.textContent || "" }));
      rec(`${tag}: main photo loads, own group, primary #${p.primary_var}, whole photo, good alt`,
        m.w > 0 && groupOf(m.src) === p.group && varOf(m.src) === p.primary_var && m.fit === "contain"
        && !/\.(png|jpe?g|webp)$/i.test(m.alt) && m.alt.includes(m.name.trim()),
        `group=${groupOf(m.src)} var=${varOf(m.src)} fit=${m.fit} alt="${m.alt}"`);
      const thumbs = page.locator('[data-testid^="product-thumb-"]');
      const n = await thumbs.count();
      const tsrc = await thumbs.locator("img").evaluateAll((els) => els.map((e) => e.getAttribute("src")));
      const sizes = await thumbs.evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height); }));
      const labels = await thumbs.evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
      rec(`${tag}: ${p.n} thumbnails, all this product's photos, >=44px, labelled`,
        n === p.n && tsrc.every((s) => groupOf(s) === p.group) && new Set(tsrc).size === p.n
        && sizes.every((s) => s >= 44) && labels.every((l) => /^Show image \d+ of \d+$/.test(l || "")),
        `n=${n} groups=${[...new Set(tsrc.map(groupOf))]} minSize=${Math.round(Math.min(...sizes))}`);
      let switched = true;
      for (let i = 0; i < n; i++) {
        await thumbs.nth(i).click();
        const s = await main.evaluate((el) => el.getAttribute("src"));
        const pressed = await thumbs.nth(i).getAttribute("aria-pressed");
        if (s !== tsrc[i] || pressed !== "true" || groupOf(s) !== p.group) switched = false;
      }
      await main.evaluate((el) => el.decode && el.decode().catch(() => {}));
      rec(`${tag}: every thumbnail switches the main photo (aria-pressed)`, switched);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      rec(`${tag}: no horizontal scroll`, overflow <= 1, `overflow=${overflow}px`);
      if (["qa-classic-statement-ring-golden", "qa-floral-charm-silver-bracelet"].includes(p.slug)) {
        await thumbs.nth(0).click();
        await page.waitForTimeout(400);
        await page.screenshot({ path: path.join(OUT, `pdp-${vp.name}-${p.slug}.png`), fullPage: false });
      }
    }
    // reset on navigation: pick the last thumbnail of product A, open product B
    const [a, b] = products;
    await page.goto(`${BASE}/product/${a.slug}`, { waitUntil: "networkidle" });
    await page.locator('[data-testid^="product-thumb-"]').last().click();
    await page.goto(`${BASE}/product/${b.slug}`, { waitUntil: "networkidle" });
    const bsrc = await page.getByTestId("product-main-image").getAttribute("src");
    rec(`${vp.name}: opening another product starts at its primary photo`, groupOf(bsrc) === b.group && varOf(bsrc) === b.primary_var, bsrc);
    // cards
    for (const cat of [...new Set(products.map((p) => p.category))]) {
      await page.goto(`${BASE}/category/${cat}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(500);
      for (const p of products.filter((x) => x.category === cat)) {
        const card = page.locator(`a[href="/product/${p.slug}"] img`).first();
        if (!(await card.count())) { rec(`${vp.name} card ${p.slug}: present`, false, "not rendered"); continue; }
        await card.scrollIntoViewIfNeeded();
        await page.waitForFunction((s) => { const i = document.querySelector(`a[href="/product/${s}"] img`); return i && i.complete && i.naturalWidth > 0; }, p.slug, { timeout: 10000 }).catch(() => {});
        const c = await card.evaluate((el) => ({ src: el.getAttribute("src"), alt: el.alt, w: el.naturalWidth }));
        rec(`${vp.name} card ${p.slug}: primary photo of this product, loads, good alt`,
          c.w > 0 && groupOf(c.src) === p.group && varOf(c.src) === p.primary_var && !/\.(png|jpe?g|webp)$/i.test(c.alt),
          `group=${groupOf(c.src)} var=${varOf(c.src)} alt="${c.alt}"`);
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      rec(`${vp.name} /category/${cat}: no horizontal scroll`, overflow <= 1, `overflow=${overflow}px`);
      await page.screenshot({ path: path.join(OUT, `category-${vp.name}-${cat}.png`), fullPage: false });
    }
    await ctx.close();
  }
  await browser.close();
  const passed = results.filter(Boolean).length;
  console.log(`\n${passed}/${results.length} checks passed`);
  process.exit(passed === results.length ? 0 : 1);
})();
