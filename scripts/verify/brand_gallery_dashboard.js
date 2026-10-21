// LOCAL ONLY (isolated test DB via localhost). 21 Oct 2026 kit checks at 390/768/1280:
// approved logo (header, mobile menu, footer, admin login/sidebar), Coral Blue CTA, approved contacts
// + Vellora parent link, no bKash/Nagad, dashboard counts for 3 New + 1 Confirmed + 1 Packed, gallery
// cover reorder reaching the storefront, and a stale save getting 409.
// Usage: BASE_URL=http://localhost:3000 API=http://localhost:8001/api ADMIN_EMAIL=... ADMIN_PASSWORD=...
//        DB_CMD="python dbtool.py" node scripts/verify/brand_gallery_dashboard.js <outdir>
const { chromium } = require("playwright");
const fs = require("fs");
const { execSync } = require("child_process");
const BASE = process.env.BASE_URL, API = process.env.API, OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
let pass = 0, fail = 0;
const ok = (c, m, extra = "") => { if (c) { pass++; console.log("PASS  " + m); } else { fail++; console.log("FAIL  " + m + (extra ? "  — " + extra : "")); } };
const CORAL_BLUE = "rgb(57, 127, 140)";

(async () => {
  const login = await fetch(API + "/admin/login", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD }) }).then((r) => r.json());
  const token = login.access_token || login.token;
  const H = { Authorization: "Bearer " + token, "Content-Type": "application/json" };
  const products = await fetch(API + "/admin/products", { headers: H }).then((r) => r.json());
  const ring = products.find((p) => p.sku === "AYN-RNG-CLS-GLD" && p.status === "active");
  ok(!!ring, "real catalogue loaded (Classic Statement Ring active)");

  // dashboard fixture: exactly 3 New, 1 Confirmed, 1 Packed
  if (process.env.DB_CMD) execSync(`${process.env.DB_CMD} dashboard_fixture`, { stdio: "inherit" });
  const dash = await fetch(API + "/admin/dashboard", { headers: H }).then((r) => r.json());
  ok(dash.new_orders === 3 && dash.confirmed_orders === 1 && dash.packed_orders === 1 && dash.total_orders === 5,
     "dashboard API: New 3, Confirmed 1, Packed 1, total 5", JSON.stringify([dash.new_orders, dash.confirmed_orders, dash.packed_orders, dash.total_orders]));

  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  for (const w of [390, 768, 1280]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
    const page = await ctx.newPage();
    const errs = []; page.on("pageerror", (e) => errs.push(String(e)));
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    const hdr = await page.getByTestId("header-logo").evaluate((el) => ({ w: el.naturalWidth, src: el.currentSrc, alt: el.alt, h: el.getBoundingClientRect().height }));
    ok(hdr.w > 0 && /\/brand\/aayna-logo-(180|360|720)\.png$/.test(hdr.src) && hdr.alt === "AAYNA", `[${w}] header shows the approved logo`, JSON.stringify(hdr));
    const foot = await page.getByTestId("site-footer").evaluate((el) => ({ text: el.innerText, logo: el.querySelector('[data-testid="footer-logo"]')?.naturalWidth || 0,
      parent: el.querySelector('[data-testid="footer-parent-company"]')?.getAttribute("href") }));
    ok(foot.logo > 0, `[${w}] footer shows the golden logo`);
    ok(foot.text.includes("+880 1348-243169") && foot.text.includes("contact@shopaayna.com"), `[${w}] footer has approved phone + email`);
    ok(foot.parent === "https://vellora.com.bd" && foot.text.includes("A concern of Vellora Mercantile International"), `[${w}] footer parent-company line links to vellora.com.bd`);
    ok(!/bkash|nagad|shopaayna\.bd@gmail|hello@aayna|XXXX/i.test(foot.text), `[${w}] footer has no bKash/Nagad/old/placeholder contact`);
    const fav = await page.evaluate(() => [...document.querySelectorAll('link[rel~="icon"],link[rel="apple-touch-icon"]')].map((l) => l.getAttribute("href")));
    ok(fav.some((h) => h.endsWith("favicon.ico")) && fav.some((h) => h.endsWith("apple-touch-icon.png")) && !fav.some((h) => h.endsWith(".svg")), `[${w}] favicons are the approved files`, fav.join(","));
    await page.screenshot({ path: `${OUT}/home-${w}.png`, fullPage: false });
    await page.getByTestId("site-footer").screenshot({ path: `${OUT}/footer-${w}.png` });
    if (w === 390) {
      await page.getByTestId("mobile-menu-button").click();
      const mlogo = await page.getByTestId("mobile-menu-logo").locator("img").evaluate((el) => el.naturalWidth);
      ok(mlogo > 0, "[390] mobile menu shows the approved logo");
      await page.screenshot({ path: `${OUT}/mobile-menu-390.png` });
      await page.keyboard.press("Escape");
    }
    // product page CTA colour + contrast
    await page.goto(`${BASE}/product/${ring.slug}`, { waitUntil: "networkidle" });
    const cta = page.locator("button", { hasText: /add to (cart|bag)/i }).first();
    const bg = await cta.evaluate((el) => getComputedStyle(el).backgroundColor);
    ok(bg === CORAL_BLUE, `[${w}] Add to cart uses Coral Blue #397F8C`, bg);
    const cssHasOld = await page.evaluate(async () => { const t = await Promise.all([...document.styleSheets].map((s) => { try { return [...s.cssRules].map((r) => r.cssText).join(""); } catch { return ""; } })); return /224,\s*109,\s*83|e06d53/i.test(t.join("")); });
    ok(!cssHasOld, `[${w}] no Warm Coral left in the loaded CSS`);
    await page.screenshot({ path: `${OUT}/product-${w}.png`, fullPage: false });
    // contact page
    await page.goto(`${BASE}/contact`, { waitUntil: "networkidle" });
    const ct = await page.locator("main").innerText();
    ok(ct.includes("+880 1348-243169") && ct.includes("contact@shopaayna.com") && ct.includes("orders@shopaayna.com") && !/whatsapp/i.test(ct.split("Follow")[0]),
       `[${w}] contact page: phone + aliases, no WhatsApp without a real number`);
    // checkout payment options: COD only
    ok(errs.length === 0, `[${w}] no page errors`, errs.join(" | "));
    await ctx.close();
  }

  // admin: login page logo, sidebar logo, dashboard cards, gallery cover reorder
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + "/admin/login", { waitUntil: "networkidle" });
  ok((await page.getByTestId("admin-login-logo").evaluate((el) => el.naturalWidth)) > 0, "admin login shows the approved logo");
  await page.screenshot({ path: `${OUT}/admin-login-1280.png` });
  await page.fill('[data-testid="admin-login-email"]', process.env.ADMIN_EMAIL);
  await page.fill('[data-testid="admin-login-password"]', process.env.ADMIN_PASSWORD);
  await page.click('[data-testid="admin-login-submit"]');
  await page.waitForURL(/\/admin(\/)?$/);
  await page.getByTestId("dash-card-packed_orders").waitFor();
  const card = async (k) => (await page.getByTestId(`dash-card-${k}`).innerText()).match(/\d+/)?.[0];
  ok((await card("new_orders")) === "3" && (await card("confirmed_orders")) === "1" && (await card("packed_orders")) === "1" && (await card("with_courier_orders")) === "0",
     "dashboard cards: New 3, Confirmed 1, Packed 1, With courier 0");
  ok((await page.getByTestId("admin-sidebar-logo").first().evaluate((el) => el.naturalWidth)) > 0, "admin sidebar shows the approved logo");
  await page.screenshot({ path: `${OUT}/admin-dashboard-1280.png`, fullPage: true });
  await page.getByTestId("dash-card-confirmed_orders").click();
  await page.waitForURL(/status=Confirmed/);
  ok((await page.getByTestId("order-status-filter").inputValue()) === "Confirmed", "Confirmed card opens the Orders list filtered to Confirmed");

  await page.goto(`${BASE}/admin/products/${ring.id}`, { waitUntil: "networkidle" });
  await page.getByTestId("gallery-manager").waitFor();
  const before = await page.getByTestId("gallery-item-0").locator("img").getAttribute("src");
  const third = await page.getByTestId("gallery-item-2").locator("img").getAttribute("src");
  await page.getByTestId("gallery-cover-2").click();
  ok((await page.getByTestId("gallery-item-0").locator("img").getAttribute("src")) === third, "Set cover moves photo 3 to the front (unsaved)");
  await page.getByTestId("gallery-save").click();
  await page.getByText("Photo order saved").waitFor();
  const g = await fetch(`${API}/admin/products/${ring.id}/gallery`, { headers: H }).then((r) => r.json());
  ok(g.revision >= 1 && g.cover === third && before !== third, "saved: revision increased and cover is the chosen photo");
  ok(!!(await page.getByTestId("gallery-uploads-off").innerText()).match(/R2/), "upload area says uploads need R2 storage (no fake upload)");
  await page.getByTestId("gallery-manager").screenshot({ path: `${OUT}/admin-gallery-1280.png` });
  const stale = await fetch(`${API}/admin/products/${ring.id}/gallery/order`, { method: "PUT", headers: H,
    body: JSON.stringify({ expected_revision: g.revision - 1, ordered_ids: g.images.map((i) => i.id) }) });
  ok(stale.status === 409, "stale revision save is refused with 409", String(stale.status));
  // storefront cover follows the saved order: card + product page main image
  const shop = await browser.newPage({ viewport: { width: 390, height: 900 } });
  await shop.goto(`${BASE}/category/rings`, { waitUntil: "networkidle" });
  const cardImg = await shop.locator(`a[href="/product/${ring.slug}"] img`).first().getAttribute("src");
  ok(cardImg === third, "catalogue card shows the new cover", cardImg);
  await shop.goto(`${BASE}/product/${ring.slug}`, { waitUntil: "networkidle" });
  ok((await shop.getByTestId("product-main-image").getAttribute("src")) === third, "product page main image is the new cover");
  await shop.screenshot({ path: `${OUT}/product-cover-390.png` });
  await browser.close();
  console.log(`\n${pass}/${pass + fail} checks passed`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); console.log(`${pass}/${pass + fail + 1} checks passed`); process.exit(1); });
