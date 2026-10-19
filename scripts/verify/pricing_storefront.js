// Cost-based pricing: storefront/cart/checkout/admin consistency on a PRODUCTION build
// against a TEST backend. Expected prices are public selling prices only (no costs).
//
//   PRICES_JSON=prices.json BASE_URL=http://localhost:3000 API=http://localhost:8001/api \
//   ADMIN_EMAIL=... ADMIN_PASSWORD=... HIST=ORD-1001:3077 node scripts/verify/pricing_storefront.js <outDir>
//
// prices.json: [{ "slug": "...", "sku": "...", "name": "...", "price": 1350, "old_price": 999 }]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = process.env.API || "http://localhost:8001/api";
const OUT = process.argv[2] || "pricing-out";
const PRICES = JSON.parse(fs.readFileSync(process.env.PRICES_JSON, "utf8"));
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};
// identical to frontend/src/lib/format.js formatBDT
const bdt = (n) => `৳${Number(n || 0).toLocaleString("en-US")}`;
const SECRETS = ["cost_price", "\"pricing\"", "price_history", "previous_selling_price", "adjusted_cost",
  "gross_profit", "gross_margin", "unrounded_price", "round_up_to", "multiplier", "internal_notes", "inventory_xlsx", "supplier"];
const api = (p, opt = {}) => fetch(API + p, opt).then((r) => r.json());

(async () => {
  const { token } = await api("/admin/login", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD }) });
  const admin = (p) => api(p, { headers: { Authorization: `Bearer ${token}` } });
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });

  for (const vp of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await ctx.newPage();
    const leaks = [];
    page.on("response", async (r) => {
      const u = r.url();
      if (!u.startsWith(API) || u.includes("/admin/")) return;
      try { const body = await r.text(); SECRETS.forEach((s) => body.includes(s) && leaks.push(`${s} in ${u.replace(API, "")}`)); } catch {}
    });

    // product pages
    for (const p of PRICES) {
      await page.goto(`${BASE}/product/${p.slug}`, { waitUntil: "networkidle" });
      const shown = (await page.getByTestId("product-price").innerText()).trim();
      const visible = await page.getByTestId("product-price").isVisible();
      rec(`${vp.name} PDP ${p.sku}: shows ${bdt(p.price)}`, shown === bdt(p.price) && visible, `shown "${shown}"`);
    }
    await page.screenshot({ path: path.join(OUT, `pdp-${vp.name}.png`) });

    // listings: /shop ("The Edit": earrings, necklaces, rings, bracelets) and every category page.
    // Each product must appear on at least one listing, always with its new price, never the old one.
    const cards = [];
    const cats = [...new Set((await api("/products?limit=100")).filter((x) => PRICES.some((p) => p.sku === x.sku)).map((x) => x.category_slug))];
    for (const url of ["/shop", ...cats.map((c) => `/category/${c}`)]) {
      await page.goto(BASE + url, { waitUntil: "networkidle" });
      for (let y = 0; y < 8000; y += 500) { await page.evaluate((v) => window.scrollTo(0, v), y); await page.waitForTimeout(40); }
      (await page.$$eval('a[href^="/product/"]', (as) => as.map((a) => ({ href: a.getAttribute("href"),
        text: (a.closest("article, li, div")?.innerText || a.innerText || "").replace(/\s+/g, " ") }))))
        .forEach((c) => cards.push({ ...c, url }));
      if (url === "/shop") await page.screenshot({ path: path.join(OUT, `shop-${vp.name}.png`) });
    }
    let cardFails = [], seen = 0;
    for (const p of PRICES) {
      const mine = cards.filter((c) => c.href === `/product/${p.slug}` && /৳/.test(c.text));
      if (!mine.length) continue;
      seen++;
      if (!mine.every((c) => c.text.includes(bdt(p.price)) && !c.text.includes(bdt(p.old_price)))) cardFails.push(p.sku);
    }
    const onShop = new Set(cards.filter((c) => c.url === "/shop").map((c) => c.href));
    rec(`${vp.name} listing cards show the new price (${seen}/${PRICES.length} listed; ${PRICES.filter((p) => onShop.has(`/product/${p.slug}`)).length} on /shop)`,
      seen === PRICES.length && !cardFails.length, cardFails.join(","));
    const missingOnShop = PRICES.filter((p) => !onShop.has(`/product/${p.slug}`)).map((p) => p.sku);
    rec(`${vp.name} /shop "All" lists every active product, cuffs and bracelets included`, missingOnShop.length === 0, missingOnShop.join(","));

    // existing category chips still work and still scope to one category
    await page.goto(`${BASE}/shop`, { waitUntil: "networkidle" });
    const chips = await page.$$eval('[data-testid^="the-edit-cat-"]', (els) => els.map((e) => e.getAttribute("data-testid").replace("the-edit-cat-", "")));
    await page.click('[data-testid="the-edit-cat-earrings"]');
    await page.waitForTimeout(900);
    const hrefs = await page.$$eval('a[href^="/product/"]', (as) => [...new Set(as.map((a) => a.getAttribute("href")))]);
    const catOf = Object.fromEntries((await api("/products?limit=100")).map((x) => [`/product/${x.slug}`, x.category_slug]));
    const nonEar = hrefs.filter((h) => catOf[h] && catOf[h] !== "earrings");
    rec(`${vp.name} category chips unchanged (${chips.join(",")}); Earrings chip shows only earrings`,
      chips.join(",") === "earrings,necklaces,rings,bracelets" && hrefs.some((h) => catOf[h] === "earrings") && nonEar.length === 0, nonEar.join(","));

    // all 10 products in one cart (qty 1, saved at the OLD price): every line, the subtotal and the
    // checkout total use the intended prices. Not submitted (keeps test stock for the order below).
    const products = await api("/products?limit=100");
    const all = PRICES.map((p) => ({ ...p, prod: products.find((x) => x.sku === p.sku) })).filter((p) => p.prod && p.prod.stock_quantity > 0);
    await page.evaluate((items) => localStorage.setItem("aayna_cart", JSON.stringify(items)), all.map((p) => ({
      product_id: p.prod.id, slug: p.slug, name: p.prod.product_name, image: "", sku: p.sku,
      selling_price: p.old_price, discount_price: null, unit_price: p.old_price, stock: p.prod.stock_quantity, quantity: 1 })));
    await page.goto(`${BASE}/cart`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    const allSub = all.reduce((s, p) => s + p.price, 0);
    const badLines = [];
    for (const p of all) {
      const t = (await page.getByTestId(`cart-item-${p.slug}`).innerText()).replace(/\s+/g, " ");
      if (!t.includes(bdt(p.price))) badLines.push(p.sku);
    }
    const allShown = (await page.getByTestId("cart-subtotal").innerText()).trim();
    rec(`${vp.name} cart with all ${all.length} products: each line + subtotal ${bdt(allSub)}`, all.length === PRICES.length && !badLines.length && allShown === bdt(allSub), `shown "${allShown}" bad=${badLines}`);
    await page.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
    await page.click('[data-testid="checkout-district"]');
    await page.locator('[role="option"]').filter({ hasText: "Dhaka" }).first().click();
    await page.waitForTimeout(500);
    const allSrv = await api("/cart/validate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ district: "Dhaka", items: all.map((p) => ({ product_id: p.prod.id, quantity: 1 })) }) });
    const allTotal = (await page.getByTestId("checkout-total").innerText()).trim();
    const coText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    rec(`${vp.name} checkout with all ${all.length}: lines + total ${bdt(allSrv.total)} = server`, allSrv.subtotal === allSub && allTotal === bdt(allSrv.total)
      && all.every((p) => coText.includes(`${bdt(p.price)} × 1`)), `shown "${allTotal}"`);
    await page.screenshot({ path: path.join(OUT, `checkout-all-${vp.name}.png`), fullPage: true });

    // stale cart: saved in the browser at the OLD price -> cart/checkout must show the server price
    // two products with enough stock for qty 1 and 2 (orders placed by this script consume test stock)
    const pick = PRICES.map((p) => ({ ...p, prod: products.find((x) => x.sku === p.sku) }))
      .filter((p) => p.prod && p.prod.stock_quantity >= 4).slice(0, 2).map((p, i) => ({ ...p, qty: i + 1 }));
    await page.evaluate((items) => localStorage.setItem("aayna_cart", JSON.stringify(items)), pick.map((p) => ({
      product_id: p.prod.id, slug: p.slug, name: p.prod.product_name, image: "", sku: p.sku,
      selling_price: p.old_price, discount_price: null, unit_price: p.old_price, stock: p.prod.stock_quantity, quantity: p.qty })));
    const expSub = pick.reduce((s, p) => s + p.price * p.qty, 0);
    await page.goto(`${BASE}/cart`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const sub = (await page.getByTestId("cart-subtotal").innerText()).trim();
    rec(`${vp.name} cart: stale browser price replaced, subtotal ${bdt(expSub)}`, sub === bdt(expSub), `shown "${sub}"`);
    const lineOk = [];
    for (const p of pick) {
      const t = (await page.getByTestId(`cart-item-${p.slug}`).innerText()).replace(/\s+/g, " ");
      lineOk.push(t.includes(bdt(p.price * p.qty)) && !t.includes(bdt(p.old_price * p.qty)));
    }
    rec(`${vp.name} cart: each line total = new price × qty`, lineOk.every(Boolean));
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("aayna_cart")));
    rec(`${vp.name} cart: saved cart now holds the server price`, stored.every((s) => pick.find((p) => p.sku === s.sku).price === s.unit_price));
    await page.screenshot({ path: path.join(OUT, `cart-${vp.name}.png`), fullPage: true });

    // checkout total = server subtotal + delivery
    await page.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
    await page.fill('[data-testid="checkout-name"]', "QA Pricing Test");
    await page.fill('[data-testid="checkout-phone"]', "01700000001");
    await page.click('[data-testid="checkout-district"]');
    await page.locator('[role="option"]').filter({ hasText: "Dhaka" }).first().click();
    await page.fill('[data-testid="checkout-address"]', "House 1, Road 1, Test Area");
    await page.waitForTimeout(400);
    const server = await api("/cart/validate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ district: "Dhaka", items: pick.map((p) => ({ product_id: p.prod.id, quantity: p.qty })) }) });
    const shownTotal = (await page.getByTestId("checkout-total").innerText()).trim();
    rec(`${vp.name} checkout total = server total ${bdt(server.total)}`, server.subtotal === expSub && shownTotal === bdt(server.total), `shown "${shownTotal}"`);
    await page.screenshot({ path: path.join(OUT, `checkout-${vp.name}.png`), fullPage: true });
    await page.click('[data-testid="place-order-button"]');
    await page.waitForURL("**/order-confirmation/**", { timeout: 15000 });
    await page.waitForSelector('[data-testid="confirmation-total"]');
    const confTotal = (await page.getByTestId("confirmation-total").innerText()).trim();
    const num = (await page.getByTestId("confirmation-order-number").innerText()).trim();
    rec(`${vp.name} order ${num}: confirmation total ${bdt(server.total)}`, confTotal === bdt(server.total), `shown "${confTotal}"`);
    const ord = (await admin(`/admin/orders?search=${encodeURIComponent(num)}`));
    const o = (ord.orders || ord.items || ord).find?.((x) => x.order_number === num);
    rec(`${vp.name} order ${num}: stored total_amount = ${server.total}`, o && o.total_amount === server.total, o ? `${o.total_amount}` : JSON.stringify(ord).slice(0, 120));
    await page.screenshot({ path: path.join(OUT, `confirmation-${vp.name}.png`), fullPage: true });

    rec(`${vp.name}: no cost/pricing/internal fields in any public API response`, leaks.length === 0, leaks.slice(0, 3).join("; "));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    rec(`${vp.name}: no horizontal scroll on confirmation`, overflow <= 1, `${overflow}px`);
    await ctx.close();
  }

  // admin: product list shows the same price as the database
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.addInitScript((t) => localStorage.setItem("aayna_admin_token", t), token);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/admin/products`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const rows = await page.$$eval("tr", (trs) => trs.map((t) => t.innerText.replace(/\s+/g, " ")));
  const bad = PRICES.filter((p) => !rows.some((r) => r.includes(p.sku) && r.includes(bdt(p.price))));
  rec(`admin products list shows the new price for all ${PRICES.length} SKUs`, bad.length === 0, bad.map((b) => b.sku).join(","));
  await page.screenshot({ path: path.join(OUT, "admin-products.png"), fullPage: true });
  await ctx.close();

  // historical order keeps the price it was placed at
  if (process.env.HIST) {
    const [num, total] = process.env.HIST.split(":");
    const ord = await admin(`/admin/orders?search=${encodeURIComponent(num)}`);
    const o = (ord.orders || ord.items || ord).find?.((x) => x.order_number === num);
    rec(`historical order ${num} total unchanged (${total})`, o && Number(o.total_amount) === Number(total), o ? `${o.total_amount}` : "not found");
  }

  await browser.close();
  const passed = results.filter(Boolean).length;
  console.log(`\n${passed}/${results.length} checks passed`);
  process.exit(passed === results.length ? 0 : 1);
})();
