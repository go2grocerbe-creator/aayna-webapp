// Admin roles + core workflows in a real browser (desktop 1280 and mobile 390).
//
//   ROLE_USERS_JSON=users.json BASE_URL=http://localhost:3000 API=http://localhost:8001/api \
//   [WRITE_SKU=SKU-to-edit-and-restore] [CHROMIUM_PATH=...] node scripts/verify/admin_roles_ui.js <outDir>
//
// users.json: {"super_admin": {"email": "...", "password": "..."}, "product_manager": {...}, "order_manager": {...}}
// TEST environment accounts only - passwords are never printed.
// Writes are reversible: a selling price is changed and restored, stock is adjusted +1 then -1.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = process.env.API || "http://localhost:8001/api";
const OUT = process.argv[2] || "admin-roles-out";
const USERS = JSON.parse(fs.readFileSync(process.env.ROLE_USERS_JSON, "utf8"));
const EXTRA_HEADERS = process.env.EXTRA_HEADERS ? JSON.parse(process.env.EXTRA_HEADERS) : {};
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (n, ok, d = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };

// Accounts = registered customer sign-ins (customers.view); Promotions = owner/ops only.
const NAV = { super_admin: ["dashboard", "orders", "products", "categories", "inventory", "customers", "accounts", "promotions", "settings"],
  admin: ["dashboard", "orders", "products", "categories", "inventory", "customers", "accounts", "promotions", "settings"],
  product_manager: ["dashboard", "products", "categories", "inventory"],
  order_manager: ["dashboard", "orders", "products", "categories", "inventory", "customers", "accounts"] };
const COST_ROLES = new Set(["super_admin", "admin"]);
const EDIT_ROLES = new Set(["super_admin", "admin", "product_manager"]);

async function apiCall(method, p, token, body) {
  const r = await fetch(API + p, { method, headers: { "Content-Type": "application/json", ...EXTRA_HEADERS, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}

async function login(page, u) {
  await page.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="admin-login-email"]', u.email);
  await page.fill('[data-testid="admin-login-password"]', u.password);
  await page.click('[data-testid="admin-login-submit"]');
  await page.waitForURL(/\/admin\/?$/, { timeout: 20000 });
}

const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });

  // unauthenticated visitor
  {
    const ctx = await browser.newContext({ extraHTTPHeaders: EXTRA_HEADERS });
    const page = await ctx.newPage();
    for (const p of ["/admin", "/admin/products", "/admin/settings"]) {
      await page.goto(BASE + p, { waitUntil: "networkidle" });
      rec(`unauthenticated ${p} -> login page`, page.url().endsWith("/admin/login"), page.url().replace(BASE, ""));
    }
    const robots = await page.$eval('meta[name="robots"]', (m) => m.content).catch(() => "");
    rec("admin login page is noindex", /noindex/.test(robots), robots);
    for (const p of ["/admin/products", "/admin/orders", "/admin/dashboard", "/admin/me"]) {
      rec(`API ${p} without token -> 401`, (await apiCall("GET", p)).status === 401);
    }
    await page.fill('[data-testid="admin-login-email"]', "nobody@example.test");
    await page.fill('[data-testid="admin-login-password"]', "wrong-password-123");
    await page.click('[data-testid="admin-login-submit"]');
    await page.waitForSelector('[data-testid="admin-login-error"]', { timeout: 10000 });
    const msg = (await page.textContent('[data-testid="admin-login-error"]')).trim();
    rec("invalid credentials: generic error, stays on login", page.url().endsWith("/admin/login") && /invalid email or password/i.test(msg), msg);
    await ctx.close();
  }

  for (const [role, u] of Object.entries(USERS)) {
    for (const vp of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, extraHTTPHeaders: EXTRA_HEADERS });
      const page = await ctx.newPage();
      const tag = `${role} ${vp.name}`;
      await login(page, u);
      const token = await page.evaluate(() => localStorage.getItem("aayna_admin_token"));
      rec(`${tag}: login works, token not in URL`, Boolean(token) && !page.url().includes(token));

      // dashboard data
      await page.waitForSelector('[data-testid="dash-catalogue-total"]', { timeout: 20000 });
      const total = (await page.textContent('[data-testid="dash-catalogue-total"]')).replace(/\D+/g, " ").trim().split(" ")[0];
      rec(`${tag}: dashboard shows catalogue from the database`, Number(total) > 0, `products=${total}`);
      await page.screenshot({ path: path.join(OUT, `${role}-${vp.name}-dashboard.png`), fullPage: true });

      // navigation matches the role
      if (vp.name === "mobile") { await page.click('[data-testid="admin-mobile-menu"]'); await page.waitForTimeout(400); }
      const nav = await page.$$eval('[data-testid^="admin-nav-"]', (els) => [...new Set(els.filter((e) => e.offsetParent !== null).map((e) => e.getAttribute("data-testid").replace("admin-nav-", "")))]);
      rec(`${tag}: navigation = ${NAV[role].join(",")}`, JSON.stringify(nav.sort()) === JSON.stringify([...NAV[role]].sort()), nav.join(","));
      if (vp.name === "mobile") await page.keyboard.press("Escape");

      // products list + detail
      await page.goto(`${BASE}/admin/products`, { waitUntil: "networkidle" });
      await page.waitForSelector('[data-testid^="product-row-"]', { timeout: 20000 });
      const rows = await page.$$('[data-testid^="product-row-"]');
      rec(`${tag}: products listed`, rows.length > 0, `${rows.length} rows`);
      rec(`${tag}: Add Product only for editors`, (await page.$('[data-testid="add-product-btn"]')) !== null === EDIT_ROLES.has(role));
      rec(`${tag}: no horizontal scroll on products`, (await overflow(page)) <= 1);
      const sku = process.env.WRITE_SKU || (await rows[0].getAttribute("data-testid")).replace("product-row-", "");
      await page.click(`[data-testid="edit-product-${sku}"]`);
      await page.waitForSelector('[data-testid="pf-name"]');
      await page.waitForFunction(() => (document.querySelector('[data-testid="pf-name"]')?.value || '').length > 0);
      rec(`${tag}: purchase cost field ${COST_ROLES.has(role) ? "shown" : "hidden"}`, ((await page.$('[data-testid="pf-cost"]')) !== null) === COST_ROLES.has(role));
      rec(`${tag}: SKU read-only on edit`, await page.$eval('[data-testid="pf-sku"]', (e) => e.readOnly));
      rec(`${tag}: Save only for editors`, ((await page.$('[data-testid="pf-save"]')) !== null) === EDIT_ROLES.has(role));
      await page.screenshot({ path: path.join(OUT, `${role}-${vp.name}-product.png`), fullPage: true });

      // reversible write: price change persists after reload, then restored (desktop, editors only)
      if (EDIT_ROLES.has(role) && vp.name === "desktop") {
        const before = await page.inputValue('[data-testid="pf-selling-price"]');
        const changed = String(Number(before) + 10);
        await page.fill('[data-testid="pf-selling-price"]', changed);
        await page.click('[data-testid="pf-save"]');
        await page.waitForURL(/\/admin\/products$/, { timeout: 20000 });
        await page.click(`[data-testid="edit-product-${sku}"]`);
        await page.waitForFunction(() => (document.querySelector('[data-testid="pf-selling-price"]')?.value || '').length > 0);
        await page.reload({ waitUntil: "networkidle" });
        await page.waitForFunction(() => (document.querySelector('[data-testid="pf-selling-price"]')?.value || '').length > 0);
        const after = await page.inputValue('[data-testid="pf-selling-price"]');
        rec(`${tag}: price edit persists after reload`, after === changed, `${before} -> ${after}`);
        await page.fill('[data-testid="pf-selling-price"]', before);
        await page.click('[data-testid="pf-save"]');
        await page.waitForURL(/\/admin\/products$/, { timeout: 20000 });
        const list = (await apiCall("GET", `/admin/products?search=${encodeURIComponent(sku)}`, token)).json || [];
        const p = list.find((x) => x.sku === sku);
        rec(`${tag}: price restored`, p && String(p.selling_price) === String(Number(before)), p && `${p.selling_price}`);

        // stock adjust +1 then -1 with reasons
        await page.goto(`${BASE}/admin/inventory`, { waitUntil: "networkidle" });
        for (const [qty, reason] of [["1", "QA verification +1"], ["-1", "QA verification revert"]]) {
          await page.click(`[data-testid="adjust-stock-${sku}"]`);
          await page.fill('[data-testid="adjust-qty"]', qty);
          await page.fill('[data-testid="adjust-reason"]', reason);
          await page.click('[data-testid="adjust-save"]');
          await page.waitForTimeout(1200);
        }
        const p2 = ((await apiCall("GET", `/admin/products?search=${encodeURIComponent(sku)}`, token)).json || []).find((x) => x.sku === sku);
        const logs = (await apiCall("GET", `/admin/inventory/${p.id}/logs`, token)).json || [];
        rec(`${tag}: stock +1/-1 via Inventory returns to original and is logged`,
          p2.stock_quantity === p.stock_quantity && logs[0]?.reason === "QA verification revert" && logs[1]?.reason === "QA verification +1",
          `stock ${p.stock_quantity} -> ${p2.stock_quantity}, last=${logs[0]?.reason}`);
      }

      // server-side enforcement, not just hidden buttons
      const prod = ((await apiCall("GET", `/admin/products?search=${encodeURIComponent(sku)}`, token)).json || [])[0];
      const put = await apiCall("PUT", `/admin/products/${prod.id}`, token, { product_name: prod.product_name });
      rec(`${tag}: API product update ${EDIT_ROLES.has(role) ? "allowed" : "403"}`, EDIT_ROLES.has(role) ? put.status === 200 : put.status === 403, `HTTP ${put.status}`);
      rec(`${tag}: API product payload ${COST_ROLES.has(role) ? "includes" : "excludes"} purchase cost`, ("cost_price" in prod) === COST_ROLES.has(role));
      const settings = await apiCall("GET", "/admin/settings", token);
      rec(`${tag}: API settings ${COST_ROLES.has(role) ? "allowed" : "403"}`, COST_ROLES.has(role) ? settings.status === 200 : settings.status === 403, `HTTP ${settings.status}`);
      const orders = await apiCall("GET", "/admin/orders", token);
      const ordersAllowed = role !== "product_manager";
      rec(`${tag}: API orders ${ordersAllowed ? "allowed" : "403"}`, ordersAllowed ? orders.status === 200 : orders.status === 403, `HTTP ${orders.status}`);
      if (!NAV[role].includes("settings")) {
        await page.goto(`${BASE}/admin/settings`, { waitUntil: "networkidle" });
        rec(`${tag}: /admin/settings shows "No access"`, (await page.$('[data-testid="admin-no-access"]')) !== null);
      }
      for (const p of NAV[role].filter((n) => n !== "dashboard")) {
        await page.goto(`${BASE}/admin/${p}`, { waitUntil: "networkidle" });
        await page.waitForTimeout(500);
        const ov = await overflow(page);
        const err = await page.$('[data-testid="admin-load-error"]');
        rec(`${tag}: /admin/${p} loads without error or horizontal scroll`, ov <= 1 && !err, `overflow=${ov}`);
        if (vp.name === "mobile") await page.screenshot({ path: path.join(OUT, `${role}-mobile-${p}.png`), fullPage: true });
      }

      // direct refresh on a deep link keeps the session
      await page.goto(`${BASE}/admin/inventory`, { waitUntil: "networkidle" });
      await page.reload({ waitUntil: "networkidle" });
      rec(`${tag}: refresh on deep link stays signed in`, page.url().endsWith("/admin/inventory"));

      // logout invalidates the token server-side
      if (vp.name === "mobile") { await page.click('[data-testid="admin-mobile-menu"]'); await page.waitForTimeout(400); }
      await page.locator('[data-testid="admin-logout"]:visible').first().click();
      await page.waitForURL(/\/admin\/login$/, { timeout: 10000 });
      rec(`${tag}: logout returns to login`, true);
      rec(`${tag}: old token rejected after logout`, (await apiCall("GET", "/admin/me", token)).status === 401);
      await page.goto(`${BASE}/admin/products`, { waitUntil: "networkidle" });
      rec(`${tag}: after logout /admin/products -> login`, page.url().endsWith("/admin/login"));
      await ctx.close();
    }
  }
  await browser.close();
  const passed = results.filter(Boolean).length;
  console.log(`\n${passed}/${results.length} checks passed`);
  process.exit(passed === results.length ? 0 : 1);
})();
