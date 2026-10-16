// Phase 4 admin UI checks (real browser): error timing and wording, expired
// session, unreachable API, broken product thumbnails.
// Usage: BASE_URL=http://localhost:3000 API=http://localhost:8001/api ADMIN_EMAIL=... ADMIN_PASSWORD=... \
//        [CHROMIUM_PATH=...] node scripts/verify/admin_ui_checks.js <out-dir>
// TEST backend only. On a backend where /admin/dashboard returns 200 (real MongoDB)
// the 5xx case is simulated by intercepting that one request.
const { chromium } = require("playwright");
const fs = require("fs");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = process.env.API || "http://localhost:8001/api";
const OUT = process.argv[2]; fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };

(async () => {
  const { token } = await fetch(`${API}/admin/login`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD }) }).then((r) => r.json());
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const ctxFor = async (tok, vp = { width: 1280, height: 900 }) => {
    const ctx = await browser.newContext({ viewport: vp });
    await ctx.addInitScript((t) => { try { t ? localStorage.setItem("aayna_admin_token", t) : localStorage.removeItem("aayna_admin_token"); } catch {} }, tok);
    return ctx;
  };
  const text = async (page) => (await page.locator('[data-testid="admin-load-error"]').innerText()).replace(/\s+/g, " ");

  // 1. Server error (5xx): shown quickly, says it is a server error, has Try again
  {
    const ctx = await ctxFor(token);
    const real = await fetch(`${API}/admin/dashboard`, { headers: { Authorization: `Bearer ${token}` } });
    if (real.status < 500) await ctx.route("**/api/admin/dashboard", (r) => r.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Something went wrong on the server. Please try again." }) }));
    const page = await ctx.newPage(); const t0 = Date.now();
    await page.goto(BASE + "/admin");
    await page.waitForSelector('[data-testid="admin-load-error"]', { timeout: 20000 }).catch(() => {});
    const ms = Date.now() - t0; const t = await text(page).catch(() => "");
    rec("5xx: dashboard error shown within 4 s (was ~7.8 s)", t && ms < 4000, `${ms} ms`);
    rec("5xx: message says server error with status, not 'could not be reached'", /server hit an error/i.test(t) && /HTTP 500/.test(t) && !/could not be reached/i.test(t), t.slice(0, 120));
    rec("5xx: Try again offered", await page.locator('[data-testid="admin-load-error"] button', { hasText: "Try again" }).count() === 1);
    await page.screenshot({ path: `${OUT}/admin_error_500.png` });
    await ctx.close();
  }
  // 2. Session expired mid-use: a 401 on a data request
  {
    const ctx = await ctxFor(token);
    await ctx.route("**/api/admin/orders**", (r) => r.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Session expired. Please log in again." }) }));
    const page = await ctx.newPage(); const t0 = Date.now();
    await page.goto(BASE + "/admin/orders");
    await page.waitForSelector('[data-testid="admin-load-error"]', { timeout: 15000 }).catch(() => {});
    const ms = Date.now() - t0; const t = await text(page).catch(() => "");
    rec("401: 'session expired' shown without retry delay", /session has expired/i.test(t) && ms < 3000, `${ms} ms — ${t.slice(0, 80)}`);
    const link = page.locator('[data-testid="admin-load-error"] a[href="/admin/login"]');
    rec("401: offers 'Sign in again' (no pointless Try again)", (await link.count()) === 1 && (await page.locator('[data-testid="admin-load-error"] button').count()) === 0);
    await page.screenshot({ path: `${OUT}/admin_error_401.png` });
    await ctx.close();
  }
  // 3. Expired token at load: auth guard sends the admin to login
  {
    const ctx = await ctxFor("expired.or.invalid.token");
    const page = await ctx.newPage();
    await page.goto(BASE + "/admin/products", { waitUntil: "networkidle" });
    rec("invalid token on load -> redirected to /admin/login", page.url().endsWith("/admin/login"), page.url());
    await ctx.close();
  }
  // 4. API unreachable
  {
    const ctx = await ctxFor(token);
    await ctx.route("**/api/admin/products**", (r) => r.abort("connectionrefused"));
    const page = await ctx.newPage(); const t0 = Date.now();
    await page.goto(BASE + "/admin/products");
    await page.waitForSelector('[data-testid="admin-load-error"]', { timeout: 15000 }).catch(() => {});
    const ms = Date.now() - t0; const t = await text(page).catch(() => "");
    rec("unreachable: says the server could not be reached, within 4 s", /could not be reached/i.test(t) && ms < 4000, `${ms} ms`);
    await ctx.close();
  }
  // 5. Thumbnails: failing product photos never show the browser's broken-image icon
  {
    const ctx = await ctxFor(token);
    await ctx.route(/\.(png|jpe?g|webp)(\?.*)?$/i, (r) => r.abort("failed"));
    const page = await ctx.newPage();
    await page.goto(BASE + "/admin/products", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const info = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('[data-testid^="product-row-"]')];
      const broken = [...document.querySelectorAll("main img")].filter((i) => i.complete && i.naturalWidth === 0 && i.getBoundingClientRect().width > 0).length;
      const fallbacks = rows.filter((r) => r.querySelector('[aria-label="Image could not be loaded"], [aria-label="No image"]')).length;
      return { rows: rows.length, broken, fallbacks };
    });
    rec("thumbnails: no visible broken <img> in product list", info.rows > 0 && info.broken === 0, JSON.stringify(info));
    rec("thumbnails: every row shows an image or the fallback icon", info.fallbacks === info.rows, JSON.stringify(info));
    await page.screenshot({ path: `${OUT}/admin_products_thumbs.png` });
    const firstEdit = page.locator('[data-testid^="edit-product-"]').first();
    if (await firstEdit.count()) {
      await firstEdit.click(); await page.waitForTimeout(1200);
      const broken = await page.evaluate(() => [...document.querySelectorAll("main img")].filter((i) => i.complete && i.naturalWidth === 0 && i.getBoundingClientRect().width > 0).length);
      rec("thumbnails: product editor image tiles show no broken <img>", broken === 0, `broken=${broken}`);
    }
    await ctx.close();
  }
  // 6. Storefront: a 404 product is not retried (shows quickly)
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await ctx.newPage(); const t0 = Date.now();
    await page.goto(BASE + "/product/no-such-piece");
    await page.waitForSelector("text=/not found/i", { timeout: 15000 }).catch(() => {});
    rec("storefront: unknown product shows not-found within 2 s", Date.now() - t0 < 2000, `${Date.now() - t0} ms`);
    await ctx.close();
  }
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})();
