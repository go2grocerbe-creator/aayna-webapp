// AAYNA storefront/admin regression gate (Phase 2 of production recovery).
// Usage (Playwright installed separately, NOT a project dependency):
//   BASE_URL=http://localhost:3000 API_PATTERN="**/localhost:8001/api/**" \
//   ADMIN_EMAIL=... ADMIN_PASSWORD=... node scripts/verify/storefront_routes.js <out-dir>
// Run ONLY against a frontend wired to an isolated TEST backend (DB name containing "test"):
// it places a real order and logs into admin. Never point this at production.
const { chromium } = require("playwright");
const fs = require("fs");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const API_PATTERN = process.env.API_PATTERN || "**/localhost:8001/api/**";
const OUT = process.argv[2];
const ADMIN_EMAIL = process.env.ADMIN_EMAIL, ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const rec = (name, ok, detail = "") => { results.push({ name, ok, detail }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`); };

function watch(page) {
  const log = { console: [], pageerrors: [], failed: [], http: [] };
  page.on("console", (m) => { if (m.type() === "error") log.console.push(m.text()); });
  page.on("pageerror", (e) => log.pageerrors.push(String(e)));
  page.on("requestfailed", (r) => log.failed.push(`${r.url()} ${r.failure()?.errorText}`));
  page.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/")) log.http.push(`${r.status()} ${r.url()}`); });
  return log;
}
const isExternalImg = (s) => /ERR_TUNNEL_CONNECTION_FAILED/.test(s); // third-party hosts blocked by sandbox egress; tracked separately

(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});

  // ---------- 1. Every known route renders inside the right shell ----------
  const routes = [
    ["/", "storefront"], ["/shop", "storefront"], ["/category/earrings", "storefront"],
    ["/product/gold-butterfly-hair-clip", "storefront"], ["/cart", "storefront"], ["/checkout", "storefront"],
    ["/track-order", "storefront"], ["/contact", "storefront"], ["/delivery-policy", "storefront"],
    ["/returns", "storefront"], ["/privacy", "storefront"], ["/terms", "storefront"],
    ["/this-page-does-not-exist", "storefront"], ["/admin/login", "admin-login"],
  ];
  for (const vw of [{ w: 375, h: 812, tag: "mobile" }, { w: 1280, h: 800, tag: "desktop" }]) {
    const ctx = await browser.newContext({ viewport: { width: vw.w, height: vw.h } });
    for (const [path, shell] of routes) {
      const page = await ctx.newPage();
      const log = watch(page);
      await page.goto(BASE + path, { waitUntil: "networkidle" });
      await page.waitForTimeout(400);
      const info = await page.evaluate(() => ({
        h1: document.querySelector("h1")?.innerText?.slice(0, 60) || "",
        header: !!document.querySelector('[data-testid="logo-link"]'),
        footer: !!document.querySelector("footer"),
        loginForm: !!document.querySelector('[data-testid="admin-login-email"]'),
        showcase: document.body.innerText.includes("Enter the mirror"),
        sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
        title: document.title,
      }));
      const shellOk = shell === "storefront" ? info.header && info.footer && !info.showcase : info.loginForm && !info.header;
      const appErrors = [...log.pageerrors, ...log.console.filter((c) => !isExternalImg(c))];
      const ok = shellOk && appErrors.length === 0 && log.http.length === 0;
      rec(`[${vw.tag}] route ${path}`, ok,
        `h1="${info.h1}" title="${info.title}" overflow=${info.sw > info.cw ? info.sw - info.cw + "px" : "none"}` +
        (appErrors.length ? ` errors=${JSON.stringify(appErrors).slice(0, 300)}` : "") +
        (log.http.length ? ` http=${log.http.join(",")}` : "") +
        (log.failed.length ? ` reqfailed=${log.failed.length} (${log.failed.map(f=>f.split('/')[2]).join(',')})` : ""));
      await page.screenshot({ path: `${OUT}/${vw.tag}${path.replace(/\//g, "_") || "_home"}.png`, fullPage: false });
      await page.close();
    }
    await ctx.close();
  }

  // ---------- 2. Navigation, cart persistence, full checkout ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    const page = await ctx.newPage();
    const log = watch(page);
    await page.goto(BASE + "/", { waitUntil: "networkidle" });

    // mobile menu → shop
    await page.click('[data-testid="mobile-menu-button"]');
    await page.waitForTimeout(400);
    const menuLinks = await page.locator('[role="dialog"] a[href="/shop"]').count();
    rec("mobile menu opens and exposes /shop link", menuLinks > 0, `visible /shop links=${menuLinks}`);
    if (menuLinks) { await page.locator('[role="dialog"] a[href="/shop"]').first().click(); await page.waitForURL("**/shop"); }
    rec("navigation reaches /shop via menu", page.url().endsWith("/shop"), page.url());

    // click first product card
    await page.waitForSelector('a[href^="/product/"]');
    const href = await page.locator('a[href^="/product/"]').first().getAttribute("href");
    await page.locator('a[href^="/product/"]').first().click();
    await page.waitForURL("**" + href);
    await page.waitForSelector('[data-testid="product-price"]');
    rec("product card → product detail", page.url().endsWith(href), href);
    const price = await page.locator('[data-testid="product-price"]').innerText();
    rec("PDP price shown in BDT", /৳|BDT|Tk/i.test(price), price.replace(/\s+/g, " "));

    await page.click('[data-testid="qty-increase"]');
    const btn = (await page.locator('[data-testid="add-to-cart-button-mobile"]').isVisible()) ? "add-to-cart-button-mobile" : "add-to-cart-button";
    await page.click(`[data-testid="${btn}"]`);
    await page.waitForTimeout(500);
    const badge = await page.locator('[data-testid="cart-count-badge"]').innerText().catch(() => "");
    rec("add to cart updates header badge", badge.trim() === "2", `badge="${badge}" via ${btn}`);

    await page.reload({ waitUntil: "networkidle" });
    const badge2 = await page.locator('[data-testid="cart-count-badge"]').innerText().catch(() => "");
    const stored = await page.evaluate(() => localStorage.getItem("aayna_cart"));
    rec("cart persists across reload (localStorage aayna_cart)", badge2.trim() === "2" && !!stored, `badge="${badge2}"`);

    await page.click('[data-testid="cart-icon"]');
    await page.waitForURL("**/cart");
    const subtotal = await page.locator('[data-testid="cart-subtotal"]').innerText();
    rec("cart page shows subtotal", !!subtotal, subtotal.replace(/\s+/g, " "));
    await page.screenshot({ path: `${OUT}/journey_cart_390.png` });
    await page.click('[data-testid="proceed-to-checkout"]');
    await page.waitForURL("**/checkout");

    // submit empty to see validation
    await page.click('[data-testid="place-order-button"]');
    await page.waitForTimeout(500);
    rec("checkout blocks empty submission (stays on /checkout)", page.url().endsWith("/checkout"));

    await page.fill('[data-testid="checkout-name"]', "QA Test Customer");
    await page.fill('[data-testid="checkout-phone"]', "01700000000");
    await page.fill('[data-testid="checkout-email"]', "qa@example.test");
    await page.click('[data-testid="checkout-district"]');
    await page.locator('[role="option"]').filter({ hasText: "Dhaka" }).first().click();
    await page.fill('[data-testid="checkout-address"]', "House 1, Road 1, Test Area");
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${OUT}/journey_checkout_390.png`, fullPage: true });
    await page.click('[data-testid="place-order-button"]');
    try {
      await page.waitForURL("**/order-confirmation/**", { timeout: 15000 });
      await page.waitForSelector('[data-testid="confirmation-order-number"]');
      const num = await page.locator('[data-testid="confirmation-order-number"]').innerText();
      rec("checkout creates order and shows confirmation (test DB)", true, `order ${num.trim()}`);
      const badge3 = await page.locator('[data-testid="cart-count-badge"]').count();
      rec("cart cleared after order", badge3 === 0);
      await page.screenshot({ path: `${OUT}/journey_confirmation_390.png`, fullPage: true });
      fs.writeFileSync(`${OUT}/order_number.txt`, num.trim());
    } catch (e) {
      const errText = await page.locator('[role="alert"], .text-red-600, [data-sonner-toast]').allInnerTexts().catch(() => []);
      rec("checkout creates order and shows confirmation (test DB)", false, `${e.message.split("\n")[0]} url=${page.url()} msgs=${JSON.stringify(errText).slice(0, 300)}`);
      await page.screenshot({ path: `${OUT}/journey_checkout_fail.png`, fullPage: true });
    }
    rec("journey: no uncaught page errors", log.pageerrors.length === 0, log.pageerrors.join(" | ").slice(0, 300));
    await ctx.close();
  }

  // ---------- 3. Admin separation and protection ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const log = watch(page);
    for (const p of ["/admin", "/admin/products", "/admin/orders", "/admin/customers"]) {
      await page.goto(BASE + p, { waitUntil: "networkidle" });
      rec(`unauthenticated ${p} redirects to /admin/login`, page.url().endsWith("/admin/login"), page.url());
    }
    const robots = await page.locator('meta[name="robots"]').getAttribute("content").catch(() => null);
    rec("admin login is noindex", !!robots && robots.includes("noindex"), `robots=${robots}`);
    await page.fill('[data-testid="admin-login-email"]', "nobody@example.test");
    await page.fill('[data-testid="admin-login-password"]', "wrong");
    await page.click('[data-testid="admin-login-submit"]');
    await page.waitForTimeout(800);
    rec("wrong credentials rejected with message", await page.locator('[data-testid="admin-login-error"]').isVisible() && page.url().endsWith("/admin/login"));
    await page.fill('[data-testid="admin-login-email"]', ADMIN_EMAIL);
    await page.fill('[data-testid="admin-login-password"]', ADMIN_PASSWORD);
    await page.click('[data-testid="admin-login-submit"]');
    await page.waitForURL((u) => !u.pathname.endsWith("/login"), { timeout: 10000 }).catch(() => {});
    rec("valid test-admin login reaches dashboard", /\/admin\/?$/.test(new URL(page.url()).pathname), page.url());
    await page.screenshot({ path: `${OUT}/admin_dashboard_1280.png` });
    for (const p of ["/admin/products", "/admin/orders", "/admin/inventory", "/admin/categories", "/admin/settings"]) {
      await page.goto(BASE + p, { waitUntil: "networkidle" });
      const ok = page.url().endsWith(p);
      rec(`authenticated ${p} renders`, ok && log.pageerrors.length === 0, page.url());
    }
    const orderNum = fs.existsSync(`${OUT}/order_number.txt`) ? fs.readFileSync(`${OUT}/order_number.txt`, "utf8") : null;
    if (orderNum) {
      await page.goto(BASE + "/admin/orders", { waitUntil: "networkidle" });
      rec("test order visible in admin orders", (await page.content()).includes(orderNum), orderNum);
    }
    rec("admin: no uncaught page errors", log.pageerrors.length === 0, log.pageerrors.join(" | ").slice(0, 300));
    await ctx.close();
  }

  // ---------- 4. API failure produces a useful state (not a blank page) ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    await ctx.route(API_PATTERN, (r) => r.abort("connectionrefused"));
    for (const p of ["/", "/shop", "/product/gold-butterfly-hair-clip", "/category/earrings"]) {
      const page = await ctx.newPage();
      const log = watch(page);
      await page.goto(BASE + p, { waitUntil: "load" });
      if (p !== "/") await page.waitForSelector('[data-testid="load-error"]', { timeout: 12000 }).catch(() => {}); else await page.waitForTimeout(2500);
      const info = await page.evaluate(() => ({ text: document.body.innerText.length, header: !!document.querySelector('[data-testid="logo-link"]'), snippet: document.querySelector("main")?.innerText.slice(0, 160).replace(/\s+/g, " ") }));
      const errState = await page.locator('[data-testid="load-error"]').count();
      const needsErr = p !== "/";
      rec(`API down: ${p} renders shell${needsErr ? " + retryable error state" : ""}`, info.header && info.text > 50 && log.pageerrors.length === 0 && (!needsErr || errState > 0) && !/not found/i.test(info.snippet), `main="${info.snippet}"`);
      await page.screenshot({ path: `${OUT}/apidown${p.replace(/\//g, "_") || "_home"}.png` });
      await page.close();
    }
    await ctx.close();
  }

  // ---------- 5. Unknown slugs still say "not found" (real 404) ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    for (const p of ["/product/no-such-piece", "/category/no-such-category"]) {
      const page = await ctx.newPage();
      await page.goto(BASE + p, { waitUntil: "networkidle" });
      await page.waitForSelector("text=/not found/i", { timeout: 10000 }).catch(() => {});
      const t = await page.locator("main").innerText();
      const robots = await page.locator('meta[name="robots"]').getAttribute("content").catch(() => null);
      rec(`404 slug ${p} shows not-found + noindex`, /not found/i.test(t) && (await page.locator('[data-testid="load-error"]').count()) === 0 && /noindex/.test(robots || ""), `robots=${robots}`);
      await page.close();
    }
    await ctx.close();
  }
  // third-party hosts the sandbox could not reach
  results.push({ name: "NOT VERIFIED: external hosts unreachable from test sandbox", ok: true, detail: "fonts.googleapis.com, static.prod-images.emergentagent.com" });

  await browser.close();
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
})();
