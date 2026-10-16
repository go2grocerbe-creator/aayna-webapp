// AAYNA responsive UI audit — real browser (Playwright/Chromium), every major page
// across the production viewport matrix plus tablet/phone landscape.
//
// Usage (TEST backend only — DB_NAME must contain "test"; it logs into admin and
// pre-fills a cart via localStorage, it does NOT place orders):
//   BASE_URL=http://localhost:3000 API=http://localhost:8001/api \
//   ADMIN_EMAIL=... ADMIN_PASSWORD=... [CHROMIUM_PATH=...] [FULLPAGE_WIDTHS=320,375,768,1024,1440] \
//   node scripts/verify/responsive_audit.js <out-dir>
//
// Writes <out-dir>/audit.json (metrics per page x viewport), screenshots, and prints a summary.
// Thresholds follow docs/PRODUCTION_STANDARD.md: no horizontal overflow, ~44px touch targets
// (24px is the hard WCAG 2.2 AA floor), no clipped headings, sticky elements must not cover CTAs,
// visible keyboard focus.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = process.env.API || "http://localhost:8001/api";
const OUT = process.argv[2];
const FULL = (process.env.FULLPAGE_WIDTHS || "320,375,768,1024,1440").split(",").map(Number);
fs.mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  ...[320, 360, 375, 390, 430].map((w) => ({ w, h: w === 320 ? 568 : 844, touch: true, tag: `${w}` })),
  { w: 768, h: 1024, touch: true, tag: "768" }, { w: 820, h: 1180, touch: true, tag: "820" },
  { w: 1024, h: 1366, touch: true, tag: "1024" },
  ...[1280, 1440, 1920].map((w) => ({ w, h: w === 1920 ? 1080 : 900, touch: false, tag: `${w}` })),
  { w: 844, h: 390, touch: true, tag: "844x390-phone-landscape" },
  { w: 1024, h: 768, touch: true, tag: "1024x768-tablet-landscape" },
  { w: 1180, h: 820, touch: true, tag: "1180x820-tablet-landscape" },
];

async function setup() {
  const login = await fetch(`${API}/admin/login`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD }) }).then((r) => r.json());
  const products = await fetch(`${API}/products`).then((r) => r.json());
  const inStock = products.filter((p) => p.stock_quantity > 0 && ["earrings", "necklaces", "rings"].includes(p.category_slug));
  const pdp = inStock.find((p) => p.discount_price) || inStock[0];
  const cart = inStock.slice(0, 2).map((p) => ({
    product_id: p.id, slug: p.slug, name: p.product_name, image: p.images?.[0]?.image_url, sku: p.sku,
    selling_price: p.selling_price, discount_price: p.discount_price,
    unit_price: p.discount_price > 0 ? p.discount_price : p.selling_price, stock: p.stock_quantity, quantity: 1,
  }));
  const adminProducts = await fetch(`${API}/admin/products`, { headers: { Authorization: `Bearer ${login.token}` } }).then((r) => r.json());
  return { token: login.token, pdp, cart, adminProductId: adminProducts[0]?.id };
}

const PAGES = (s) => [
  { key: "home", path: "/" },
  { key: "shop", path: "/shop" },
  { key: "category", path: "/category/earrings" },
  { key: "product", path: `/product/${s.pdp.slug}` },
  { key: "cart", path: "/cart", cart: true },
  { key: "cart-empty", path: "/cart" },
  { key: "checkout", path: "/checkout", cart: true },
  { key: "track-order", path: "/track-order" },
  { key: "contact", path: "/contact" },
  { key: "policy", path: "/returns" },
  { key: "not-found", path: "/no-such-page" },
  { key: "admin-login", path: "/admin/login" },
  { key: "admin-dashboard", path: "/admin", admin: true },
  { key: "admin-products", path: "/admin/products", admin: true },
  { key: "admin-product-edit", path: `/admin/products/${s.adminProductId}`, admin: true },
  { key: "admin-orders", path: "/admin/orders", admin: true },
  { key: "admin-inventory", path: "/admin/inventory", admin: true },
];

async function measure(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const visible = (el) => {
      const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && cs.opacity !== "0";
    };
    const clippedByAncestor = (el) => { let a = el.parentElement; while (a) { const o = getComputedStyle(a).overflowX; if (o === "hidden" || o === "clip" || o === "auto" || o === "scroll") return true; a = a.parentElement; } return false; };
    const label = (el) => (el.getAttribute("data-testid") || el.getAttribute("aria-label") || el.innerText || el.getAttribute("placeholder") || el.name || el.tagName).toString().replace(/\s+/g, " ").trim().slice(0, 40);

    // overflow
    const offenders = [];
    for (const el of document.body.querySelectorAll("*")) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && getComputedStyle(el).position !== "fixed" && !el.closest('[aria-hidden="true"]') && !clippedByAncestor(el)) offenders.push(`${el.tagName.toLowerCase()}[${label(el)}]`);
    }
    // touch targets (exclude links inline inside running text paragraphs)
    const interactive = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role="button"], [role="combobox"], [role="switch"], [role="checkbox"]')]
      .filter(visible).filter((el) => !el.closest('[aria-hidden="true"]'));
    const small44 = [], small24 = [];
    for (const el of interactive) {
      if (el.tagName === "A" && el.closest("p") && el.closest("p").innerText.length > el.innerText.length + 20) continue;
      // control wrapped in a larger clickable <label> (e.g. payment radio cards): the label is the target
      const lab = el.closest("label") || (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`));
      if (lab && lab.getBoundingClientRect().height >= 44) continue;
      const r = el.getBoundingClientRect();
      const h = Math.round(r.height), w = Math.round(r.width);
      if (h < 24 || w < 24) small24.push(`${label(el)} ${w}x${h}`);
      else if (h < 44) small44.push(`${label(el)} ${w}x${h}`);
    }
    // unnamed controls
    const unnamed = interactive.filter((el) => {
      if (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA") {
        const id = el.id; return !(el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || (id && document.querySelector(`label[for="${id}"]`)) || el.closest("label"));
      }
      if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return false;
      return !(el.closest("label") || el.innerText.trim() || el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.getAttribute("title") || el.querySelector("img[alt]:not([alt=''])"));
    }).map(label);
    // tiny text
    const tiny = new Set();
    for (const el of document.body.querySelectorAll("p, span, a, button, label, li, small, div")) {
      if (!visible(el) || el.closest('[aria-hidden="true"]')) continue;
      const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
      if (!own) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < 12) tiny.add(`${fs}px "${el.innerText.replace(/\s+/g, " ").trim().slice(0, 30)}"`);
    }
    // headings clipped
    const clippedHeadings = [...document.querySelectorAll("h1, h2")].filter(visible).filter((h) => {
      const r = h.getBoundingClientRect(); return r.right > vw + 1 || r.left < -1 || h.scrollWidth > h.clientWidth + 2;
    }).map((h) => h.innerText.slice(0, 40));
    // fixed / sticky
    const fixed = [...document.body.querySelectorAll("*")].filter((el) => visible(el) && ["fixed", "sticky"].includes(getComputedStyle(el).position))
      .map((el) => { const r = el.getBoundingClientRect(); return { what: `${el.tagName.toLowerCase()}[${label(el)}]`, pos: getComputedStyle(el).position, top: Math.round(r.top), h: Math.round(r.height), w: Math.round(r.width), share: +(r.height * Math.min(r.width, vw) / (vw * vh)).toFixed(3) }; });
    // images
    const imgs = [...document.images].filter(visible);
    const broken = imgs.filter((i) => i.complete && i.naturalWidth === 0).map((i) => (i.currentSrc || i.src).split("/")[2]);
    const distorted = imgs.filter((i) => i.naturalWidth > 0).filter((i) => {
      const fit = getComputedStyle(i).objectFit; if (fit === "cover" || fit === "contain") return false;
      const r = i.getBoundingClientRect(); return Math.abs(r.width / r.height - i.naturalWidth / i.naturalHeight) > 0.05;
    }).length;
    // first-viewport density: share of first viewport (below header) covered by visible text/media
    const header = document.querySelector("header"); const hb = header ? header.getBoundingClientRect().bottom : 0;
    const blocks = [...document.querySelectorAll("main h1, main h2, main h3, main p, main img, main button, main a, main input, main label, main [role=img]")].filter(visible)
      .map((el) => el.getBoundingClientRect()).filter((r) => r.top < vh && r.bottom > hb);
    const firstContentTop = blocks.length ? Math.round(Math.min(...blocks.map((r) => r.top)) - hb) : null;
    const h1 = document.querySelector("h1"); const h1r = h1?.getBoundingClientRect();
    return {
      vw, vh, scrollW: document.documentElement.scrollWidth, docH: document.documentElement.scrollHeight,
      overflow: document.documentElement.scrollWidth > vw, offenders: [...new Set(offenders)].slice(0, 8),
      small24: [...new Set(small24)], small44: [...new Set(small44)], unnamed: [...new Set(unnamed)],
      tiny: [...tiny].slice(0, 12), clippedHeadings, fixed, broken: broken.length, brokenHosts: [...new Set(broken)], distorted,
      firstContentTop, headerBottom: Math.round(hb), h1: h1?.innerText.replace(/\s+/g, " ").slice(0, 60), h1Top: h1r ? Math.round(h1r.top) : null,
    };
  });
}

async function focusCheck(page, n = 14) {
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  const missing = [];
  for (let i = 0; i < n; i++) {
    await page.keyboard.press("Tab");
    await page.waitForTimeout(350); // let focus transitions (e.g. transition-all 300ms) settle
    const info = await page.evaluate(() => {
      const el = document.activeElement; if (!el || el === document.body) return null;
      const cs = getComputedStyle(el);
      const ring = (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== "none");
      return { ring, what: (el.getAttribute("data-testid") || el.getAttribute("aria-label") || el.innerText || el.tagName).replace(/\s+/g, " ").slice(0, 30) };
    });
    if (info && !info.ring) missing.push(info.what);
  }
  return [...new Set(missing)];
}

(async () => {
  const s = await setup();
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const rows = [];
  for (const vp of VIEWPORTS) {
    for (const pg of PAGES(s)) {
      const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, hasTouch: vp.touch, isMobile: vp.touch && vp.w < 1100 });
      await ctx.addInitScript(({ cart, token, admin, useCart }) => {
        try {
          localStorage.setItem("aayna_cart", JSON.stringify(useCart ? cart : []));
          if (admin) localStorage.setItem("aayna_admin_token", token); else localStorage.removeItem("aayna_admin_token");
        } catch {}
      }, { cart: s.cart, token: s.token, admin: !!pg.admin, useCart: !!pg.cart });
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
      page.on("console", (m) => { if (m.type() === "error" && !/ERR_TUNNEL|Failed to load resource/.test(m.text())) errors.push(m.text().slice(0, 160)); });
      await page.goto(BASE + pg.path, { waitUntil: "networkidle" }).catch(() => {});
      await page.waitForTimeout(500);
      const m = await measure(page);
      m.errors = errors;
      if (!vp.touch) m.focusMissing = await focusCheck(page);
      const shotBase = `${OUT}/${pg.key}__${vp.tag}`;
      await page.screenshot({ path: `${shotBase}__fold.png` });
      if (FULL.includes(vp.w) && /^\d+$/.test(vp.tag)) await page.screenshot({ path: `${shotBase}__full.png`, fullPage: true });
      rows.push({ page: pg.key, path: pg.path, vp: vp.tag, ...m });
      await ctx.close();
    }
    process.stdout.write(`${vp.tag} `);
  }
  await browser.close();
  fs.writeFileSync(`${OUT}/audit.json`, JSON.stringify(rows, null, 2));
  // summary
  const sum = (f) => rows.filter(f).map((r) => `${r.page}@${r.vp}`);
  console.log("\n\nOVERFLOW:", sum((r) => r.overflow).join(" ") || "none");
  console.log("CLIPPED HEADINGS:", sum((r) => r.clippedHeadings.length).join(" ") || "none");
  console.log("JS ERRORS:", sum((r) => r.errors.length).join(" ") || "none");
  const agg = (k) => { const m = {}; for (const r of rows) for (const x of r[k] || []) { const key = `${r.page}: ${x.replace(/ \d+x\d+$/, "")}`; m[key] = (m[key] || 0) + 1; } return Object.entries(m).sort((a, b) => b[1] - a[1]); };
  for (const k of ["small24", "small44", "unnamed", "tiny", "focusMissing"]) {
    const a = agg(k); console.log(`\n${k.toUpperCase()} (${a.length} distinct)`); a.slice(0, 60).forEach(([x, n]) => console.log(`  ${n}x  ${x}`));
  }
  console.log("\nBROKEN IMAGES (blocked hosts):", [...new Set(rows.flatMap((r) => r.brokenHosts))].join(", ") || "none", " total:", rows.reduce((a, r) => a + r.broken, 0));
  console.log("DISTORTED IMAGES:", rows.reduce((a, r) => a + r.distorted, 0));
})();
