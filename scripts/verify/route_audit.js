// Every route of the app, at 320 / 390 / 430 / 768 / 1280 / 1440 px, against an ISOLATED test backend.
//
//   BASE_URL=http://localhost:3000 EMAIL_CAPTURE_FILE=... ADMIN_EMAIL=... ADMIN_PASSWORD=... \
//   [CHROMIUM_PATH=...] node scripts/verify/route_audit.js <outDir>
//
// Per route and width: renders meaningful content, no horizontal overflow, no uncaught page errors or
// console errors, a page title, broken-image count, correct robots meta (private pages noindex,
// public pages indexable), and one <h1>. Screenshots for every route at 390 and 1280 (and 320 for
// the purchase path) go to <outDir>/shots for visual review. Creates one test customer and one test
// order; nothing else is written.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = `${BASE}/api`;
const OUT = process.argv[2] || "route-audit-out";
const SHOTS = path.join(OUT, "shots");
fs.mkdirSync(SHOTS, { recursive: true });
const CAPTURE = process.env.EMAIL_CAPTURE_FILE;
const WIDTHS = [320, 390, 430, 768, 1280, 1440];
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok, d }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };
const lastLink = (kind, to) => {
  const lines = fs.readFileSync(CAPTURE, "utf8").trim().split("\n").map((l) => JSON.parse(l)).reverse();
  for (const m of lines) { if (to && m.to !== to) continue; const f = m.text.match(new RegExp(`(https?://[^\\s]+${kind}#token=[A-Za-z0-9_-]+)`)); if (f) return f[1]; }
  return null;
};

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const products = await (await fetch(`${API}/products`)).json();
  const cats = await (await fetch(`${API}/categories`)).json();
  const LAUNCH = new Set(["earrings", "necklaces", "rings", "bracelets"]); // = backend LAUNCH_CATEGORY_SLUGS: only these are indexable
  const P = products.find((p) => p.status === "active" && p.stock_quantity > 2 && LAUNCH.has(p.category_slug));
  const soldOut = products.find((p) => p.status === "out_of_stock" && LAUNCH.has(p.category_slug));
  const offLaunch = products.find((p) => p.status === "active" && !LAUNCH.has(p.category_slug));
  // test order (for confirmation + account detail routes)
  const order = await (await fetch(`${API}/checkout`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    customer_name: "Audit Test", customer_phone: "01766000001", customer_email: "", district: "Dhaka", payment_method: "cod",
    delivery_address: "House 1, Road 1, Banani (audit)", items: [{ product_id: P.id, quantity: 1 }] }) })).json();

  // test customer (fresh) for account routes
  const email = `audit.${Date.now().toString(36)}@example.test`, password = "audit " + crypto.randomBytes(9).toString("base64url") + " phrase";
  const cust = await browser.newContext();
  const cp = await cust.newPage();
  await cp.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await cp.evaluate(async (b) => fetch("/api/customer/register", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-AAYNA-CSRF": "1" }, body: JSON.stringify(b) }),
    { full_name: "Audit Customer", email, phone: "01766000002", password, confirm_password: password, accept_terms: true });
  await cp.goto(lastLink("/verify-email", email), { waitUntil: "networkidle" });
  await cp.waitForSelector('[data-testid="verify-success"]', { timeout: 15000 });
  await cp.evaluate(async (b) => fetch("/api/account/addresses", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-AAYNA-CSRF": "1" }, body: JSON.stringify(b) }),
    { recipient_name: "Audit Customer", phone: "01766000002", district: "Sylhet", address: "Flat 2B, Zindabazar, Sylhet (audit)", is_default: true });
  // a signed-in order so /account/orders/:n has content
  const mine = await cp.evaluate(async (b) => (await fetch("/api/checkout", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })).json(),
    { customer_name: "Audit Customer", customer_phone: "01766000002", customer_email: email, district: "Sylhet", payment_method: "cod",
      delivery_address: "Flat 2B, Zindabazar, Sylhet (audit)", items: [{ product_id: P.id, quantity: 1 }] });
  const custState = await cust.storageState();
  await cust.close();

  // admin storage state
  const actx = await browser.newContext();
  const ap = await actx.newPage();
  await ap.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
  await ap.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
  await ap.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
  await ap.click('[data-testid="admin-login-submit"]');
  await ap.waitForURL(/\/admin\/?$/, { timeout: 20000 });
  const adminState = await actx.storageState();
  const accountsList = await ap.evaluate(async () => (await fetch("/api/admin/customer-accounts", { headers: { Authorization: `Bearer ${localStorage.getItem("aayna_admin_token")}` } })).json()).catch(() => []);
  const customers = await ap.evaluate(async () => (await fetch("/api/admin/customers", { headers: { Authorization: `Bearer ${localStorage.getItem("aayna_admin_token")}` } })).json()).catch(() => []);
  await actx.close();
  const acctId = Array.isArray(accountsList) ? accountsList[0]?.id : null;
  const custId = Array.isArray(customers) ? customers[0]?.id : null;

  const PUBLIC = ["/", "/shop", `/category/${cats[0].slug}`, `/product/${P.slug}`, "/contact", "/delivery-policy", "/returns", "/privacy", "/terms"];
  if (P && !LAUNCH.has(P.category_slug)) throw new Error("pick a launch-category product");
  const PRIVATE_GUEST = [...(offLaunch ? [`/product/${offLaunch.slug}`] : []), "/cart", "/checkout", `/order-confirmation/${order.order_number}?token=${order.order_confirmation_token}`, "/track-order",
    "/login", "/register", "/forgot-password", "/verify-email", "/reset-password", "/confirm-email", "/account/orders/claim", "/no-such-page"];
  const ACCOUNT = ["/account", "/account/orders", `/account/orders/${mine.order_number}`, "/account/addresses", "/account/profile", "/account/security", "/account/rewards"];
  const ADMIN = ["/admin/login", "/admin", "/admin/orders", `/admin/orders/${order.order_number}`, "/admin/products", "/admin/products/new", `/admin/products/${P.id}`,
    "/admin/categories", "/admin/inventory", "/admin/customers", ...(custId ? [`/admin/customers/${custId}`] : []), "/admin/accounts",
    ...(acctId ? [`/admin/accounts/${acctId}`] : []), "/admin/promotions", "/admin/settings"];
  const SHOT_320 = new Set(["/", `/product/${P.slug}`, "/cart", "/checkout", "/account", "/admin/orders"]);
  if (soldOut) PUBLIC.push(`/product/${soldOut.slug}`);

  const groups = [["public", PUBLIC, null], ["guest", PRIVATE_GUEST, null], ["account", ACCOUNT, custState], ["admin", ADMIN, adminState]];
  const summary = [];
  for (const width of WIDTHS) {
    for (const [group, routes, state] of groups) {
      if (group === "admin" && width === 320) continue; // admin is supported from 390
      const ctx = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, ...(state ? { storageState: state } : {}) });
      const page = await ctx.newPage();
      await page.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
      // cart content for /cart and /checkout
      if (group === "guest" || group === "account") {
        await page.goto(`${BASE}/product/${P.slug}`, { waitUntil: "networkidle" });
        await page.click(width < 768 ? '[data-testid="add-to-cart-button-mobile"]' : '[data-testid="add-to-cart-button"]');
      }
      for (const r of routes) {
        const errs = [];
        const onErr = (e) => errs.push(String(e).slice(0, 140));
        const onCon = (m) => { if (m.type() === "error" && !/ERR_TUNNEL|favicon|Failed to load resource.*(googletagmanager|facebook|fonts)/.test(m.text())) errs.push(m.text().slice(0, 140)); };
        page.on("pageerror", onErr); page.on("console", onCon);
        const resp = await page.goto(BASE + r, { waitUntil: "networkidle" }).catch((e) => null);
        await page.waitForTimeout(350);
        const info = await page.evaluate(() => ({
          ov: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          text: (document.querySelector("main") || document.body).innerText.trim().length,
          title: document.title,
          robots: document.querySelector('meta[name="robots"]')?.content || "",
          h1: document.querySelectorAll("h1").length,
          broken: [...document.images].filter((i) => i.complete && i.naturalWidth === 0 && !/^data:/.test(i.src) && i.offsetParent !== null).map((i) => i.src.slice(-60)),
          path: location.pathname,
        }));
        page.off("pageerror", onErr); page.off("console", onCon);
        const problems = [];
        if (!resp) problems.push("no response");
        if (info.ov > 1) problems.push(`overflow ${info.ov}px`);
        if (info.text < 40) problems.push(`thin content (${info.text})`);
        if (!/AAYNA/.test(info.title)) problems.push(`title "${info.title}"`);
        if (info.broken.length) problems.push(`broken img ${info.broken.join(",")}`);
        if (errs.length) problems.push(`errors: ${errs.join(" | ")}`);
        const isPublic = group === "public";
        if (isPublic && /noindex/.test(info.robots)) problems.push("public page is noindex");
        if (!isPublic && !/noindex/.test(info.robots)) problems.push(`private page indexable (${info.robots || "no meta"})`);
        if (info.h1 !== 1 && !r.startsWith("/admin")) problems.push(`${info.h1} h1`);
        summary.push({ width, route: r.split("?")[0], group, ...info, problems });
        if (problems.length) rec(`${width}px ${r.split("?")[0]}`, false, problems.join("; "));
        if (width === 390 || width === 1280 || (width === 320 && SHOT_320.has(r))) {
          await page.screenshot({ path: path.join(SHOTS, `${group}${r.split("?")[0].replace(/\//g, "_")}-${width}.png`), fullPage: width !== 1440 });
        }
      }
      await ctx.close();
    }
  }
  const total = summary.length, bad = summary.filter((s) => s.problems.length).length;
  rec(`route audit: ${total - bad}/${total} route-width combinations clean`, bad === 0);
  fs.writeFileSync(path.join(OUT, "summary.json"), JSON.stringify(summary, null, 1));
  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("FAIL  harness error —", e.message.split("\n")[0]); process.exit(1); });
