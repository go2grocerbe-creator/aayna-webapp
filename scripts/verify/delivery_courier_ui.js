// Delivery policy (৳100 below ৳1,500, free from ৳1,500) + Steadfast courier panel, in a real browser,
// against an ISOLATED backend whose catalogue is the public snapshot of the 10 genuine products at
// their +৳100 prices, with STEADFAST_MODE=mock (simulator; nothing is sent to Steadfast).
//
//   BASE_URL=http://localhost:3000 EMAIL_CAPTURE_FILE=... ADMIN_EMAIL=... ADMIN_PASSWORD=... \
//   [CHROMIUM_PATH=...] node scripts/verify/delivery_courier_ui.js <outDir>
//
// Also works against the protected preview: BASE_URL=<preview url> plus BYPASS_QUERY=_vercel_share=...
// (customer registration needs EMAIL_CAPTURE_FILE, so the welcome-offer part runs locally only).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const API = `${BASE}/api`;
const OUT = process.argv[2] || "delivery-courier-out";
const SHOTS = path.join(OUT, "shots");
fs.mkdirSync(SHOTS, { recursive: true });
const CAPTURE = process.env.EMAIL_CAPTURE_FILE;
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };
const taka = (n) => "৳" + Number(n).toLocaleString("en-US");
const RUN = Date.now().toString(36);
const PW = () => "test " + crypto.randomBytes(9).toString("base64url") + " phrase";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
const text = async (page, sel) => ((await page.textContent(sel).catch(() => "")) || "").replace(/\s+/g, " ").trim();

async function api(method, p, { token, body } = {}) {
  const r = await fetch(API + p, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}
const mails = (to) => (CAPTURE && fs.existsSync(CAPTURE) ? fs.readFileSync(CAPTURE, "utf8") : "").trim().split("\n").filter(Boolean)
  .map((l) => JSON.parse(l)).filter((m) => !to || m.to === to);
const lastLink = (kind, to) => { for (const m of mails(to).reverse()) { const f = m.text.match(new RegExp(`(https?://[^\\s]+${kind}#token=[A-Za-z0-9_-]+)`)); if (f) return f[1]; } return null; };
const inPage = (page, method, p, body) => page.evaluate(async ({ method, p, body }) => {
  const r = await fetch("/api" + p, { method, credentials: "include", headers: { "Content-Type": "application/json", "X-AAYNA-CSRF": "1" }, body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}, { method, p, body });

async function newPage(browser, width) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, deviceScaleFactor: width < 768 ? 2 : 1 });
  const page = await ctx.newPage();
  await page.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
  return { ctx, page };
}
async function addToCart(page, slug, width) {
  await page.goto(`${BASE}/product/${slug}`, { waitUntil: "networkidle" });
  await page.click(width < 768 ? '[data-testid="add-to-cart-button-mobile"]' : '[data-testid="add-to-cart-button"]');
  await sleep(300);
}
async function fillCheckout(page, phone, email = "") {
  if (!(await page.inputValue('[data-testid="checkout-name"]'))) await page.fill('[data-testid="checkout-name"]', "Delivery Test");
  await page.fill('[data-testid="checkout-phone"]', phone);
  if (email) await page.fill('[data-testid="checkout-email"]', email);
  await page.click('[data-testid="checkout-district"]');
  await page.click('[role="option"]:has-text("Sylhet")');
  await page.fill('[data-testid="checkout-address"]', "Flat 2B, Zindabazar Road, Sylhet (test)");
}
async function placeOrder(page) {
  await page.click('[data-testid="place-order-button"]');
  await page.waitForSelector('[data-testid="confirmation-order-number"]', { timeout: 20000 });
  return (await text(page, '[data-testid="confirmation-order-number"]'));
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const products = await (await fetch(`${API}/products?limit=100`)).json();
  const bySku = Object.fromEntries(products.map((p) => [p.sku, p]));
  const CHK = bySku["AYN-EAR-CHK-GLD"], STN = bySku["AYN-CUF-STN-GLD"], FLR = bySku["AYN-EAR-FLR-GLD"], FLS = bySku["AYN-EAR-FLR-SLV"];
  const targets = { "AYN-NKL-LUN-GLD": 1450, "AYN-NKL-AUR-GLD": 1450, "AYN-CUF-CRS-GLD": 1150, "AYN-CUF-STN-GLD": 1090, "AYN-EAR-CHK-GLD": 970,
    "AYN-EAR-FLR-GLD": 1510, "AYN-EAR-FLR-SLV": 1510, "AYN-BRC-FLR-GLD": 1410, "AYN-BRC-FLR-SLV": 1410, "AYN-RNG-CLS-GLD": 1390 };
  const priceOk = Object.entries(targets).every(([s, v]) => bySku[s] && bySku[s].selling_price === v);
  rec("catalogue: 10 genuine products at the approved +৳100 prices", products.length === 10 && priceOk,
      Object.entries(targets).filter(([s, v]) => !bySku[s] || bySku[s].selling_price !== v).map(([s]) => s).join(",") || "all match");
  const settings = await (await fetch(`${API}/settings`)).json();
  rec("public settings expose the delivery policy ৳100 / free from ৳1,500", JSON.stringify(settings.delivery_policy) === JSON.stringify({ charge: 100, free_threshold: 1500 }));

  // ---- 1. Cart + checkout + confirmation at phone and desktop widths --------------------------
  const orders = {};
  for (const width of [390, 1280]) {
    const cases = [
      { key: "970", items: [CHK], sub: 970, del: 100, hint: 530 },
      { key: "1090", items: [STN], sub: 1090, del: 100, hint: 410 },
      { key: "1510", items: [FLR], sub: 1510, del: 0 },
      { key: "two", items: [CHK, STN], sub: 2060, del: 0 },
    ];
    for (const c of cases) {
      const { ctx, page } = await newPage(browser, width);
      for (const p of c.items) await addToCart(page, p.slug, width);
      await page.goto(`${BASE}/cart`, { waitUntil: "networkidle" });
      await sleep(500);
      const cart = { sub: await text(page, '[data-testid="cart-subtotal"]'), del: await text(page, '[data-testid="cart-delivery"]'),
                     total: await text(page, '[data-testid="cart-total"]'), prog: await text(page, '[data-testid="free-delivery-progress"]') };
      const delOk = c.del ? cart.del === taka(c.del) : cart.del === "Free";
      const progOk = c.del ? cart.prog.includes(`Add ${taka(c.hint)} more for free delivery`) : /Free delivery unlocked/.test(cart.prog);
      rec(`${width}px cart ${taka(c.sub)}: delivery ${c.del ? taka(c.del) : "Free"}, total ${taka(c.sub + c.del)}, progress message`,
          cart.sub === taka(c.sub) && delOk && cart.total === taka(c.sub + c.del) && progOk && (await overflow(page)) <= 1, JSON.stringify(cart));
      if (c.key === "970" || c.key === "1510") await page.screenshot({ path: path.join(SHOTS, `cart-${c.key}-${width}.png`), fullPage: true });
      await page.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
      await sleep(400);
      const co = { del: await text(page, '[data-testid="checkout-delivery"]'), total: await text(page, '[data-testid="checkout-total"]') };
      rec(`${width}px checkout ${taka(c.sub)}: delivery ${c.del ? taka(c.del) : "Free"} before choosing a district, total ${taka(c.sub + c.del)}`,
          (c.del ? co.del === taka(c.del) : co.del === "Free") && co.total === taka(c.sub + c.del), JSON.stringify(co));
      if (c.key !== "two" || width === 1280) {
        await fillCheckout(page, width === 390 ? "01722000390" : "01722001280");
        await page.screenshot({ path: path.join(SHOTS, `checkout-${c.key}-${width}.png`), fullPage: true });
        const num = await placeOrder(page);
        const conf = await text(page, '[data-testid="confirmation-delivery"]');
        rec(`${width}px confirmation ${num}: delivery ${c.del ? taka(c.del) : "Free"} (server-calculated)`, c.del ? conf === taka(c.del) : conf === "Free", conf);
        if (c.key === "1510") await page.screenshot({ path: path.join(SHOTS, `confirmation-free-${width}.png`), fullPage: true });
        orders[`${c.key}-${width}`] = { num, phone: width === 390 ? "01722000390" : "01722001280", total: c.sub + c.del };
      }
      await ctx.close();
    }
  }
  const dp = await (await fetch(`${BASE}/delivery-policy`)).text();
  const { ctx: pctx, page: pp } = await newPage(browser, 390);
  await pp.goto(`${BASE}/delivery-policy`, { waitUntil: "networkidle" });
  const pol = await text(pp, "main");
  rec("delivery policy page states ৳100 below ৳1,500 and free from ৳1,500, nationwide, before discounts",
      /Orders below ৳1,500: ৳100 delivery/.test(pol) && /Orders of ৳1,500 or more: free delivery/.test(pol) && /before any discount/.test(pol) && !/Inside Dhaka/.test(pol) && !!dp);
  await pp.screenshot({ path: path.join(SHOTS, "delivery-policy-390.png"), fullPage: true });
  await pctx.close();

  // ---- 2. Welcome offer math (isolated local backend only: needs captured emails) -------------
  const admin = (await api("POST", "/admin/login", { body: { email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD } })).json?.token;
  if (CAPTURE && admin) {
    const en = await api("PUT", "/admin/promotions/campaigns/welcome", { token: admin, body: { enabled: true, min_subtotal: 1000, max_discount_bdt: 150, confirm: true } });
    rec("welcome offer enabled in the ISOLATED test database only (approved limits)", en.status === 200);
    for (const [p, disc, del, total, phone] of [[STN, 109, 100, 1081, "01733000001"], [FLS, 150, 0, 1360, "01733000002"]]) {
      const email = `deliv.${RUN}.${phone.slice(-1)}@example.test`, password = PW();
      const { ctx, page } = await newPage(browser, 390);
      await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
      await inPage(page, "POST", "/customer/register", { full_name: "Welcome Test", email, phone, password, confirm_password: password, accept_terms: true });
      await page.goto(lastLink("/verify-email", email), { waitUntil: "networkidle" });
      await page.waitForSelector('[data-testid="verify-success"]', { timeout: 15000 });
      const code = (await inPage(page, "GET", "/account/rewards")).json.coupons[0].code;
      await addToCart(page, p.slug, 390);
      await page.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
      await fillCheckout(page, phone);
      await page.fill('[data-testid="checkout-coupon-input"]', code);
      await page.click('[data-testid="checkout-coupon-apply"]');
      await page.waitForSelector('[data-testid="checkout-discount"]');
      await sleep(300);
      const v = { disc: await text(page, '[data-testid="checkout-discount"]'), del: await text(page, '[data-testid="checkout-delivery"]'), total: await text(page, '[data-testid="checkout-total"]') };
      rec(`390px welcome 10% on ${taka(p.selling_price)}: −${taka(disc)}, delivery ${del ? taka(del) : "Free"}, total ${taka(total)}`,
          v.disc.includes(taka(disc)) && (del ? v.del === taka(del) : v.del === "Free") && v.total === taka(total), JSON.stringify(v));
      await page.screenshot({ path: path.join(SHOTS, `checkout-welcome-${p.selling_price}-390.png`), fullPage: true });
      const num = await placeOrder(page);
      const cTotal = await text(page, "main");
      rec(`welcome order ${num} confirmed with total ${taka(total)}`, cTotal.includes(taka(total)));
      orders[`welcome-${total}`] = { num, phone, total };
      await ctx.close();
    }
    await api("PUT", "/admin/promotions/campaigns/welcome", { token: admin, body: { enabled: false } });
    rec("welcome offer switched back off in the test database", (await (await fetch(`${API}/promotions/welcome`)).json()).enabled === false);
  }

  // ---- 3. Steadfast panel (simulator) ----------------------------------------------------------
  for (const width of [1280, 390]) {
    const { ctx, page } = await newPage(browser, width);
    await page.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
    await page.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
    await page.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
    await page.click('[data-testid="admin-login-submit"]');
    await page.waitForURL(/\/admin\/?$/, { timeout: 20000 });
    const o = width === 1280 ? (orders["welcome-1081"] || orders["1090-1280"]) : orders["970-390"];
    await page.goto(`${BASE}/admin/orders/${o.num}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="steadfast-panel"]');
    rec(`${width}px admin: Steadfast panel in simulator mode; booking blocked until Packed`,
        /simulator/i.test(await text(page, '[data-testid="steadfast-mode"]')) && /Packed/.test(await text(page, '[data-testid="steadfast-problems"]'))
        && (await page.isDisabled('[data-testid="steadfast-book"]')));
    rec(`${width}px admin: COD to collect = order total ${taka(o.total)}`, (await text(page, '[data-testid="steadfast-cod"]')) === taka(o.total));
    await page.selectOption('[data-testid="order-status-select"]', "Packed");
    await page.click('[data-testid="order-save"]');
    await page.waitForFunction(() => !document.querySelector('[data-testid="steadfast-book"]')?.disabled, null, { timeout: 10000 });
    await page.click('[data-testid="steadfast-book"]');
    await page.waitForSelector('[data-testid="steadfast-confirm"]');
    rec(`${width}px admin: explicit confirmation shows the COD amount`, (await text(page, '[data-testid="steadfast-confirm"]')).includes(taka(o.total)));
    await page.screenshot({ path: path.join(SHOTS, `admin-steadfast-confirm-${width}.png`), fullPage: true });
    await page.click('[data-testid="steadfast-confirm-book"]');
    await page.waitForSelector('[data-testid="steadfast-cid"]', { timeout: 15000 });
    const tracking = await text(page, '[data-testid="steadfast-tracking"]');
    rec(`${width}px admin: booked - consignment, tracking, COD ${taka(o.total)}; order still Packed`,
        !!(await text(page, '[data-testid="steadfast-cid"]')) && /^SFM/.test(tracking) && (await text(page, '[data-testid="steadfast-booked-cod"]')) === taka(o.total)
        && (await text(page, "h1 + p, .text-xs.font-semibold.px-3")).length >= 0 && (await page.$$eval("span", (els) => els.some((e) => e.textContent.trim() === "Packed"))));
    rec(`${width}px admin: no horizontal overflow on the order page`, (await overflow(page)) <= 1, `${await overflow(page)}px`);
    await page.screenshot({ path: path.join(SHOTS, `admin-steadfast-booked-${width}.png`), fullPage: true });
    // customer view
    const t = await api("POST", "/track", { body: { order_number: o.num, phone: o.phone } });
    rec(`${width}px customer tracking shows "Booked with Steadfast courier" and the tracking code, nothing internal`,
        t.json?.[0]?.courier_status === "Booked with Steadfast courier" && t.json[0].courier_tracking_code === tracking && !/consignment|cod_amount|claim/.test(JSON.stringify(t.json)));
    // hand-over, then simulated confirmed delivery
    await page.selectOption('[data-testid="order-status-select"]', "Sent to Courier");
    await page.click('[data-testid="order-save"]');
    await sleep(800);
    await page.click('[data-testid="steadfast-simulator"] summary');
    await page.selectOption('[data-testid="sim-status"]', "delivered_approval_pending");
    await page.click('[data-testid="sim-set-status"]');
    await sleep(500);
    await page.click('[data-testid="steadfast-sync"]');
    await page.waitForFunction(() => /awaiting Steadfast confirmation/.test(document.querySelector('[data-testid="steadfast-status"]')?.textContent || ""), null, { timeout: 10000 });
    rec(`${width}px rider-reported delivery is NOT treated as delivered`, (await page.$$eval("span", (els) => els.some((e) => e.textContent.trim() === "Sent to Courier"))));
    await page.selectOption('[data-testid="sim-status"]', "delivered");
    await page.click('[data-testid="sim-set-status"]');
    await sleep(500);
    await page.click('[data-testid="steadfast-sync"]');
    await page.waitForFunction(() => /Delivered \(confirmed/.test(document.querySelector('[data-testid="steadfast-status"]')?.textContent || ""), null, { timeout: 10000 });
    await sleep(800);
    const ordStatus = (await api("POST", "/track", { body: { order_number: o.num, phone: o.phone } })).json?.[0];
    rec(`${width}px confirmed delivery moves the order to Delivered; customer timeline updated`,
        ordStatus?.order_status === "Delivered" && ordStatus.timeline.steps.find((s) => s.status === "Delivered").done && ordStatus.courier_status === "Delivered by Steadfast courier");
    await page.screenshot({ path: path.join(SHOTS, `admin-steadfast-delivered-${width}.png`), fullPage: true });
    await ctx.close();
  }

  // timeout after acceptance -> reconcile -> link (desktop)
  {
    const { ctx, page } = await newPage(browser, 1280);
    await page.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
    await page.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
    await page.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
    await page.click('[data-testid="admin-login-submit"]');
    await page.waitForURL(/\/admin\/?$/, { timeout: 20000 });
    const o = orders["1510-1280"];
    await page.goto(`${BASE}/admin/orders/${o.num}`, { waitUntil: "networkidle" });
    await page.selectOption('[data-testid="order-status-select"]', "Packed");
    await page.click('[data-testid="order-save"]');
    await page.waitForFunction(() => !document.querySelector('[data-testid="steadfast-book"]')?.disabled, null, { timeout: 10000 });
    rec("free-delivery order: COD = merchandise only (৳1,510, no delivery)", (await text(page, '[data-testid="steadfast-cod"]')) === taka(1510));
    await page.click('[data-testid="steadfast-simulator"] summary');
    await page.selectOption('[data-testid="sim-fault"]', "timeout_after_accept");
    await page.click('[data-testid="sim-fail-next"]');
    await sleep(500);
    await page.click('[data-testid="steadfast-book"]');
    await page.click('[data-testid="steadfast-confirm-book"]');
    await page.waitForSelector('[data-testid="steadfast-reconcile-note"]', { timeout: 15000 });
    rec("timeout after acceptance: no retry offered, reconciliation required", !(await page.$('[data-testid="steadfast-book"]')) && /reconcile/i.test(await text(page, '[data-testid="steadfast-reconcile-note"]')));
    await page.screenshot({ path: path.join(SHOTS, "admin-steadfast-reconcile-1280.png"), fullPage: true });
    await page.click('[data-testid="steadfast-reconcile"]');
    await page.waitForSelector('[data-testid="steadfast-link-form"]', { timeout: 10000 });
    const sim = await text(page, '[data-testid="steadfast-sim-portal"]');
    const [, cid, code] = sim.match(/consignment (\d+), tracking ([A-Z0-9]+)/) || [];
    rec("reconcile by invoice finds the parcel Steadfast accepted", !!cid && /Do not book again/.test(await text(page, '[data-testid="steadfast-reconcile-note"]')));
    await page.fill('[data-testid="steadfast-link-cid"]', cid);
    await page.fill('[data-testid="steadfast-link-code"]', code);
    await page.click('[data-testid="steadfast-link"]');
    await page.waitForSelector('[data-testid="steadfast-cid"]', { timeout: 10000 });
    rec("existing parcel linked by hand: one consignment, no duplicate booking", (await text(page, '[data-testid="steadfast-cid"]')) === cid);
    // orders list badges + bulk check
    await page.goto(`${BASE}/admin/orders`, { waitUntil: "networkidle" });
    rec("orders list shows Steadfast badges", /Steadfast: (Booked|Delivered)/.test(await text(page, "table")));
    await page.click('[data-testid="steadfast-sync-all"]');
    await sleep(1500);
    rec("orders list: 'Check Steadfast parcels' runs without error", !(await page.$('[data-sonner-toast][data-type="error"]')));
    await page.screenshot({ path: path.join(SHOTS, "admin-orders-badges-1280.png"), fullPage: true });
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("FAIL  harness error —", e.message.split("\n")[0]); process.exit(1); });
