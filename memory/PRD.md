# AAYNA — Product Requirements Document

## Original Problem Statement
Bangladesh-based women's accessories e-commerce website (brand: **AAYNA**, tagline "Reflect your everyday style."). Mobile-first, simple, fast, fully functional for real orders. Built in milestones from 3 client files: Master Prompt (requirements), Website Side Details (brand identity/colors/fonts/delivery/payment/SEO/operations), and an Excel template (first 10 products + 6 categories).

Hard constraints (Version 1): No customer login, no online payment gateway, no seller dashboard, no mobile app. All totals calculated on backend. Secrets in env vars only.

## Architecture
- **Frontend:** React 19 (CRA + CRACO), React Router 7, TanStack Query, Tailwind + shadcn/ui, sonner toasts. Cart in localStorage (guest, no login).
- **Backend:** FastAPI + Motor (MongoDB). All routes prefixed `/api`. Data seeded on startup.
- **Brand system:** Dusty Rose #9A4F5F, Cream #FFF8F2, Rose Mist #F7E7E9, Antique Gold #C6A15B, Espresso Charcoal #2F2623. Playfair Display (headings), Inter (body/UI), Noto Sans Bengali.
- **Product/category/hero images:** AAYNA-branded AI placeholders (replaceable later via admin). Excel image filenames kept as references.

## User Personas
- **Shopper (guest):** Browses, filters, adds to cart, checks out with COD/manual bKash/Nagad — no account. Tracks order by ID/phone.
- **Admin (future milestone):** Will manage products, orders, inventory, notifications, settings.

## Core Requirements (static)
- Guest browsing + guest checkout, backend-authoritative pricing, stock guard, BD phone validation, delivery charge by district (Dhaka 80 / outside 130), order snapshots, non-blocking Make.com notification, no PII leakage in public APIs.

## Implemented — Milestone 1 (2026-06-22)
- **DB / seed:** categories(6), products(10 from Excel), website_settings, + collections for orders, order_items(embedded), customers, inventory_logs, notification_logs, counters.
- **Public API:** `/settings`, `/categories`, `/categories/{slug}`, `/products` (filter/sort/search), `/products/{slug}` (+related), `/districts` (64), `/cart/validate`, `/checkout`, `/orders/{order_number}` (public-safe), `/track`.
- **Order flow:** validate fields + BD phone → stock check → recalc subtotal from DB → delivery by district → total → upsert customer → create order (status New, ORD-1001+) → reduce stock + inventory log → non-blocking webhook → return order number. Idempotent via `client_request_id`. cost_price/internal_notes never exposed; confirmation/track never leak phone/address.
- **Storefront pages:** Home (announcement, hero, categories, new arrivals, best sellers, trust badges, footer, floating WhatsApp), Shop (filter + sort + search), Category, Product Detail (gallery, qty, add/buy, WhatsApp inquiry, related, sticky mobile CTA), Cart, Checkout (COD/bKash/Nagad, district-based delivery), Order Confirmation, Track Order, Contact, and static Delivery/Returns/Privacy/Terms pages.
- **Verified:** 27/27 backend tests pass; all frontend critical flows pass (incl. refresh-no-duplicate-order).

## Known Notes
- WhatsApp/bKash/Nagad numbers are placeholders per client (to update later in settings).
- `MAKE_WEBHOOK_URL` is a placeholder — notifications log as "failed" but orders still save (by design).

## Implemented — Milestone 3D–3F (2026-06-25)
- **Router readiness:** `NOTIFICATION_ROUTER_NAME` (default `generic_webhook`) and `NOTIFICATION_ROUTER_MODE` (default `webhook`) env vars; both recorded in `notification_logs` + info log line. Webhook-only (no SDKs/SMS/email). 6 new backend tests.
- **SEO basics:** dependency-free `useSeo` hook (`src/lib/seo.js`) sets per-page `<title>`, meta description, OG/Twitter tags + canonical on every storefront page; cart/checkout/confirmation are `noindex`. Static `public/robots.txt` (disallows /admin, /cart, /checkout, /order-confirmation) and `public/sitemap.xml`.
- **Analytics:** `Analytics` component conditionally loads GA4 / Meta / TikTok pixels ONLY when `REACT_APP_GA4_ID` / `REACT_APP_META_PIXEL_ID` / `REACT_APP_TIKTOK_PIXEL_ID` are set, and NEVER on `/admin` routes. Env/config-based (no admin UI editing).
- **Launch checklist** added to README.
- **Verified:** 76/76 backend tests pass; SEO titles/meta verified live; robots.txt + sitemap.xml return 200.
- ⚠️ Before launch: replace placeholder domain `https://www.aayna.com.bd` in robots.txt & sitemap.xml.

## Backlog / Next Milestones
**P0 (Milestone 2 — Admin):** Admin auth (login), dashboard summary, orders management (status updates, courier tracking, resend notification), products CRUD + image upload, category management, inventory, customers, notification logs, homepage content + website settings editor.
**P1:** Real Make.com webhook + email/SMS notifications; editable static pages from admin; CSV export (orders/customers/products) + product CSV import.
**P2:** Product variants, free-delivery threshold logic, SEO meta/analytics pixels (GA/Meta/TikTok) wiring, maintenance mode.

## Next Action Items
- On client approval, begin Milestone 2 (Admin dashboard) — start with admin auth via integration_expert.
