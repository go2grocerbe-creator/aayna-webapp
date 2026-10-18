// Customer accounts, checkout coupons, tracking, welcome popup and admin
// promotions in a real browser, against an ISOLATED test backend only.
//
//   BASE_URL=http://localhost:3000 EMAIL_CAPTURE_FILE=/path/captured.jsonl \
//   ADMIN_EMAIL=... ADMIN_PASSWORD=... RESET_RATE_LIMITS_CMD="python -c ..." \
//   [CHROMIUM_PATH=...] node scripts/verify/customer_accounts_ui.js <outDir>
//
// The backend must run with EMAIL_MODE=capture (refused in production) so the
// test can open real verification/reset links. Test data only; secrets are
// never printed. Viewports: 390 (mobile), 768 (tablet), 1280 (desktop).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = `${BASE}/api`;
const OUT = process.argv[2] || "customer-accounts-out";
const CAPTURE = process.env.EMAIL_CAPTURE_FILE;
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };
const resetLimits = () => { if (process.env.RESET_RATE_LIMITS_CMD) execSync(process.env.RESET_RATE_LIMITS_CMD); };
const RUN = Date.now().toString(36);
const EMAIL = `maya.${RUN}@example.test`;
const PW1 = "a long and memorable passphrase";
const PW2 = "another fresh long passphrase";
const PHONE = "01712345678";

function lastLink(kind, to) {
  const lines = fs.readFileSync(CAPTURE, "utf8").trim().split("\n").map((l) => JSON.parse(l)).reverse();
  for (const m of lines) {
    if (to && m.to !== to) continue;
    const found = m.text.match(new RegExp(`(https?://[^\\s]+${kind.replace(/\//g, "\\/")}#token=[A-Za-z0-9_-]+)`));
    if (found) return found[1];
  }
  return null;
}
const mails = (to) => fs.readFileSync(CAPTURE, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l)).filter((m) => !to || m.to === to);
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function adminToken() {
  const r = await fetch(`${API}/admin/login`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD }) });
  return (await r.json()).token;
}
async function adminCall(token, method, p, body) {
  const r = await fetch(API + p, { method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}
async function addToCart(page, slug) {
  await page.goto(`${BASE}/product/${slug}`, { waitUntil: "networkidle" });
  const mobile = (page.viewportSize() || { width: 1280 }).width < 768;
  await page.click(mobile ? '[data-testid="add-to-cart-button-mobile"]' : '[data-testid="add-to-cart-button"]');
  await page.waitForTimeout(300);
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const products = await (await fetch(`${API}/products`)).json();
  const pick = products.filter((p) => p.stock_quantity >= 3 && p.status === "active").sort((a, b) => b.selling_price - a.selling_price);
  const P1 = pick[0], P2 = pick[1];
  const admin = await adminToken();
  rec("test catalogue and admin login available", !!P1 && !!P2 && !!admin);
  const stockBefore = {};
  for (const p of [P1, P2]) stockBefore[p.id] = p.stock_quantity;

  // --- 1. Unauthenticated access ------------------------------------------------
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await desk.newPage();
  await page.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
  await page.goto(`${BASE}/account/orders`, { waitUntil: "networkidle" });
  rec("signed-out /account/orders -> login with next", /\/login\?next=%2Faccount%2Forders/.test(page.url()), page.url().replace(BASE, ""));
  const robots = await page.$eval('meta[name="robots"]', (m) => m.content).catch(() => "");
  rec("login page is noindex", /noindex/.test(robots), robots);
  rec("Google button hidden while Google is not configured", (await page.$('[data-testid="google-signin"]')) === null);
  for (const p of ["/account/me", "/account/orders", "/account/addresses"]) {
    rec(`API ${p} without session -> 401`, (await fetch(API + p)).status === 401);
  }

  // --- 2. Registration (validation, then success) -----------------------------
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.click('[data-testid="register-submit"]');
  const fieldErrors = await page.$$eval('[id$="-error"]', (els) => els.length);
  rec("empty registration shows field errors", fieldErrors >= 5, `${fieldErrors} errors`);
  await page.fill('[data-testid="register-name"]', "Maya Rahman");
  await page.fill('[data-testid="register-email"]', EMAIL);
  await page.fill('[data-testid="register-phone"]', PHONE);
  await page.fill('[data-testid="register-password"]', PW1);
  await page.fill('[data-testid="register-confirm"]', PW1);
  await page.check('[data-testid="register-terms"]');
  rec("password field has visibility toggle", (await page.$('button[aria-label="Show password"]')) !== null);
  await page.click('[data-testid="register-submit"]');
  await page.waitForSelector('[data-testid="register-sent"]', { timeout: 15000 });
  rec("registration -> check-your-email state", true);
  await page.screenshot({ path: path.join(OUT, "register-sent-1280.png") });
  const verifyUrl = lastLink("/verify-email", EMAIL);
  rec("verification email captured with fragment link", !!verifyUrl && verifyUrl.startsWith(BASE));
  const vm = mails(EMAIL).pop();
  rec("verification email from accounts@shopaayna.com", /accounts@shopaayna\.com/.test(vm.from), vm.from);

  // login before verification: explained only with the right password
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="login-email"]', EMAIL);
  await page.fill('[data-testid="login-password"]', PW1);
  await page.click('[data-testid="login-submit"]');
  await page.waitForSelector('[data-testid="login-resend"]', { timeout: 10000 });
  rec("unverified login -> confirm-email message with resend", true);

  // --- 3. Verify link ---------------------------------------------------------------
  await page.goto(verifyUrl, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="verify-success"]', { timeout: 15000 });
  rec("verify link -> email confirmed and signed in", true);
  rec("token removed from address bar", !page.url().includes("token="), page.url().replace(BASE, ""));
  await page.goto(`${BASE}/shop`, { waitUntil: "networkidle" });
  await page.goto(verifyUrl, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="verify-used"]', { timeout: 10000 });
  rec("re-opening the same link -> already used", true);
  await page.goto(`${BASE}/account`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="account-no-orders"]', { timeout: 10000 });
  const hello = await page.textContent("h1");
  rec("account home: greeting and polished empty state", /Hello, Maya/.test(hello), hello.trim());
  const cookies = await desk.cookies();
  const sid = cookies.find((c) => c.name.endsWith("aayna_sid"));
  rec("session cookie is HttpOnly, SameSite=Lax", !!sid && sid.httpOnly && sid.sameSite === "Lax");
  const ls = await page.evaluate(() => Object.keys(localStorage).join(","));
  rec("no session token in localStorage", !/sid|session|token/i.test(ls), ls);
  await page.click('[data-testid="account-icon"]');
  rec("header account icon -> /account", page.url().endsWith("/account"));

  // --- 4. Addresses & profile ----------------------------------------------------
  await page.goto(`${BASE}/account/addresses`, { waitUntil: "networkidle" });
  await page.click('[data-testid="addresses-empty"] button');
  await page.click('[data-testid="address-save"]');
  await page.waitForTimeout(500);
  rec("empty address form shows server field errors", (await page.$$('[data-testid="address-form"] [id$="-error"]')).length >= 3);
  await page.fill('[data-testid="address-name"]', "Maya Rahman");
  await page.fill('[data-testid="address-phone"]', PHONE);
  await page.selectOption('[data-testid="address-district"]', "Dhaka");
  await page.fill('[data-testid="address-text"]', "House 12, Road 5, Dhanmondi");
  await page.click('[data-testid="address-save"]');
  await page.waitForSelector('[data-testid="address-card"]', { timeout: 10000 });
  rec("address saved and shown as default", /Default/.test(await page.textContent('[data-testid="address-card"]')));
  await page.goto(`${BASE}/account/profile`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="profile-phone"]', "01812345678");
  await page.click('[data-testid="profile-save"]');
  await page.waitForTimeout(800);
  const me = await page.evaluate(async () => (await fetch("/api/account/me", { credentials: "include" })).json());
  rec("profile phone updated (normalised)", me.phone === "+8801812345678", me.phone);

  // --- 5. Promotion via admin API, signed-in checkout with coupon ------------------
  const code = `TEST${RUN.toUpperCase().slice(-5)}`;
  const created = await adminCall(admin, "POST", "/admin/promotions", { code, name: "Browser test 10%", type: "percent", value: 10, max_discount_bdt: 50, usage_limit_total: 5, usage_limit_per_customer: 1 });
  const act = await adminCall(admin, "POST", `/admin/promotions/${created.json.id}/activate`, { confirm: true, note: "isolated test" });
  rec("admin creates draft and activates coupon (test env)", created.status === 200 && created.json.status === "draft" && act.status === 200);
  await addToCart(page, P1.slug);
  await page.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="checkout-signed-in"]');
  const prefill = { name: await page.inputValue('[data-testid="checkout-name"]'), phone: await page.inputValue('[data-testid="checkout-phone"]'), addr: await page.inputValue('[data-testid="checkout-address"]') };
  rec("checkout prefilled from account and default address", prefill.name === "Maya Rahman" && prefill.phone === PHONE && /Dhanmondi/.test(prefill.addr), JSON.stringify(prefill));
  await page.fill('[data-testid="checkout-coupon-input"]', "NOPE123");
  await page.click('[data-testid="checkout-coupon-apply"]');
  await page.waitForSelector('[data-testid="checkout-coupon-error"]');
  rec("invalid coupon -> clear message", /isn't valid/.test(await page.textContent('[data-testid="checkout-coupon-error"]')));
  await page.fill('[data-testid="checkout-coupon-input"]', code.toLowerCase());
  await page.click('[data-testid="checkout-coupon-apply"]');
  await page.waitForSelector('[data-testid="checkout-discount"]');
  const discTxt = await page.textContent('[data-testid="checkout-discount"]');
  const expected = Math.min(50, Math.floor((P1.discount_price || P1.selling_price) * 0.1));
  rec("coupon applied with server-calculated, capped discount", discTxt.includes(`৳${expected}`), discTxt);
  await page.screenshot({ path: path.join(OUT, "checkout-coupon-1280.png"), fullPage: true });
  await page.click('[data-testid="place-order-button"]');
  await page.waitForURL(/order-confirmation/, { timeout: 20000 });
  await page.waitForSelector('[data-testid="confirmation-order-number"]');
  const orderNum = (await page.textContent('[data-testid="confirmation-order-number"]')).trim();
  rec("order placed; confirmation shows discount", !!(await page.$('[data-testid="confirmation-discount"]')), orderNum);
  rec("confirmation says the order is in the account", !!(await page.$('[data-testid="confirmation-in-account"]')));
  rec("order confirmation email sent from orders@shopaayna.com", mails(EMAIL).some((m) => m.template === "order_confirmation" && /orders@shopaayna\.com/.test(m.from)));

  // --- 6. Order history, detail, timeline after an admin status change --------
  await adminCall(admin, "PUT", `/admin/orders/${orderNum}`, { order_status: "Confirmed", courier_name: "Pathao", courier_tracking_code: "PTH-TEST-1" });
  await page.goto(`${BASE}/account/orders`, { waitUntil: "networkidle" });
  rec("order history lists the order", !!(await page.$(`[data-testid="account-order-${orderNum}"]`)));
  await page.click(`[data-testid="account-order-${orderNum}"]`);
  await page.waitForSelector('[data-testid="order-timeline"]');
  const tl = await page.textContent('[data-testid="order-timeline"]');
  rec("order detail timeline: received + confirmed recorded, later steps pending", /Order received/.test(tl) && /Order confirmed - completed/.test(tl) && /Handed to courier - not yet/.test(tl));
  rec("order detail shows courier and discount", !!(await page.$('[data-testid="account-order-courier"]')) && !!(await page.$('[data-testid="account-order-discount"]')));
  rec("status email sent for Confirmed", mails(EMAIL).some((m) => m.template === "order_status"));
  const other = await page.evaluate(async () => (await fetch("/api/account/orders/ORD-999999", { credentials: "include" })).status);
  rec("unknown/foreign order detail -> 404", other === 404);

  // --- 7. Guest order, then save it to the account with the confirmation token
  const guest = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const gp = await guest.newPage();
  await gp.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
  await addToCart(gp, P2.slug);
  await gp.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
  await gp.fill('[data-testid="checkout-name"]', "Maya Rahman");
  await gp.fill('[data-testid="checkout-phone"]', PHONE);
  await gp.click('[data-testid="checkout-district"]');
  await gp.click('[role="option"]:has-text("Dhaka")');
  await gp.fill('[data-testid="checkout-address"]', "House 12, Road 5, Dhanmondi");
  let confirmUrl = null;
  gp.on("framenavigated", (f) => { if (f === gp.mainFrame() && /token=/.test(f.url())) confirmUrl = f.url(); });
  await gp.click('[data-testid="place-order-button"]');
  await gp.waitForSelector('[data-testid="confirmation-order-number"]', { timeout: 20000 });
  const guestNum = (await gp.textContent('[data-testid="confirmation-order-number"]')).trim();
  rec("guest checkout still works (no account needed)", !!guestNum && !(await gp.$('[data-testid="confirmation-in-account"]')), guestNum);
  rec("guest phone match alone does not expose the order", !(await page.evaluate(async () => (await (await fetch("/api/account/orders", { credentials: "include" })).json()).map((o) => o.order_number))).includes(guestNum));
  await page.goto(confirmUrl, { waitUntil: "networkidle" });
  await page.click('[data-testid="confirmation-save"] button');
  await page.waitForTimeout(800);
  const nowMine = await page.evaluate(async () => (await (await fetch("/api/account/orders", { credentials: "include" })).json()).map((o) => o.order_number));
  rec("guest order saved to account with confirmation token", nowMine.includes(guestNum));
  await guest.close();

  // --- 8. Track page timeline (guest) --------------------------------------------
  const tp = await desk.newPage();
  await tp.goto(`${BASE}/track-order`, { waitUntil: "networkidle" });
  await tp.fill('[data-testid="track-order-number"]', orderNum);
  await tp.fill('[data-testid="track-phone"]', PHONE);
  await tp.click('[data-testid="track-submit"]');
  await tp.waitForSelector(`[data-testid="track-timeline-${orderNum}"]`, { timeout: 10000 });
  rec("track order shows the recorded timeline", /Order confirmed - completed/.test(await tp.textContent(`[data-testid="track-timeline-${orderNum}"]`)));
  await tp.close();

  // --- 9. Security: sessions, password change, logout ----------------------------
  const second = await browser.newContext();
  const sp = await second.newPage();
  await sp.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await sp.fill('[data-testid="login-email"]', EMAIL);
  await sp.fill('[data-testid="login-password"]', PW1);
  await sp.click('[data-testid="login-submit"]');
  await sp.waitForURL(/\/account$/, { timeout: 15000 });
  await page.goto(`${BASE}/account/security`, { waitUntil: "networkidle" });
  const sessCount = await page.$$eval('[data-testid="session-list"] li', (l) => l.length);
  rec("security page lists both signed-in devices", sessCount === 2, `${sessCount}`);
  await page.click('[data-testid="revoke-others"]');
  await page.waitForTimeout(800);
  await sp.goto(`${BASE}/account`, { waitUntil: "networkidle" });
  rec("other device signed out after 'sign out other devices'", /\/login/.test(sp.url()));
  await second.close();
  await page.click('[data-testid="account-logout"]');
  await page.waitForURL((u) => u.pathname === "/", { timeout: 10000 });
  await page.goto(`${BASE}/account`, { waitUntil: "networkidle" });
  rec("logout ends the session", /\/login/.test(page.url()));

  // --- 10. Forgot / reset password -------------------------------------------------
  resetLimits();
  await page.goto(`${BASE}/forgot-password`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="forgot-email"]', `nobody.${RUN}@example.test`);
  await page.click('[data-testid="forgot-submit"]');
  await page.waitForSelector('[data-testid="forgot-status"]');
  const unknownMsg = (await page.textContent('[data-testid="forgot-status"]')).trim();
  await page.fill('[data-testid="forgot-email"]', EMAIL);
  await page.click('[data-testid="forgot-submit"]');
  await page.waitForTimeout(800);
  const knownMsg = (await page.textContent('[data-testid="forgot-status"]')).trim();
  rec("forgot password: same message for unknown and known email", unknownMsg === knownMsg && /If an eligible account exists/.test(knownMsg));
  rec("no reset email for the unknown address", mails(`nobody.${RUN}@example.test`).length === 0);
  const resetUrl = lastLink("/reset-password", EMAIL);
  await page.goto(resetUrl, { waitUntil: "networkidle" });
  rec("reset token removed from address bar", !page.url().includes("token="));
  await page.fill('[data-testid="reset-password"]', PW2);
  await page.fill('[data-testid="reset-confirm"]', PW2);
  await page.click('[data-testid="reset-submit"]');
  await page.waitForSelector('[data-testid="reset-done"]', { timeout: 10000 });
  rec("password reset succeeds", true);
  await page.goto(`${BASE}/shop`, { waitUntil: "networkidle" });
  await page.goto(resetUrl, { waitUntil: "networkidle" });
  await page.fill('[data-testid="reset-password"]', "yet another long phrase");
  await page.fill('[data-testid="reset-confirm"]', "yet another long phrase");
  await page.click('[data-testid="reset-submit"]');
  await page.waitForSelector('[data-testid="reset-status"]');
  rec("reset link cannot be used twice", /already been used/.test(await page.textContent('[data-testid="reset-status"]')));
  resetLimits();
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="login-email"]', EMAIL);
  await page.fill('[data-testid="login-password"]', PW1);
  await page.click('[data-testid="login-submit"]');
  await page.waitForSelector('[data-testid="login-status"]');
  rec("old password rejected after reset", /Invalid email or password/.test(await page.textContent('[data-testid="login-status"]')));
  await page.fill('[data-testid="login-password"]', PW2);
  await page.click('[data-testid="login-submit"]');
  await page.waitForURL(/\/account$/, { timeout: 15000 });
  rec("new password accepted", true);
  rec("password-changed notice emailed", mails(EMAIL).some((m) => m.template === "password_changed"));

  // --- 11. Google button (config mocked in the browser only) -----------------------
  const gctx = await browser.newContext();
  const g = await gctx.newPage();
  await g.route("**/api/customer/config", (r) => r.fulfill({ json: { google_enabled: true, email_enabled: true, password_min_length: 12 } }));
  await g.goto(`${BASE}/login?next=/account/orders`, { waitUntil: "networkidle" });
  const href = await g.getAttribute('[data-testid="google-signin"]', "href");
  rec("Google button links to server-side start with safe next", href === "/api/auth/google/start?next=%2Faccount%2Forders&mode=login", href);
  await g.click('[data-testid="google-signin"]');
  await g.waitForURL(/error=google_unavailable/, { timeout: 10000 });
  rec("unconfigured Google -> graceful message", /isn't available yet/.test(await g.textContent('[data-testid="login-status"]')));
  await gctx.close();

  // --- 12. Welcome popup ------------------------------------------------------------
  const wctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const w = await wctx.newPage();
  await w.goto(`${BASE}/`, { waitUntil: "networkidle" });
  rec("popup not shown immediately", (await w.$('[data-testid="welcome-popup"]')) === null);
  await w.waitForSelector('[data-testid="welcome-popup"]', { timeout: 20000 });
  const ptxt = await w.textContent('[data-testid="welcome-popup"]');
  rec("popup appears after delay; no discount promised while campaign disabled", !/%|off/i.test(ptxt), ptxt.replace(/\s+/g, " ").slice(0, 90));
  await w.waitForTimeout(900); // let the fade-in finish before the screenshot
  rec("popup fits 390px (no overflow)", (await overflow(w)) <= 1);
  await w.screenshot({ path: path.join(OUT, "welcome-popup-390.png") });
  await w.keyboard.press("Escape");
  rec("Escape dismisses popup", (await w.$('[data-testid="welcome-popup"]')) === null);
  await w.reload({ waitUntil: "networkidle" });
  await w.waitForTimeout(14000);
  rec("dismissed popup does not come back", (await w.$('[data-testid="welcome-popup"]')) === null);
  await wctx.close();
  const cctx = await browser.newContext();
  const c = await cctx.newPage();
  await c.goto(`${BASE}/track-order`, { waitUntil: "networkidle" });
  await c.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
  await c.waitForTimeout(13500);
  rec("popup never shown on checkout", (await c.$('[data-testid="welcome-popup"]')) === null);
  await cctx.close();

  // --- 13. Admin: promotions, welcome campaign, accounts ----------------------------
  const actx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const a = await actx.newPage();
  await a.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
  await a.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
  await a.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
  await a.click('[data-testid="admin-login-submit"]');
  await a.waitForURL(/\/admin\/?$/, { timeout: 20000 });
  await a.click('[data-testid="admin-nav-promotions"]');
  await a.waitForSelector(`[data-testid="promo-row-${code}"]`);
  await a.click(`[data-testid="promo-row-${code}"]`);
  await a.waitForSelector('[data-testid="promotion-detail"]');
  const det = await a.textContent('[data-testid="promotion-detail"]');
  rec("admin promotion detail shows real redemption and audit", /Redemptions1/.test(det.replace(/\s+/g, "")) && det.includes(orderNum) && /activated/.test(det));
  await a.click('[data-testid="promo-new"]');
  await a.fill('[data-testid="promo-code"]', `DRAFT${RUN.toUpperCase().slice(-4)}`);
  await a.fill('[data-testid="promo-name"]', "Draft only");
  await a.fill('[data-testid="promo-value"]', "15");
  await a.fill('[data-testid="promo-max"]', "120");
  await a.waitForSelector('[data-testid="promo-preview-result"]', { timeout: 10000 });
  const prev = await a.textContent('[data-testid="promo-preview-result"]');
  rec("promotion form shows server preview before activation", /৳120/.test(prev), prev.trim());
  await a.click('[data-testid="promo-save"]');
  await a.waitForSelector('[data-testid="promotion-detail"]');
  rec("new code saved as draft (not usable)", /draft/.test(await a.textContent('[data-testid="promotion-detail"]')));
  await a.click('text=Welcome offer');
  await a.waitForSelector('[data-testid="welcome-campaign"]');
  rec("welcome campaign shown disabled with proposed (unapproved) limits",
      (await a.textContent('[data-testid="welcome-status"]')).trim() === "Disabled" && /Not approved yet/.test(await a.textContent('[data-testid="welcome-campaign"]')));
  await a.screenshot({ path: path.join(OUT, "admin-welcome-1280.png"), fullPage: true });
  await a.click('[data-testid="admin-nav-accounts"]');
  await a.waitForSelector('[data-testid="account-row"]');
  rec("admin accounts list shows the registered customer", (await a.textContent('[data-testid="admin-accounts"]')).includes(EMAIL));
  await a.click('[data-testid="account-row"] a');
  await a.waitForSelector('[data-testid="admin-account-detail"]');
  const ad = await a.textContent('[data-testid="admin-account-detail"]');
  rec("admin account detail: orders, events, emails; no secrets", ad.includes(orderNum) && /password reset/.test(ad) && !/password_hash|token_hash/.test(ad));
  await a.goto(`${BASE}/admin/orders/${orderNum}`, { waitUntil: "networkidle" });
  await a.waitForSelector('[data-testid="admin-order-emails"]');
  rec("admin order shows coupon, customer emails and status history",
      !!(await a.$('[data-testid="admin-order-discount"]')) && /order confirmation/.test(await a.textContent('[data-testid="admin-order-emails"]')));
  rec("customer cookie does not open the admin API", (await page.evaluate(async () => (await fetch("/api/admin/products", { credentials: "include" })).status)) === 401);
  await actx.close();

  // --- 14. Responsive sweep (390 / 768 / 1280) ------------------------------------
  const routes = ["/login", "/register", "/forgot-password", "/verify-email", "/account", "/account/orders", `/account/orders/${orderNum}`,
    "/account/addresses", "/account/profile", "/account/security", "/account/rewards", "/checkout", "/track-order"];
  const state = await desk.storageState();
  for (const width of [390, 768, 1280]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, storageState: state });
    const p = await ctx.newPage();
    await addToCart(p, P2.slug);
    const bad = [];
    for (const r of routes) {
      await p.goto(BASE + r, { waitUntil: "networkidle" });
      await p.waitForTimeout(250);
      const ov = await overflow(p);
      const blank = (await p.evaluate(() => document.querySelector("main")?.innerText.trim().length || 0)) < 20;
      if (ov > 1 || blank) bad.push(`${r} ov=${ov}${blank ? " blank" : ""}`);
      if (["/account", `/account/orders/${orderNum}`, "/register", "/checkout"].includes(r)) {
        await p.screenshot({ path: path.join(OUT, `${r.replace(/\//g, "_") || "_root"}-${width}.png`), fullPage: true });
      }
    }
    rec(`${width}px: ${routes.length} routes render without horizontal overflow`, bad.length === 0, bad.join("; "));
    await ctx.close();
  }

  // --- 15. Stock integrity ------------------------------------------------------------
  const after = await (await fetch(`${API}/products`)).json();
  const s1 = after.find((p) => p.id === P1.id).stock_quantity, s2 = after.find((p) => p.id === P2.id).stock_quantity;
  rec("stock decreased exactly by the 2 real test orders", s1 === stockBefore[P1.id] - 1 && s2 === stockBefore[P2.id] - 1, `${s1}, ${s2}`);

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} passed`);
  fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify(results, null, 1));
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("ERROR", e.message.split("\n")[0]); process.exit(2); });
