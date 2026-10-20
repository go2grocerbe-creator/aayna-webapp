// Usage: BASE_URL=http://localhost:3000 API=http://localhost:8001/api ADMIN_EMAIL=... ADMIN_PASSWORD=... node scripts/verify/product_copy_responsive.js <outdir> <copy.json>
// copy.json = {SKU: {short_description, full_description, highlights, seo_title, seo_description}}
// LOCAL ONLY (aayna_pytest via localhost): apply the 10-SKU copy through the admin route, then
// check product pages + /returns at 390/768/1280: no sideways scroll, readable description,
// single-brand title, JSON-LD without ratings/returns/shipping/material, no 7-day text.
const { chromium } = require("playwright");
const fs = require("fs");
const BASE = process.env.BASE_URL, API = process.env.API, OUT = process.argv[2];
const PAY = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
fs.mkdirSync(OUT, { recursive: true });
let pass = 0, fail = 0; const ok = (c, m) => { if (c) pass++; else { fail++; console.log("FAIL " + m); } };
(async () => {
  const login = await fetch(API + "/admin/login", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD }) }).then(r => r.json());
  const H = { Authorization: "Bearer " + (login.access_token || login.token), "Content-Type": "application/json" };
  const list = await fetch(API + "/admin/products", { headers: H }).then(r => r.json());
  const items = Array.isArray(list) ? list : (list.items || list.products || []);
  const slugs = {};
  for (const [sku, body] of Object.entries(PAY)) {
    const p = items.find(x => x.sku === sku && x.status === "active");
    ok(!!p, `${sku} present locally`); if (!p) continue;
    slugs[sku] = p.slug;
    const r = await fetch(API + "/admin/products/" + p.id, { method: "PUT", headers: H, body: JSON.stringify(body) });
    ok(r.status === 200, `${sku} PUT ${r.status}`);
    const h = await fetch(API + "/admin/products/" + p.id + "/content-history", { headers: H }).then(r => r.json());
    ok(h.length === 1, `${sku} history entries ${h.length}`);
  }
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  for (const w of [390, 768, 1280]) {
    const page = await browser.newPage({ viewport: { width: w, height: 900 } });
    const errs = []; page.on("pageerror", e => errs.push(String(e)));
    for (const [sku, slug] of Object.entries(slugs)) {
      await page.goto(`${BASE}/product/${slug}`, { waitUntil: "networkidle" });
      await page.waitForSelector("h1");
      const d = await page.evaluate((exp) => {
        const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => JSON.parse(s.textContent));
        const p = ld.find(x => x["@type"] === "Product") || {};
        const t = document.body.textContent;
        const shortEl = [...document.querySelectorAll("p")].find(e => e.textContent.trim() === exp.short);
        return { title: document.title, overflow: document.documentElement.scrollWidth - window.innerWidth,
          shortVisible: !!shortEl && shortEl.getBoundingClientRect().width > 0,
          shortFont: shortEl ? parseFloat(getComputedStyle(shortEl).fontSize) : 0,
          full: t.includes(exp.full.slice(0, 40)), ldBad: ["aggregateRating", "review", "hasMerchantReturnPolicy", "shippingDetails", "material"].filter(k => k in p || k in (p.offers || {})),
          ldDesc: p.description, meta: (document.querySelector("meta[name=description]") || {}).content, bad: (t.match(/7 days|7-day|seven days|\| AAYNA \| AAYNA/i) || [null])[0] };
      }, { short: PAY[sku].short_description, full: PAY[sku].full_description });
      ok(d.title === PAY[sku].seo_title, `[${w}] ${sku} title "${d.title}"`);
      ok(d.overflow <= 0, `[${w}] ${sku} sideways scroll ${d.overflow}px`);
      ok(d.shortVisible && d.shortFont >= 14, `[${w}] ${sku} short description visible (font ${d.shortFont}px)`);
      ok(d.full, `[${w}] ${sku} full description in page`);
      ok(d.ldBad.length === 0, `[${w}] ${sku} JSON-LD extra keys ${d.ldBad}`);
      ok(d.meta === PAY[sku].seo_description && d.ldDesc === PAY[sku].seo_description, `[${w}] ${sku} meta/JSON-LD description`);
      ok(!d.bad, `[${w}] ${sku} forbidden text ${d.bad}`);
      if (sku === "AYN-CUF-CRS-GLD" || sku === "AYN-EAR-FLR-SLV") await page.screenshot({ path: `${OUT}/${sku}-${w}.png`, fullPage: true });
    }
    await page.goto(`${BASE}/returns`, { waitUntil: "networkidle" });
    const r = await page.evaluate(() => ({ t: document.body.textContent, o: document.documentElement.scrollWidth - window.innerWidth }));
    ok(!/7 days|7-day|seven days/i.test(r.t) && r.t.includes("We do not currently offer a fixed exchange window"), `[${w}] /returns wording`);
    ok(r.o <= 0, `[${w}] /returns sideways scroll ${r.o}px`);
    await page.screenshot({ path: `${OUT}/returns-${w}.png`, fullPage: true });
    ok(errs.length === 0, `[${w}] page errors: ${errs.join(" | ")}`);
    await page.close();
  }
  await browser.close();
  console.log(`${pass}/${pass + fail} checks passed`);
})();
