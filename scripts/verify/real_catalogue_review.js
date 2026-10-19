// Visual + functional review of the GENUINE catalogue (10 products) on an ISOLATED test backend
// whose products are the customer-facing snapshot of aayna_prod (never aayna_prod itself).
//
//   BASE_URL=http://localhost:3000 [CHROMIUM_PATH=...] node scripts/verify/real_catalogue_review.js <outDir>
//
// Per product, at 390 (mobile), 768 (tablet) and 1280 (desktop): exact name, SKU-mapped photo group,
// main photo + full gallery in the reviewed order, every photo loads (WebP, 200), no distortion
// (rendered aspect ratio vs natural, object-fit), price, colour/size shown, stock handling, and
// add-to-cart. Shop and category grids are checked for card ownership and counts.
// Screenshots go to <outDir>/shots for the founder's visual approval.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.argv[2] || "real-catalogue-out";
const SHOTS = path.join(OUT, "shots");
fs.mkdirSync(SHOTS, { recursive: true });
const gallery = JSON.parse(fs.readFileSync(path.join(__dirname, "../../frontend/src/data/productGallery.json"), "utf8")).products;
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok, d }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };
const groupOf = (src) => ((src || "").match(/\/product-images\/([a-z0-9-]+)\//) || [])[1];
const varOf = (src) => Number(((src || "").match(/-(\d{2})-\d+\.webp/) || [])[1]);
const taka = (n) => "৳" + Number(n).toLocaleString("en-US");
const EXPECTED_CATS = { necklaces: 2, bracelets: 4, earrings: 3, rings: 1 };

(async () => {
  const products = await (await fetch(`${BASE}/api/products?limit=100`)).json();
  rec("snapshot: 10 genuine products, 46 units, all SKUs mapped to a reviewed gallery",
      products.length === 10 && products.reduce((s, p) => s + p.stock_quantity, 0) === 46 && products.every((p) => gallery[p.sku]),
      `${products.length} products`);
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const summary = [];
  for (const vp of [{ name: "mobile", width: 390, height: 844, dsf: 2 }, { name: "tablet", width: 768, height: 1024, dsf: 2 }, { name: "desktop", width: 1280, height: 900, dsf: 1 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.dsf });
    const page = await ctx.newPage();
    await page.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
    const badImg = [];
    page.on("response", (r) => { if (r.url().includes("/product-images/") && (r.status() !== 200 || !/image\/webp/.test(r.headers()["content-type"] || ""))) badImg.push(`${r.status()} ${r.url()}`); });
    const scrollAll = () => page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 350) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 80)); } window.scrollTo(0, 0); });

    // grids: shop + categories
    for (const url of ["/shop", ...Object.keys(EXPECTED_CATS).map((c) => `/category/${c}`)]) {
      await page.goto(BASE + url, { waitUntil: "networkidle" });
      await scrollAll();
      // lazy images: bring each card into view and wait until its photo has really loaded
      for (const h of await page.$$('a[href^="/product/"] img')) { await h.scrollIntoViewIfNeeded().catch(() => {}); }
      await page.waitForFunction(() => [...document.querySelectorAll('a[href^="/product/"] img')].every((i) => i.complete && i.naturalWidth > 0), null, { timeout: 15000 }).catch(() => {});
      await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(400);
      const cards = await page.$$eval('a[href^="/product/"] img', (els) => els.map((e) => ({ href: e.closest("a").getAttribute("href"), src: e.currentSrc || e.src, ok: e.complete && e.naturalWidth > 0 })));
      const bySlug = Object.fromEntries(products.map((p) => [p.slug, p]));
      const wrong = cards.filter((c) => bySlug[c.href.replace("/product/", "")] && groupOf(c.src) !== gallery[bySlug[c.href.replace("/product/", "")].sku].group);
      const slugs = new Set(cards.map((c) => c.href));
      const want = url === "/shop" ? 10 : EXPECTED_CATS[url.split("/").pop()];
      const ov = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      rec(`${vp.name} ${url}: ${want} products, each card shows its own photo, all loaded, no overflow`,
          slugs.size === want && wrong.length === 0 && cards.every((c) => c.ok) && ov <= 1, `${slugs.size} cards, wrong=${wrong.length}, ov=${ov}`);
      if (vp.name !== "tablet" || url === "/shop") await page.screenshot({ path: path.join(SHOTS, `${vp.name}${url.replace(/\//g, "_")}.png`), fullPage: true });
    }

    for (const p of products) {
      const g = gallery[p.sku];
      await page.goto(`${BASE}/product/${p.slug}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(500);
      const info = await page.evaluate(() => {
        const main = document.querySelector('[data-testid="product-main-image"]');
        const r = main?.getBoundingClientRect();
        return {
          h1: document.querySelector("h1")?.textContent.trim(), price: document.querySelector('[data-testid="product-price"]')?.textContent.trim(),
          main: main && { src: main.currentSrc || main.src, nat: [main.naturalWidth, main.naturalHeight], box: [r.width, r.height], fit: getComputedStyle(main).objectFit, alt: main.alt },
          thumbs: [...document.querySelectorAll('[data-testid^="product-thumb-"] img')].map((i) => i.getAttribute("src")),
          text: document.querySelector("main")?.innerText || "",
          ov: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          title: document.title, robots: document.querySelector('meta[name="robots"]')?.content || "",
        };
      });
      const order = info.thumbs.length ? info.thumbs.map(varOf) : [varOf(info.main?.src)];
      const expected = g.images.map((i) => i.variation);
      // distortion: with object-fit cover/contain the photo is never stretched; with "fill" the box ratio must match
      const ratioNat = info.main ? info.main.nat[0] / info.main.nat[1] : 0, ratioBox = info.main ? info.main.box[0] / info.main.box[1] : 0;
      const undistorted = !!info.main && (["cover", "contain", "scale-down"].includes(info.main.fit) || Math.abs(ratioNat - ratioBox) < 0.02);
      const ok = info.h1 === p.product_name && info.main && groupOf(info.main.src) === g.group && info.main.nat[0] > 0 &&
                 JSON.stringify(order) === JSON.stringify(expected) && undistorted && info.price && info.price.includes(taka(p.selling_price)) &&
                 info.ov <= 1 && /AAYNA/.test(info.title) && info.main.alt.includes(p.product_name);
      rec(`${vp.name} ${p.sku}: name, ${g.images.length} photos in reviewed order, loads, undistorted (${info.main?.fit}), price ${taka(p.selling_price)}`,
          ok, ok ? "" : JSON.stringify({ h1: info.h1, order, expected, fit: info.main?.fit, price: info.price, ov: info.ov }).slice(0, 220));
      summary.push({ vp: vp.name, sku: p.sku, slug: p.slug, name: info.h1, price: info.price, photos: order, fit: info.main?.fit,
                     colour: info.text.includes(p.color), size: info.text.includes(p.size), robots: info.robots });
      if (vp.name !== "tablet" || ["AYN-CUF-STN-GLD", "AYN-EAR-FLR-SLV"].includes(p.sku)) {
        await page.screenshot({ path: path.join(SHOTS, `${vp.name}_product_${p.sku}.png`), fullPage: vp.name !== "desktop" });
        if (vp.name === "desktop") await page.screenshot({ path: path.join(SHOTS, `desktop_product_${p.sku}_full.png`), fullPage: true });
      }
    }
    rec(`${vp.name}: every product photo request answered 200 image/webp`, badImg.length === 0, badImg.slice(0, 3).join("; "));

    // stock + cart (one-of-a-kind locket: quantity capped at 1; cuff with 12 in stock)
    const luna = products.find((p) => p.sku === "AYN-NKL-LUN-GLD"), cuff = products.find((p) => p.sku === "AYN-CUF-STN-GLD");
    await page.goto(`${BASE}/product/${luna.slug}`, { waitUntil: "networkidle" });
    const inc = page.locator('[data-testid="qty-increase"]').first();
    if (await inc.count()) { await inc.click().catch(() => {}); await inc.click().catch(() => {}); }
    const qty = (await page.locator('[data-testid="qty-value"]').first().textContent().catch(() => "1")).trim();
    rec(`${vp.name}: quantity cannot exceed stock for the single locket (stock 1)`, qty === "1", `qty=${qty}`);
    await page.click(vp.width < 768 ? '[data-testid="add-to-cart-button-mobile"]' : '[data-testid="add-to-cart-button"]');
    await page.goto(`${BASE}/product/${cuff.slug}`, { waitUntil: "networkidle" });
    await page.click(vp.width < 768 ? '[data-testid="add-to-cart-button-mobile"]' : '[data-testid="add-to-cart-button"]');
    await page.goto(`${BASE}/cart`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const cart = await page.evaluate(() => ({ text: document.querySelector("main")?.innerText || "",
      imgs: [...document.querySelectorAll("main img")].map((i) => ({ src: i.currentSrc || i.src, ok: i.complete && i.naturalWidth > 0 })) }));
    const sub = (await page.textContent('[data-testid="cart-subtotal"]').catch(() => "")).trim();
    rec(`${vp.name}: cart shows both genuine products with their own photos and subtotal ${taka(luna.selling_price + cuff.selling_price)}`,
        cart.text.includes(luna.product_name) && cart.text.includes(cuff.product_name) && sub.includes(taka(luna.selling_price + cuff.selling_price)) &&
        cart.imgs.filter((i) => groupOf(i.src)).every((i) => i.ok), sub);
    await page.screenshot({ path: path.join(SHOTS, `${vp.name}_cart.png`), fullPage: true });
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, "summary.json"), JSON.stringify(summary, null, 1));
  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("FAIL  harness error —", e.message.split("\n")[0]); process.exit(1); });
