// Product descriptions (admin editor -> storefront -> SEO) and Steadfast financials (admin-only),
// in a real browser against an ISOLATED backend (real-catalogue snapshot, STEADFAST_MODE=mock).
//
//   BASE_URL=http://localhost:3000 ADMIN_EMAIL=... ADMIN_PASSWORD=... ROLE_USERS_JSON=... \
//   [CHROMIUM_PATH=...] node scripts/verify/content_finance_ui.js <outDir>
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const API = `${BASE}/api`;
const OUT = process.argv[2] || "content-finance-out";
const SHOTS = path.join(OUT, "shots");
fs.mkdirSync(SHOTS, { recursive: true });
const USERS = process.env.ROLE_USERS_JSON ? JSON.parse(fs.readFileSync(process.env.ROLE_USERS_JSON, "utf8")) : {};
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
const text = async (page, sel) => ((await page.textContent(sel).catch(() => "")) || "").replace(/\s+/g, " ").trim();
const BN = "সোনালি রঙের সাহসী কানের দুল।";

async function api(method, p, { token, body } = {}) {
  const r = await fetch(API + p, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}
async function adminPage(browser, email, password, width = 1280) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="admin-login-email"]', email);
  await page.fill('[data-testid="admin-login-password"]', password);
  await page.click('[data-testid="admin-login-submit"]');
  await page.waitForURL(/\/admin\/?$/, { timeout: 20000 });
  return { ctx, page };
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const admin = (await api("POST", "/admin/login", { body: { email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD } })).json.token;
  const products = await (await fetch(`${API}/products?limit=100`)).json();
  const P = products.find((p) => p.sku === "AYN-EAR-CHK-GLD");
  rec("setup: genuine catalogue with Bold Chunky Earrings at ৳970", !!P && P.selling_price === 970);

  // ---- 1. Admin description editor ------------------------------------------------------
  const { ctx: actx, page: ap } = await adminPage(browser, process.env.ADMIN_EMAIL, process.env.ADMIN_PASSWORD);
  await ap.goto(`${BASE}/admin/products/${P.id}`, { waitUntil: "networkidle" });
  await ap.waitForSelector('[data-testid="pf-content"]');
  rec("editor shows the product has no description yet", /No description yet/.test(await text(ap, '[data-testid="pf-content-status"]')));
  const before = (await api("GET", `/admin/products/${P.id}`, { token: admin })).json;
  await ap.fill('[data-testid="pf-full"]', "<b>bold</b> claim");
  await ap.click('[data-testid="pf-save"]');
  await sleep(1200);
  const afterBad = (await api("GET", `/admin/products/${P.id}`, { token: admin })).json;
  rec("markup is refused by the server and nothing is saved", afterBad.full_description === before.full_description && /\/admin\/products\//.test(ap.url()));
  await ap.fill('[data-testid="pf-short"]', "Bold golden earrings for everyday wear.");
  await ap.fill('[data-testid="pf-full"]', `A rounded, chunky silhouette in a golden colour.\n\n${BN}`);
  await ap.fill('[data-testid="pf-highlights"]', "Sold as a pair\nAbout 1 inch per earring");
  await ap.fill('[data-testid="pf-seo-title"]', "Bold Chunky Golden Earrings");
  await ap.fill('[data-testid="pf-seo-description"]', "Bold, chunky golden earrings from AAYNA. Cash on delivery across Bangladesh.");
  rec("completeness indicator updates as the founder writes", /Description complete/.test(await text(ap, '[data-testid="pf-content-status"]')));
  await ap.click('[data-testid="pf-preview-toggle"]');
  const prev = await text(ap, '[data-testid="pf-preview"]');
  rec("customer preview renders paragraphs, Bengali text and product details before saving", prev.includes(BN) && prev.includes("Sold as a pair") && prev.includes("chunky silhouette"));
  await ap.screenshot({ path: path.join(SHOTS, "admin-description-editor-1280.png"), fullPage: true });
  await ap.click('[data-testid="pf-save"]');
  await ap.waitForURL(/\/admin\/products\/?$/, { timeout: 15000 });
  const saved = (await api("GET", `/admin/products/${P.id}`, { token: admin })).json;
  rec("saved: text cleaned, status unchanged, history recorded",
      saved.full_description.includes(BN) && saved.highlights.length === 2 && saved.status === before.status && saved.content_status.status === "complete" &&
      (await api("GET", `/admin/products/${P.id}/content-history`, { token: admin })).json.length >= 1);
  await ap.waitForSelector(`[data-testid="content-status-${P.sku}"]`);
  rec("product list marks the description complete; others show 'No description'",
      /Description ✓/.test(await text(ap, `[data-testid="content-status-${P.sku}"]`)) && /No description/.test(await text(ap, "table")));

  // ---- 2. Storefront presentation + SEO --------------------------------------------------
  for (const width of [390, 1280]) {
    const ctx = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 } });
    const page = await ctx.newPage();
    await page.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
    await page.goto(`${BASE}/product/${P.slug}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="product-description"]');
    const d = await text(page, '[data-testid="product-description"]');
    const meta = await page.evaluate(() => ({ title: document.title, desc: document.querySelector('meta[name="description"]')?.content,
      ld: [...document.querySelectorAll('script[type="application/ld+json"]')].map((s) => JSON.parse(s.textContent)).find((j) => j["@type"] === "Product") }));
    rec(`${width}px product page: description + Bengali + details shown, no overflow`, d.includes("chunky silhouette") && d.includes(BN) && d.includes("Sold as a pair") && (await overflow(page)) <= 1);
    rec(`${width}px SEO: founder's title/description used; JSON-LD has verified fields only, price ৳970`,
        meta.title === "Bold Chunky Golden Earrings | AAYNA" && meta.desc.startsWith("Bold, chunky golden earrings") &&
        meta.ld.offers.price === "970" && !("material" in meta.ld) && !("aggregateRating" in meta.ld) && !("review" in meta.ld));
    await page.screenshot({ path: path.join(SHOTS, `product-description-${width}.png`), fullPage: true });
    // a product without a description keeps working with the factual fallback
    const other = products.find((p) => p.sku === "AYN-RNG-CLS-GLD");
    await page.goto(`${BASE}/product/${other.slug}`, { waitUntil: "networkidle" });
    const od = await page.evaluate(() => document.querySelector('meta[name="description"]')?.content || "");
    rec(`${width}px product without description: details still shown, factual meta fallback`,
        /Aayna Classic Statement Ring — Rings at AAYNA/.test(od) && (await text(page, '[data-testid="pd-details"]')).includes("0.7"));
    await ctx.close();
  }

  // ---- 3. Steadfast financials ------------------------------------------------------------
  const ord = (await api("POST", "/checkout", { body: { customer_name: "Finance Test", customer_phone: "01755000970", customer_email: "", district: "Khulna",
    payment_method: "cod", delivery_address: "House 9, Test Road, Khulna (test)", items: [{ product_id: P.id, quantity: 1 }] } })).json;
  const n = ord.order_number;
  await api("PUT", `/admin/orders/${n}`, { token: admin, body: { order_status: "Packed" } });
  const bk = await api("POST", `/admin/orders/${n}/courier/book`, { token: admin, body: { confirm: true } });
  rec("simulated booking: COD ৳1,070 (৳970 + ৳100 delivery)", bk.json?.courier?.cod_amount === 1070);
  await api("POST", `/admin/orders/${n}/courier/mock`, { token: admin, body: { action: "set_status", status: "delivered" } });
  await api("POST", `/admin/orders/${n}/courier/sync`, { token: admin });
  await ap.goto(`${BASE}/admin/orders/${n}`, { waitUntil: "networkidle" });
  await ap.waitForSelector('[data-testid="steadfast-finance"]');
  rec("finance panel: unknown fees shown as pending, not ৳0; status not 'paid'",
      /Pending provider confirmation/.test(await text(ap, '[data-testid="fin-delivery-fee"]')) && /Pending provider confirmation/.test(await text(ap, '[data-testid="fin-expected"]')) &&
      /Not enough information/.test(await text(ap, '[data-testid="fin-status"]')));
  await ap.click('[data-testid="fin-open-amounts"]');
  await ap.fill('[data-testid="fin-cod_collected"]', "1070");
  await ap.fill('[data-testid="fin-delivery_fee"]', "110");
  await ap.fill('[data-testid="fin-cod_fee"]', "10.70");
  await ap.fill('[data-testid="fin-reference"]', "STMT-TEST-1");
  await ap.click('[data-testid="fin-submit"]');
  await ap.waitForFunction(() => /Charges confirmed/.test(document.querySelector('[data-testid="fin-status"]')?.textContent || ""), null, { timeout: 10000 });
  rec("after statement entry: expected settlement ৳949.30 (1,070 − 110 − 10.70)", (await text(ap, '[data-testid="fin-expected"]')).includes("949.3"));
  await ap.click('[data-testid="fin-open-payout"]');
  await ap.fill('[data-testid="fin-amount"]', "940");
  await ap.fill('[data-testid="fin-reference"]', "PAY-TEST-9");
  await ap.click('[data-testid="fin-submit"]');
  await ap.waitForFunction(() => /Payout recorded/.test(document.querySelector('[data-testid="fin-status"]')?.textContent || ""), null, { timeout: 10000 });
  rec("payout recorded: difference −৳9.30 highlighted", (await text(ap, '[data-testid="fin-difference"]')).includes("9.3"));
  await ap.click('[data-testid="fin-open-reconcile"]');
  await ap.click('[data-testid="fin-submit"]');
  await sleep(800);
  rec("reconciling a difference without a reason is refused", /Payout recorded/.test(await text(ap, '[data-testid="fin-status"]')));
  await ap.fill('[data-testid="fin-note"]', "Steadfast rounding, confirmed with support (test)");
  await ap.click('[data-testid="fin-submit"]');
  await ap.waitForFunction(() => /Reconciled/.test(document.querySelector('[data-testid="fin-status"]')?.textContent || ""), null, { timeout: 10000 });
  rec("reconciled with a reason; history lists every step", (await text(ap, '[data-testid="fin-history"]')).includes("(3)"));
  rec("order page has no horizontal overflow", (await overflow(ap)) <= 1);
  await ap.screenshot({ path: path.join(SHOTS, "admin-finance-reconciled-1280.png"), fullPage: true });
  await ap.goto(`${BASE}/admin/courier-money`, { waitUntil: "networkidle" });
  await ap.click('[data-testid="fin-view-settled"]');
  await ap.waitForSelector(`[data-testid="fin-row-${n}"]`, { timeout: 10000 });
  rec("Courier money page: order listed under Settled", true);
  await ap.screenshot({ path: path.join(SHOTS, "admin-courier-money-1280.png"), fullPage: true });
  await actx.close();

  // mobile admin
  const { ctx: mctx, page: mp } = await adminPage(browser, process.env.ADMIN_EMAIL, process.env.ADMIN_PASSWORD, 390);
  await mp.goto(`${BASE}/admin/orders/${n}`, { waitUntil: "networkidle" });
  await mp.waitForSelector('[data-testid="steadfast-finance"]');
  rec("390px admin order page with financials: no horizontal overflow", (await overflow(mp)) <= 1, `${await overflow(mp)}px`);
  await mp.screenshot({ path: path.join(SHOTS, "admin-finance-390.png"), fullPage: true });
  await mp.goto(`${BASE}/admin/products/${P.id}`, { waitUntil: "networkidle" });
  rec("390px description editor: no horizontal overflow", (await overflow(mp)) <= 1);
  await mctx.close();

  // order manager: handles the order, never sees courier money
  if (USERS.order_manager) {
    const { ctx, page } = await adminPage(browser, USERS.order_manager.email, USERS.order_manager.password);
    await page.goto(`${BASE}/admin/orders/${n}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="steadfast-panel"]');
    const om = await api("GET", `/admin/orders/${n}/courier/finance`, { token: (await api("POST", "/admin/login", { body: USERS.order_manager })).json.token });
    rec("order manager: Steadfast panel visible, financials hidden (UI) and refused (API 403)", !(await page.$('[data-testid="steadfast-finance"]')) && om.status === 403);
    await ctx.close();
  }
  const t = (await api("POST", "/track", { body: { order_number: n, phone: "01755000970" } })).json;
  rec("customer tracking shows no fees, payouts or settlement data", !/fee|payout|settle|949|courier_finance/i.test(JSON.stringify(t)));

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("FAIL  harness error —", e.message.split("\n")[0]); process.exit(1); });
