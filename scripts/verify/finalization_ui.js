// Release-candidate finalization suite: the flows not covered by customer_accounts_ui.js,
// in a real browser against an ISOLATED test backend only (EMAIL_MODE=capture).
//
//   BASE_URL=http://localhost:3000 EMAIL_CAPTURE_FILE=/path/captured.jsonl ADMIN_EMAIL=... ADMIN_PASSWORD=... \
//   ROLE_USERS_JSON=users.json DB_CMD="python dbtool.py" RESET_RATE_LIMITS_CMD="..." \
//   [CHROMIUM_PATH=...] node scripts/verify/finalization_ui.js <outDir>
//
// Covers: guest-order claiming (valid / invalid / replayed / other account / expired / email
// mismatch), saved addresses CRUD + default + IDOR, profile + email change, password change,
// deletion request, suspension/reactivation, admin Accounts search/filter, promotion rules
// (fixed, min, caps, scheduled, expired, paused, total limit, first order, category,
// activation authority, restore), admin order status -> tracking + email, checkout
// validation, double-submit, idempotent retry and logout protection.
// Test identities only; passwords are generated per run and never printed.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execSync } = require("child_process");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = `${BASE}/api`;
const OUT = process.argv[2] || "finalization-out";
const CAPTURE = process.env.EMAIL_CAPTURE_FILE;
const USERS = process.env.ROLE_USERS_JSON ? JSON.parse(fs.readFileSync(process.env.ROLE_USERS_JSON, "utf8")) : {};
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (n, ok, d = "") => { results.push({ n, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  — " + d : ""}`); };
const resetLimits = () => { if (process.env.RESET_RATE_LIMITS_CMD) execSync(process.env.RESET_RATE_LIMITS_CMD); };
const db = (args) => JSON.parse(execSync(`${process.env.DB_CMD} ${args}`).toString());
const RUN = Date.now().toString(36);
const PW = () => "test " + crypto.randomBytes(9).toString("base64url") + " phrase";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const mails = (to) => (fs.existsSync(CAPTURE) ? fs.readFileSync(CAPTURE, "utf8") : "").trim().split("\n").filter(Boolean)
  .map((l) => JSON.parse(l)).filter((m) => !to || m.to === to);
function lastLink(kind, to) {
  for (const m of mails(to).reverse()) {
    const found = m.text.match(new RegExp(`(https?://[^\\s]+${kind.replace(/\//g, "\\/")}#token=[A-Za-z0-9_-]+)`));
    if (found) return found[1];
  }
  return null;
}
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function api(method, p, { token, body } = {}) {
  const r = await fetch(API + p, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}
async function adminLogin(email, password) { return (await api("POST", "/admin/login", { body: { email, password } })).json?.token; }
// fetch from inside a page: uses that browser context's customer cookie, plus the CSRF header
const inPage = (page, method, p, body) => page.evaluate(async ({ method, p, body }) => {
  const r = await fetch("/api" + p, { method, credentials: "include", headers: { "Content-Type": "application/json", "X-AAYNA-CSRF": "1" },
    body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await r.json(); } catch {}
  return { status: r.status, json };
}, { method, p, body });

async function newPage(browser, width = 1280) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await ctx.newPage();
  await page.addInitScript(() => { try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ dismissedAt: Date.now() })); } catch {} });
  return { ctx, page };
}
async function registerVerified(browser, { name, email, phone, password }) {
  const { ctx, page } = await newPage(browser);
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  const r = await inPage(page, "POST", "/customer/register", { full_name: name, email, phone, password, confirm_password: password, accept_terms: true });
  if (r.status !== 200) throw new Error(`register ${r.status}`);
  await page.goto(lastLink("/verify-email", email), { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="verify-success"]', { timeout: 15000 });
  return { ctx, page };
}
async function uiLogin(page, email, password) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('[data-testid="login-email"]', email);
  await page.fill('[data-testid="login-password"]', password);
  await page.click('[data-testid="login-submit"]');
}
const orderBody = (pid, { phone = "01712345678", email = "", coupon, rid, qty = 1, name = "Test Customer" } = {}) => ({
  customer_name: name, customer_phone: phone, customer_email: email, district: "Dhaka", payment_method: "cod",
  delivery_address: "House 3, Road 7, Dhanmondi (test)", items: [{ product_id: pid, quantity: qty }],
  ...(coupon ? { coupon_code: coupon } : {}), ...(rid ? { client_request_id: rid } : {}) });
async function guestOrder(pid, opts) { return api("POST", "/checkout", { body: orderBody(pid, opts) }); }
async function validate(pid, code, { phone, page, qty = 1 } = {}) {
  const body = { items: [{ product_id: pid, quantity: qty }], coupon_code: code, ...(phone ? { phone } : {}) };
  const r = page ? await inPage(page, "POST", "/cart/validate", body) : await api("POST", "/cart/validate", { body });
  return r.json?.coupon || {};
}
async function promo(token, over, activate = true) {
  const body = { code: over.code, name: over.code, type: "percent", value: 10, usage_limit_per_customer: null, min_subtotal: 0, ...over };
  const c = await api("POST", "/admin/promotions", { token, body });
  if (c.status !== 200) throw new Error(`promo ${over.code}: ${c.status} ${JSON.stringify(c.json)}`);
  if (activate) {
    const a = await api("POST", `/admin/promotions/${c.json.id}/activate`, { token, body: { confirm: true } });
    if (a.status !== 200) throw new Error(`activate ${over.code}: ${a.status}`);
  }
  return c.json;
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const admin = await adminLogin(process.env.ADMIN_EMAIL, process.env.ADMIN_PASSWORD);
  const products = await (await fetch(`${API}/products`)).json();
  const active = products.filter((p) => p.status === "active" && p.stock_quantity >= 4).sort((a, b) => b.selling_price - a.selling_price);
  const P = active[0], Q = active[active.length - 1];
  const OTHER_CAT = active.find((p) => p.category_slug !== P.category_slug);
  rec("setup: test catalogue, admin, role users", !!admin && !!P && !!Q && !!OTHER_CAT && !!USERS.admin && !!USERS.product_manager && !!USERS.order_manager);
  const roleTok = {};
  for (const r of ["admin", "product_manager", "order_manager"]) roleTok[r] = await adminLogin(USERS[r].email, USERS[r].password);

  const A = { name: "Nadia Test", email: `nadia.${RUN}@example.test`, phone: "01711000001", password: PW() };
  const B = { name: "Rafi Test", email: `rafi.${RUN}@example.test`, phone: "01811000002", password: PW() };
  const a = await registerVerified(browser, A);
  const b = await registerVerified(browser, B);
  rec("two isolated test customers registered and verified", true);

  // ================= 1. Guest-order claiming =====================================
  const { ctx: gctx, page: gp } = await newPage(browser, 390);
  await gp.goto(`${BASE}/product/${Q.slug}`, { waitUntil: "networkidle" });
  await gp.click('[data-testid="add-to-cart-button-mobile"]');
  await gp.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
  await gp.fill('[data-testid="checkout-name"]', "Nadia Test");
  await gp.fill('[data-testid="checkout-phone"]', A.phone);
  await gp.fill('[data-testid="checkout-email"]', A.email);
  await gp.click('[data-testid="checkout-district"]');
  await gp.click('[role="option"]:has-text("Dhaka")');
  await gp.fill('[data-testid="checkout-address"]', "House 4, Road 1, Uttara (test)");
  let confirmUrl = null;
  gp.on("framenavigated", (f) => { if (f === gp.mainFrame() && /token=/.test(f.url())) confirmUrl = f.url(); });
  await gp.click('[data-testid="place-order-button"]');
  await gp.waitForSelector('[data-testid="confirmation-order-number"]', { timeout: 20000 });
  const claimNum = (await gp.textContent('[data-testid="confirmation-order-number"]')).trim();
  const claimTok = new URL(confirmUrl).searchParams.get("token");
  rec("guest order placed; confirmation token removed from the address bar", !!claimTok && !gp.url().includes("token="), claimNum);
  await gctx.close();

  const bad = await inPage(b.page, "POST", "/account/orders/claim", { order_number: claimNum, confirmation_token: "x".repeat(43) });
  rec("claim with a wrong token -> generic 404, nothing linked", bad.status === 404 && /couldn't match/.test(bad.json.detail) && !db(`order ${claimNum}`).account_id);
  const none = await inPage(b.page, "POST", "/account/orders/claim", { order_number: claimNum });
  rec("claim with no token -> 404", none.status === 404);
  const byMail = await inPage(b.page, "POST", "/account/orders/claim-by-email", { order_number: claimNum });
  rec("claim-by-email from an account with a different email: same generic answer, no email sent",
      byMail.status === 200 && mails(B.email).every((m) => m.template !== "order_claim") && mails(A.email).every((m) => m.template !== "order_claim"));
  const unauth = await api("POST", "/account/orders/claim", { body: { order_number: claimNum, confirmation_token: claimTok } });
  rec("claim without signing in -> 401/403", [401, 403].includes(unauth.status), `${unauth.status}`);
  await a.page.goto(confirmUrl, { waitUntil: "networkidle" });
  await a.page.click('[data-testid="confirmation-save"] button');
  await a.page.waitForTimeout(800);
  const linked = db(`order ${claimNum}`);
  rec("owner saves the guest order with its confirmation token", linked.account_link_method === "confirmation_token");
  const steal = await inPage(b.page, "POST", "/account/orders/claim", { order_number: claimNum, confirmation_token: claimTok });
  rec("replayed token by another account cannot move a linked order", steal.status === 404 && db(`order ${claimNum}`).account_id === linked.account_id);
  const again = await inPage(a.page, "POST", "/account/orders/claim", { order_number: claimNum, confirmation_token: claimTok });
  rec("owner replay is idempotent (already linked)", again.status === 200 && again.json.already_linked === true);
  const foreign = await inPage(b.page, "GET", `/account/orders/${claimNum}`);
  rec("another account cannot open the claimed order (404)", foreign.status === 404);

  // email-link claim
  const mailOrder = (await guestOrder(Q.id, { phone: A.phone, email: A.email })).json.order_number;
  await a.page.goto(`${BASE}/account/orders`, { waitUntil: "networkidle" });
  await a.page.click("text=Missing an order you placed as a guest?");
  await a.page.fill('[data-testid="claim-order-number"]', mailOrder);
  await a.page.click("text=Email me a link");
  await a.page.waitForSelector("text=we've emailed you a link", { timeout: 10000 });
  const claimLink = lastLink("/account/orders/claim", A.email);
  rec("claim-by-email: link sent only to the order's recorded address", !!claimLink && mails(A.email).some((m) => m.template === "order_claim"));
  await b.page.goto(claimLink, { waitUntil: "networkidle" });
  await b.page.waitForSelector('[data-testid="claim-confirm-page"]');
  await b.page.waitForTimeout(800);
  rec("link opened while signed in to another account: refused, link not spent",
      /Sign in to the account that requested/.test(await b.page.textContent('[data-testid="claim-confirm-page"]')) && !db(`order ${mailOrder}`).account_id);
  await a.page.goto(claimLink, { waitUntil: "networkidle" });
  await a.page.waitForTimeout(1000);
  rec("owner opens the link: order added", db(`order ${mailOrder}`).account_link_method === "email_link",
      (await a.page.textContent('[data-testid="claim-confirm-page"]')).replace(/\s+/g, " ").slice(0, 80));
  await a.page.goto(`${BASE}/shop`, { waitUntil: "networkidle" });
  await a.page.goto(claimLink, { waitUntil: "networkidle" });
  await a.page.waitForTimeout(800);
  rec("replayed claim link -> already used", /already been used/.test(await a.page.textContent('[data-testid="claim-confirm-page"]')));
  const expOrder = (await guestOrder(Q.id, { phone: A.phone, email: A.email })).json.order_number;
  await inPage(a.page, "POST", "/account/orders/claim-by-email", { order_number: expOrder });
  const expLink = lastLink("/account/orders/claim", A.email);
  const expired = db(`expire-tokens order_claim ${A.email}`).expired;
  await a.page.goto(`${BASE}/shop`, { waitUntil: "networkidle" }); // a fresh document, not a same-page hash change
  await a.page.goto(expLink, { waitUntil: "networkidle" });
  await a.page.waitForTimeout(1200);
  const expTxt = (await a.page.textContent('[data-testid="claim-confirm-page"]')).replace(/\s+/g, " ");
  rec("expired claim link -> expired message, order not linked",
      /expired/.test(expTxt) && !db(`order ${expOrder}`).account_id, `expired=${expired} ${expTxt.slice(0, 90)}`);
  const hist = (await inPage(a.page, "GET", "/account/orders")).json.map((o) => o.order_number);
  rec("order history shows exactly the owner's claimed orders", hist.includes(claimNum) && hist.includes(mailOrder) && !hist.includes(expOrder));
  rec("phone match alone links nothing to the other account", (await inPage(b.page, "GET", "/account/orders")).json.length === 0);

  // ================= 2. Saved addresses ============================================
  const ap = a.page;
  await ap.goto(`${BASE}/account/addresses`, { waitUntil: "networkidle" });
  async function fillAddress(name, phone, district, text, makeDefault) {
    await ap.fill('[data-testid="address-name"]', name);
    await ap.fill('[data-testid="address-phone"]', phone);
    if (district) await ap.selectOption('[data-testid="address-district"]', district);
    await ap.fill('[data-testid="address-text"]', text);
    if (makeDefault) await ap.check('[data-testid="address-form"] input[type="checkbox"]');
    await ap.click('[data-testid="address-save"]');
  }
  await ap.click('[data-testid="address-add"]');
  await fillAddress("Nadia Home", "12345", "", "x", false);
  await ap.waitForTimeout(600);
  const addrErrs = await ap.$$eval('[data-testid="address-form"] [id$="-error"]', (els) => els.map((e) => e.textContent));
  rec("invalid address: phone, district and address errors shown", addrErrs.length >= 3, addrErrs.join(" | ").slice(0, 120));
  await fillAddress("Nadia Home", "01711000001", "Dhaka", "House 10, Road 3, Mirpur DOHS", false);
  await ap.waitForSelector('[data-testid="address-card"]');
  await ap.click('[data-testid="address-add"]');
  await fillAddress("Nadia Office", "01911000003", "Chattogram", "Level 4, Agrabad C/A, Chattogram", true);
  await ap.waitForFunction(() => document.querySelectorAll('[data-testid="address-card"]').length === 2);
  let addrs = (await inPage(ap, "GET", "/account/addresses")).json;
  rec("second address saved as the new default (only one default)", addrs.filter((x) => x.is_default).length === 1 && addrs.find((x) => x.is_default).recipient_name === "Nadia Office");
  await ap.reload({ waitUntil: "networkidle" });
  rec("addresses persist after refresh", (await ap.$$('[data-testid="address-card"]')).length === 2);
  await ap.locator('[data-testid="address-card"]', { hasText: "Nadia Home" }).locator("text=Edit").click();
  await ap.fill('[data-testid="address-text"]', "House 11, Road 3, Mirpur DOHS (edited)");
  await ap.click('[data-testid="address-save"]');
  await ap.waitForTimeout(800);
  addrs = (await inPage(ap, "GET", "/account/addresses")).json;
  rec("address edited", addrs.some((x) => /edited/.test(x.address)));
  const officeId = addrs.find((x) => x.is_default).id, homeId = addrs.find((x) => !x.is_default).id;
  const idorPut = await inPage(b.page, "PUT", `/account/addresses/${officeId}`, { recipient_name: "Hijack", phone: "01811000002", district: "Dhaka", address: "Somewhere else entirely" });
  const idorDel = await inPage(b.page, "DELETE", `/account/addresses/${officeId}`);
  rec("another account cannot edit or delete this address (404)", idorPut.status === 404 && idorDel.status === 404);
  // checkout uses the default saved address
  await ap.goto(`${BASE}/product/${Q.slug}`, { waitUntil: "networkidle" });
  await ap.click('[data-testid="add-to-cart-button"]');
  await ap.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
  await ap.waitForSelector('[data-testid="checkout-signed-in"]');
  const pre = await ap.evaluate(() => ({ phone: document.querySelector('[data-testid="checkout-phone"]')?.value,
    district: document.querySelector('[data-testid="checkout-district"]')?.textContent, addr: document.querySelector('[data-testid="checkout-address"]')?.value }));
  rec("signed-in checkout prefilled from the default address", /Chattogram/.test(pre.district) && /Agrabad/.test(pre.addr), JSON.stringify(pre).slice(0, 120));
  rec("saved-address picker offered at checkout", !!(await ap.$('[data-testid="checkout-saved-address"]')));
  await ap.screenshot({ path: path.join(OUT, "checkout-signed-in-1280.png"), fullPage: true });
  await ap.goto(`${BASE}/account/addresses`, { waitUntil: "networkidle" });
  ap.on("dialog", (d) => d.accept().catch(() => {}));
  await ap.locator('[data-testid="address-card"]', { hasText: "Nadia Office" }).locator("text=Delete").click();
  await ap.waitForFunction(() => document.querySelectorAll('[data-testid="address-card"]').length === 1);
  addrs = (await inPage(ap, "GET", "/account/addresses")).json;
  rec("deleting the default promotes the remaining address to default", addrs.length === 1 && addrs[0].id === homeId && addrs[0].is_default);

  // ================= 3. Profile and email change ===================================
  await ap.goto(`${BASE}/account/profile`, { waitUntil: "networkidle" });
  await ap.fill('[data-testid="profile-phone"]', "0171");
  await ap.click('[data-testid="profile-save"]');
  await ap.waitForTimeout(600);
  rec("profile: invalid phone rejected with a field error", /valid Bangladesh mobile/.test(await ap.textContent('[data-testid="account-profile"]')));
  await ap.fill('[data-testid="profile-name"]', "Nadia T. Rahman");
  await ap.fill('[data-testid="profile-phone"]', "01711000009");
  await ap.click('[data-testid="profile-save"]');
  await ap.waitForTimeout(800);
  const me = (await inPage(ap, "GET", "/account/me")).json;
  rec("profile name and phone saved (normalised)", me.full_name === "Nadia T. Rahman" && me.phone === "+8801711000009");
  const NEW_EMAIL = `nadia.new.${RUN}@example.test`;
  await ap.fill('input[type="email"]', NEW_EMAIL);
  await ap.fill('[data-testid="account-profile"] input[type="password"]', "not the password at all");
  await ap.click("text=Send confirmation link");
  await ap.waitForTimeout(800);
  rec("email change with a wrong password is refused", /current password is not correct/.test(await ap.textContent('[data-testid="account-profile"]')) && !lastLink("/confirm-email", NEW_EMAIL));
  await ap.fill('input[type="email"]', NEW_EMAIL);
  await ap.fill('[data-testid="account-profile"] input[type="password"]', A.password);
  await ap.click("text=Send confirmation link");
  await ap.waitForTimeout(1000);
  const changeLink = lastLink("/confirm-email", NEW_EMAIL);
  rec("email change: confirmation link sent to the NEW address only; email unchanged until confirmed",
      !!changeLink && (await inPage(ap, "GET", "/account/me")).json.email === A.email);
  await ap.goto(changeLink, { waitUntil: "networkidle" });
  await ap.waitForTimeout(1200);
  rec("email change confirmed; all sessions signed out", /has been updated/.test(await ap.textContent('[data-testid="confirm-email-page"]')) &&
      (await inPage(ap, "GET", "/account/me")).status === 401);
  await uiLogin(ap, A.email, A.password);
  await ap.waitForTimeout(1200);
  rec("old email no longer signs in", /Invalid email or password/.test(await ap.textContent('[data-testid="login-status"]').catch(() => "")));
  resetLimits();
  await uiLogin(ap, NEW_EMAIL, A.password);
  await ap.waitForURL(/\/account$/, { timeout: 15000 });
  rec("new email signs in", true);
  A.email = NEW_EMAIL;

  // ================= 4. Password change, deletion request ==========================
  const second = await browser.newContext();
  const sp = await second.newPage();
  await uiLogin(sp, A.email, A.password);
  await sp.waitForURL(/\/account$/, { timeout: 15000 });
  await ap.goto(`${BASE}/account/security`, { waitUntil: "networkidle" });
  await ap.fill('[data-testid="pw-current"]', "wrong current password");
  await ap.fill('[data-testid="pw-new"]', "another quite long passphrase");
  await ap.fill('[data-testid="pw-confirm"]', "another quite long passphrase");
  await ap.click('[data-testid="pw-submit"]');
  await ap.waitForTimeout(800);
  rec("password change: wrong current password refused", /current password is not correct/.test(await ap.textContent('[data-testid="account-security"]')));
  await ap.fill('[data-testid="pw-current"]', A.password);
  await ap.fill('[data-testid="pw-new"]', "short");
  await ap.fill('[data-testid="pw-confirm"]', "short");
  await ap.click('[data-testid="pw-submit"]');
  await ap.waitForTimeout(800);
  rec("password change: weak password refused", /at least 12 characters/.test(await ap.textContent('[data-testid="account-security"]')));
  const NEWPW = PW();
  await ap.fill('[data-testid="pw-current"]', A.password);
  await ap.fill('[data-testid="pw-new"]', NEWPW);
  await ap.fill('[data-testid="pw-confirm"]', NEWPW);
  await ap.click('[data-testid="pw-submit"]');
  await ap.waitForTimeout(1200);
  A.password = NEWPW;
  rec("password changed: this device stays signed in, other device signed out",
      (await inPage(ap, "GET", "/account/me")).status === 200 && (await inPage(sp, "GET", "/account/me")).status === 401);
  rec("password-changed notice emailed", mails(A.email).some((m) => m.template === "password_changed"));
  await second.close();
  await ap.goto(`${BASE}/account/security`, { waitUntil: "networkidle" });
  await ap.evaluate(() => { window.prompt = () => "DELETE"; });
  await ap.click('[data-testid="delete-request"]');
  await ap.waitForTimeout(1000);
  rec("deletion request recorded and shown", /We received your deletion request/.test(await ap.textContent('[data-testid="account-security"]')));

  // ================= 5. Admin: Accounts (search, filter, suspend, reactivate) =========
  const { ctx: actx, page: adm } = await newPage(browser);
  await adm.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
  await adm.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
  await adm.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
  await adm.click('[data-testid="admin-login-submit"]');
  await adm.waitForURL(/\/admin\/?$/, { timeout: 20000 });
  await adm.goto(`${BASE}/admin/accounts`, { waitUntil: "networkidle" });
  await adm.fill('[data-testid="accounts-search"]', `nadia.new.${RUN}`);
  await adm.waitForTimeout(1200);
  let rows = await adm.$$eval('[data-testid="account-row"]', (r) => r.map((x) => x.textContent));
  rec("admin Accounts search finds exactly the customer", rows.length === 1 && rows[0].includes(A.email) && /deletion requested/.test(rows[0]));
  await adm.selectOption('[data-testid="accounts-method"]', "google");
  await adm.waitForTimeout(1000);
  rec("admin Accounts sign-in method filter (google -> none)", (await adm.$$('[data-testid="account-row"]')).length === 0);
  await adm.selectOption('[data-testid="accounts-method"]', "password");
  await adm.waitForSelector('[data-testid="account-row"]');
  await adm.click('[data-testid="account-row"] a');
  await adm.waitForSelector('[data-testid="admin-account-detail"]');
  const detailTxt = await adm.textContent('[data-testid="admin-account-detail"]');
  rec("account detail lists claimed orders, no hashes or tokens", detailTxt.includes(claimNum) && detailTxt.includes(mailOrder) && !/password_hash|token_hash|\$2b\$/.test(detailTxt));
  await adm.evaluate(() => { window.prompt = () => "QA suspension test"; });
  await adm.click('[data-testid="account-suspend"]');
  await adm.waitForSelector("text=Reactivate", { timeout: 10000 });
  rec("suspend: customer session ends immediately", (await inPage(ap, "GET", "/account/me")).status === 401);
  await uiLogin(ap, A.email, A.password);
  await ap.waitForTimeout(1000);
  rec("suspended account cannot sign in (clear message)", /not available/.test(await ap.textContent('[data-testid="login-status"]').catch(() => "")));
  const forgotSuspended = mails(A.email).length;
  await inPage(ap, "POST", "/customer/forgot-password", { email: A.email });
  rec("suspended account gets no reset email (same public answer)", mails(A.email).length === forgotSuspended);
  await adm.click("text=Reactivate");
  await adm.waitForSelector('[data-testid="account-suspend"]', { timeout: 10000 });
  resetLimits();
  await uiLogin(ap, A.email, A.password);
  await ap.waitForURL(/\/account$/, { timeout: 15000 });
  rec("reactivated account signs in again", true);
  const evs = (await api("GET", `/admin/customer-accounts/${(await inPage(ap, "GET", "/account/me")).json.id}`, { token: admin })).json;
  rec("suspension and reactivation recorded in the account's security events",
      JSON.stringify(evs).includes("suspended_by_admin") && JSON.stringify(evs).includes("reactivated"));

  // ================= 6. Promotions rules (server-side) ==============================
  const T = RUN.toUpperCase().slice(-4);
  const fixed = await promo(admin, { code: `FIX100${T}`, type: "fixed", value: 100, min_subtotal: 1000 });
  const low = await validate(Q.id, fixed.code, { phone: "01733000001" });
  rec("fixed ৳100 code below its minimum -> minimum message", low.valid === false && low.reason === "minimum" && /at least ৳1,000/.test(low.message), low.message);
  const highQty = Math.ceil(1000 / P.selling_price);
  const ok = await validate(P.id, fixed.code, { phone: "01733000001", qty: highQty });
  rec("fixed ৳100 code above its minimum -> exactly ৳100 off", ok.valid === true && ok.discount === 100, `${ok.discount}`);
  const capped = await promo(admin, { code: `PCT50${T}`, type: "percent", value: 50, max_percent_of_subtotal: 20, max_discount_bdt: 100000 });
  const cv = await validate(P.id, capped.code, { phone: "01733000001" });
  rec("percent code limited by maximum percent of subtotal", cv.valid && cv.discount === Math.floor(cv.eligible_subtotal * 0.2) && cv.discount < cv.eligible_subtotal * 0.5,
      `${cv.discount} of ${cv.eligible_subtotal}`);
  const tomorrow = new Date(Date.now() + 86400000).toISOString();
  const sched = await promo(admin, { code: `LATER${T}`, starts_at: tomorrow });
  rec("scheduled code -> not active yet", (await validate(P.id, sched.code, { phone: "01733000001" })).message === "This code isn't active yet.");
  const soon = await promo(admin, { code: `BRIEF${T}`, ends_at: new Date(Date.now() + 4000).toISOString() });
  rec("code valid before its end date", (await validate(P.id, soon.code, { phone: "01733000001" })).valid === true);
  await sleep(5000);
  rec("code after its end date -> expired", (await validate(P.id, soon.code, { phone: "01733000001" })).message === "This code has expired.");
  const pauseMe = await promo(admin, { code: `PAUSE${T}` });
  await api("POST", `/admin/promotions/${pauseMe.id}/pause`, { token: admin });
  rec("paused code -> not available", (await validate(P.id, pauseMe.code, { phone: "01733000001" })).message === "This code isn't available right now.");
  const draft = await promo(admin, { code: `DRAFT${T}` }, false);
  rec("draft code is unusable", (await validate(P.id, draft.code, { phone: "01733000001" })).message === "This code isn't valid.");
  const once = await promo(admin, { code: `ONCE${T}`, usage_limit_total: 1 });
  const o1 = await guestOrder(Q.id, { phone: "01733000002", coupon: once.code });
  const o2 = await guestOrder(Q.id, { phone: "01733000003", coupon: once.code });
  rec("total usage limit: first order succeeds, the next is refused", o1.status === 200 && o2.status === 400 && /usage limit/.test(o2.json.detail), o2.json?.detail);
  const first = await promo(admin, { code: `FIRST${T}`, first_order_only: true });
  rec("first-order-only refused for a phone with previous orders", (await validate(P.id, first.code, { phone: "01733000002" })).reason === "first_order");
  rec("first-order-only accepted for a new phone", (await validate(P.id, first.code, { phone: "01733000099" })).valid === true);
  const catCode = await promo(admin, { code: `CAT${T}`, eligible_category_slugs: [OTHER_CAT.category_slug] });
  rec("category-limited code does not apply to other categories",
      (await validate(P.id, catCode.code, { phone: "01733000001" })).reason === "not_applicable" &&
      (await validate(OTHER_CAT.id, catCode.code, { phone: "01733000001" })).valid === true);
  const vip = await promo(admin, { code: `VIP${T}`, customer_emails: [A.email] });
  rec("customer-specific code asks a guest to sign in", (await validate(P.id, vip.code, { phone: "01733000001" })).reason === "signin");
  rec("customer-specific code refused for another account", (await validate(P.id, vip.code, { page: b.page })).valid === false);
  rec("customer-specific code accepted for its owner", (await validate(P.id, vip.code, { page: ap })).valid === true);
  const actByAdmin = await api("POST", "/admin/promotions", { token: roleTok.admin, body: { code: `ROLE${T}`, name: "x", type: "percent", value: 5 } });
  rec("admin role can create a draft", actByAdmin.status === 200);
  rec("admin role cannot activate (super admin only)", (await api("POST", `/admin/promotions/${actByAdmin.json.id}/activate`, { token: roleTok.admin, body: { confirm: true } })).status === 403);
  rec("product manager cannot see promotions", (await api("GET", "/admin/promotions", { token: roleTok.product_manager })).status === 403);
  rec("order manager cannot see promotions", (await api("GET", "/admin/promotions", { token: roleTok.order_manager })).status === 403);
  rec("activation requires explicit confirmation", (await api("POST", `/admin/promotions/${actByAdmin.json.id}/activate`, { token: admin, body: {} })).status === 400);
  rec("active code cannot be edited until paused", (await api("PUT", `/admin/promotions/${once.id}`, { token: admin, body: { code: once.code, name: "x", type: "percent", value: 20 } })).status === 400);
  const wcfg = (await api("GET", "/admin/promotions/campaigns/welcome", { token: admin })).json;
  rec("welcome campaign still disabled; public endpoint promises nothing", wcfg.enabled === false && (await api("GET", "/promotions/welcome")).json.enabled === false);

  // restore a redemption through the UI after cancelling the order
  const onceNum = o1.json.order_number;
  await api("PUT", `/admin/orders/${onceNum}`, { token: admin, body: { order_status: "Cancelled" } });
  await adm.goto(`${BASE}/admin/promotions`, { waitUntil: "networkidle" });
  await adm.click(`[data-testid="promo-row-${once.code}"]`);
  await adm.waitForSelector('[data-testid="promotion-detail"]');
  await adm.evaluate(() => { window.prompt = () => "QA: order cancelled"; });
  await adm.click('[data-testid="promotion-detail"] >> text=Restore');
  await adm.waitForTimeout(1200);
  const afterRestore = (await api("GET", `/admin/promotions/${once.id}`, { token: admin })).json;
  rec("restore after cancellation gives the use back (UI)", afterRestore.remaining_uses === 1 && afterRestore.audit.some((x) => x.action === "redemption_restored"));
  await adm.screenshot({ path: path.join(OUT, "admin-promotion-detail-1280.png"), fullPage: true });

  // promotion form at mobile width
  const { ctx: mctx, page: mob } = await newPage(browser, 390);
  await mob.goto(`${BASE}/admin/login`, { waitUntil: "networkidle" });
  await mob.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
  await mob.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
  await mob.click('[data-testid="admin-login-submit"]');
  await mob.waitForURL(/\/admin\/?$/, { timeout: 20000 });
  await mob.goto(`${BASE}/admin/promotions`, { waitUntil: "networkidle" });
  await mob.click('[data-testid="promo-new"]');
  await mob.waitForSelector('[data-testid="promotion-form"]');
  rec("promotion form fits 390px", (await overflow(mob)) <= 1);
  await mob.screenshot({ path: path.join(OUT, "admin-promotion-form-390.png"), fullPage: true });
  await mctx.close();

  // ================= 7. Orders: status updates -> tracking + email ===================
  const trackPhone = "01744000001";
  const tracked = (await guestOrder(Q.id, { phone: trackPhone, email: `track.${RUN}@example.test` })).json.order_number;
  await adm.goto(`${BASE}/admin/orders/${tracked}`, { waitUntil: "networkidle" });
  await adm.selectOption('[data-testid="order-status-select"]', "Confirmed").catch(async () => {
    await adm.click('[data-testid="order-status-select"]'); await adm.click('[role="option"]:has-text("Confirmed")'); });
  await adm.fill('[data-testid="order-courier-name"]', "Pathao");
  await adm.fill('[data-testid="order-tracking-code"]', "PTH-TEST-1");
  await adm.click('[data-testid="order-save"]');
  await adm.waitForTimeout(1200);
  const ord = (await api("GET", `/admin/orders/${tracked}`, { token: admin })).json;
  rec("admin sets Confirmed + courier from the order page", ord.order_status === "Confirmed" && ord.courier_name === "Pathao" && ord.events.some((e) => e.status === "Confirmed" && e.actor));
  rec("customer status email sent once for Confirmed", mails(`track.${RUN}@example.test`).filter((m) => m.template === "order_status").length === 1);
  await api("PUT", `/admin/orders/${tracked}`, { token: admin, body: { order_status: "Confirmed" } });
  rec("saving the same status again sends no duplicate email", mails(`track.${RUN}@example.test`).filter((m) => m.template === "order_status").length === 1);
  rec("order manager can move it to Sent to Courier", (await api("PUT", `/admin/orders/${tracked}`, { token: roleTok.order_manager, body: { order_status: "Sent to Courier" } })).status === 200);
  rec("product manager cannot change orders", (await api("PUT", `/admin/orders/${tracked}`, { token: roleTok.product_manager, body: { order_status: "Delivered" } })).status === 403);
  rec("invalid status refused", (await api("PUT", `/admin/orders/${tracked}`, { token: admin, body: { order_status: "Teleported" } })).status === 400);
  const { ctx: tctx, page: tp } = await newPage(browser, 390);
  await tp.goto(`${BASE}/track-order`, { waitUntil: "networkidle" });
  await tp.fill('[data-testid="track-order-number"]', tracked);
  await tp.fill('[data-testid="track-phone"]', trackPhone);
  await tp.click('[data-testid="track-submit"]');
  await tp.waitForSelector(`[data-testid="track-timeline-${tracked}"]`, { timeout: 10000 });
  const tl = await tp.textContent(`[data-testid="track-timeline-${tracked}"]`);
  rec("tracking shows recorded Confirmed + Handed to courier with courier details", /Order confirmed - completed/.test(tl) && /Handed to courier/.test(tl) && /Pathao/.test(await tp.textContent("main")));
  await tp.screenshot({ path: path.join(OUT, "track-timeline-390.png"), fullPage: true });
  await tp.fill('[data-testid="track-phone"]', "01799999999");
  await tp.click('[data-testid="track-submit"]');
  await tp.waitForTimeout(1000);
  rec("tracking with the wrong phone reveals nothing", !(await tp.$(`[data-testid="track-timeline-${tracked}"]`)) || /couldn't find|No order/i.test(await tp.textContent("main")));
  await tctx.close();

  // ================= 8. Checkout integrity =========================================
  const badPhone = await api("POST", "/checkout", { body: orderBody(Q.id, { phone: "12345" }) });
  rec("checkout refuses an invalid Bangladesh phone", badPhone.status === 400 || badPhone.status === 422, `${badPhone.status}`);
  const tooMany = await api("POST", "/checkout", { body: orderBody(Q.id, { qty: 9999, phone: "01755000001" }) });
  rec("checkout refuses more than the available stock", tooMany.status === 400 && /left of|out of stock/.test(tooMany.json.detail), tooMany.json?.detail);
  const rid = `qa-${RUN}-retry`;
  const r1 = await api("POST", "/checkout", { body: orderBody(Q.id, { phone: "01755000002", rid }) });
  const r2 = await api("POST", "/checkout", { body: orderBody(Q.id, { phone: "01755000002", rid }) });
  rec("idempotent retry returns the same order, stock taken once",
      r1.json.order_number === r2.json.order_number && r2.json.duplicate === true && db(`inventory-logs ${r1.json.order_number}`) === 1);
  // double click on Place Order -> one order
  const { ctx: dctx, page: dp } = await newPage(browser);
  await dp.goto(`${BASE}/product/${Q.slug}`, { waitUntil: "networkidle" });
  await dp.click('[data-testid="add-to-cart-button"]');
  await dp.goto(`${BASE}/checkout`, { waitUntil: "networkidle" });
  await dp.fill('[data-testid="checkout-name"]', "Double Click");
  await dp.fill('[data-testid="checkout-phone"]', "01755000003");
  await dp.click('[data-testid="checkout-district"]');
  await dp.click('[role="option"]:has-text("Dhaka")');
  await dp.fill('[data-testid="checkout-address"]', "House 1, Road 1, Gulshan (test)");
  const before = (await api("GET", "/admin/orders?search=01755000003", { token: admin })).json.length;
  await dp.click('[data-testid="place-order-button"]', { clickCount: 2, delay: 20 }).catch(() => {});
  await dp.click('[data-testid="place-order-button"]').catch(() => {});
  await dp.waitForSelector('[data-testid="confirmation-order-number"]', { timeout: 20000 });
  await sleep(1000);
  const afterN = (await api("GET", "/admin/orders?search=01755000003", { token: admin })).json.length;
  rec("double-clicking Place Order creates exactly one order", afterN - before === 1, `${afterN - before}`);
  await dctx.close();

  // ================= 9. Logout and authentication isolation =========================
  const custCookieAdmin = await ap.evaluate(async () => (await fetch("/api/admin/orders", { credentials: "include" })).status);
  rec("customer session cannot use the admin API", custCookieAdmin === 401);
  const adminOnCustomer = await api("GET", "/account/me", { token: admin });
  rec("admin bearer token cannot use the customer API", adminOnCustomer.status === 401);
  await ap.goto(`${BASE}/account`, { waitUntil: "networkidle" });
  await ap.click('[data-testid="account-logout"]');
  await ap.waitForURL((u) => u.pathname === "/", { timeout: 10000 });
  rec("after logout the old session is rejected", (await inPage(ap, "GET", "/account/me")).status === 401);
  for (const r of ["/account", "/account/orders", "/account/addresses", "/account/profile", "/account/security", "/account/rewards"]) {
    await ap.goto(BASE + r, { waitUntil: "networkidle" });
    if (!/\/login\?next=/.test(ap.url())) { rec(`signed-out ${r} redirects to login`, false, ap.url()); }
  }
  rec("every signed-out account page redirects to login with next", true);
  await adm.click('[data-testid="admin-logout"]').catch(() => {});
  await actx.close();
  await a.ctx.close(); await b.ctx.close();
  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify(results, null, 2));
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("FAIL  harness error —", e.message.split("\n")[0]); console.log(`\n${results.filter((r) => r.ok).length}/${results.length + 1} checks passed`); process.exit(1); });
