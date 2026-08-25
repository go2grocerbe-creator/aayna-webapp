# AAYNA Launch Business Settings Audit (L3)

Read-only audit. No setting, policy text, or code was changed in this pass.
Full settings collection (19 keys) was read directly from `aayna_dev` and
cross-checked against `GET /api/settings` — the public API exposes exactly
those 19 keys, nothing more. No admin credentials, secrets, API keys, or
storage credentials are present in the settings collection or its public
response.

## 1. Executive Summary

Delivery (COD, ৳80/৳130), order/status workflow, and policy copy are all in
solid, honest, launch-plausible shape — the policy text in particular is
already self-governed (its own file header documents that invented SLA/
exchange-window language was deliberately removed rather than replaced with
a guess). The real problems found are not "missing values" so much as
**two customer-facing surfaces that don't respect the placeholder gating
the rest of the app already uses correctly**:

- `Footer.jsx` renders the raw `whatsapp_number` ("+8801XXXXXXXXX") next to
  a plain phone icon, site-wide, on every page, with no `isPlaceholder()`
  check — unlike `WhatsAppFloat` and the PDP WhatsApp link, which both
  gate it correctly.
- `Contact.jsx` is worse: both its "WhatsApp" and "Call Us" cards render
  the same raw placeholder, ungated, and the WhatsApp card's `href` is
  actively broken — stripping non-digit characters from
  "+8801XXXXXXXXX" leaves only `"8801"` (every `X` is a letter, not a
  digit), producing `https://wa.me/8801`, a garbage link.

Separately, `cod_available` is a real, admin-editable settings field with a
working toggle in the Admin UI, but it is never read by Checkout.jsx or the
backend checkout endpoint — COD is unconditionally offered regardless of
this setting's value. Toggling it today would have no effect on what a
customer can select.

No email/SMS/WhatsApp sending code exists anywhere in this codebase — order
notification is a generic, currently-disabled webhook
(`ORDER_WEBHOOK_ENABLED=false`, empty URL in dev) that would need an
external automation to actually deliver anything. This directly matters
because the Privacy Policy states "We may contact you about your order via
phone, WhatsApp, or SMS" — a real capability claim I cannot verify is wired
up end-to-end.

## 2. Contact

| Field | Value | Status |
|---|---|---|
| `whatsapp_number` | `+8801XXXXXXXXX` | **PLACEHOLDER** — correctly gated in `WhatsAppFloat` and PDP; **NOT gated** in `Footer.jsx` or `Contact.jsx` (see §1) |
| `support_email` | `hello@aayna.xyz` | READY-looking (not placeholder-pattern) — founder should confirm this inbox is real and monitored before launch |
| Phone (separate from WhatsApp) | *not present* | **MISSING** — there is no distinct phone-number setting; `whatsapp_number` doubles as "Call Us" in Contact.jsx via a `tel:` link, which is itself the placeholder |
| Business address | *not present* | OPTIONAL — not referenced anywhere in the storefront (Footer, Contact, policies) |

## 3. Social

| Field | Value | Placeholder? | Exposed | Resolves |
|---|---|---|---|---|
| `instagram_handle` / `instagram_url` | `@shopaayna.bd` / `https://instagram.com/shopaayna.bd` | No | Footer, Contact | HTTP 200 |
| `facebook_url` | `https://facebook.com/AAYNA-Bangladesh` | No | Footer, Contact | HTTP 200 |
| `tiktok_url` | `https://tiktok.com/@shopaayna.bd` | No | Stored, admin-editable | HTTP 200 — **not currently rendered anywhere in the storefront** (no TikTok icon/link in Footer or Contact) |

Connection-level 200s only — I did not verify these are the founder's actual
owned accounts (out of scope for a code/config audit).

## 4. Delivery

| Field | Value | Status |
|---|---|---|
| Inside Dhaka | ৳80 (`delivery_charge_inside_dhaka`) | IMPLEMENTED, CURRENT DEV VALUE — this is a real settings value, not hardcoded, and Checkout.jsx/StaticPage.jsx both read it live so they can never drift apart. **Founder production approval required** — a dev-environment observation is not launch sign-off. |
| Outside Dhaka | ৳130 (`delivery_charge_outside_dhaka`) | Same as above — IMPLEMENTED, CURRENT DEV VALUE, approval required. |
| How calculated | `district === "Dhaka" ? inside : outside` (frontend preview) / `delivery_charge_for()` (backend, authoritative at order time) | Simple two-tier model, no per-district table beyond Dhaka/non-Dhaka |
| `free_delivery_threshold` | `0` | Stored but **never read anywhere** in backend or frontend code — dead setting, not in the Admin UI form either |
| Delivery-note behavior | Optional field, passed through to the order record, not otherwise validated | READY |
| Delivery Policy page | Live-injects the two charges from settings (never duplicated as static text) | READY, honest |

## 5. Payments

| Method | Status |
|---|---|
| COD | Enabled in Checkout, always selectable. `cod_available` setting exists, is admin-editable (toggle in Settings UI), but is **not read anywhere** in Checkout.jsx or backend checkout validation — inert. Founder must explicitly confirm COD-only is the intended launch configuration; this is not documented as an explicit decision anywhere in source. |
| bKash | Disabled — `bkash_number` is a placeholder (`01XXXXXXXXX`), `isPlaceholder()` correctly gates the Checkout radio option to "Not available yet." **NOT REQUIRED FOR COD-ONLY LAUNCH.** |
| Nagad | Same as bKash — placeholder, correctly gated, disabled. **NOT REQUIRED FOR COD-ONLY LAUNCH.** |

**Payment architecture safety (§16):** confirmed — a placeholder field alone
cannot make bKash/Nagad selectable; the `RadioGroupItem` is `disabled` and
styled inert whenever `isPlaceholder(manualNumber)` is true. No mutation
needed, no regression found.

## 6. Policies

| Policy | Route | Content status |
|---|---|---|
| Delivery Policy | `/delivery-policy` | Real, honest, settings-backed charges. No delivery-time promise (no "same-day"/"1-2 days"/etc. anywhere). |
| Return & Exchange | `/returns` | Explicitly states the full policy is "still being finalized" — this is honest but **is itself a launch decision**: ship with that language, or finalize the policy first? |
| Privacy Policy | `/privacy` | Contains the "phone, WhatsApp, or SMS" contact-method claim discussed in §1/§7 — capability not verifiably implemented end-to-end. |
| Terms & Conditions | `/terms` | Generic, defensible boilerplate (availability, pricing, cancellation, delivery responsibility). No unsupported commitments found. |

All four are settings-adjacent but content-hardcoded in
`frontend/src/data/staticPages.js` (not DB-backed) — editable only by a
developer, not through the Admin UI. The file's own header comment
documents that speculative SLA/exchange-window language was deliberately
removed during an earlier claim audit rather than replaced with an invented
figure — this is genuinely good governance already in place, not something
L3 needs to redo.

**§19 delivery-promise search:** zero hits for same-day / next-day / N-day
delivery windows / "guaranteed delivery" / "free delivery" anywhere in
policies, settings, or storefront copy.

**§20 return/exchange promise search:** the only written policy is the
"still being finalized" `/returns` page above — no separate marketing copy
elsewhere makes a stronger or conflicting claim (checked Home/PDP/Footer
copy already audited across D1-D6; none of it promises returns/exchange
terms).

## 7. Customer Communications

| Channel | Status |
|---|---|
| Email confirmation | **NOT IMPLEMENTED** — no email-sending code anywhere in the backend |
| SMS | **NOT IMPLEMENTED** — no SMS-sending code anywhere |
| WhatsApp (automated, outbound) | **NOT IMPLEMENTED** — no WhatsApp Business API integration; the customer-facing WhatsApp link is inbound-only (customer messages AAYNA), and is currently placeholder-gated off anyway |
| Admin notification | **CONDITIONAL / UNKNOWN for production** — `send_order_notification()` posts a clean, secret-free JSON payload (with ready-to-use `admin_message`/`customer_message` text) to `ORDER_WEBHOOK_URL` only if `ORDER_WEBHOOK_ENABLED=true`. In `aayna_dev`'s `.env` today: **disabled, no URL configured.** Whether a production deployment has this wired to a real automation (Make.com/n8n/etc., per the router-name/mode settings) is outside what this codebase can confirm. |

The only confirmation a customer actually receives today is the on-screen
Order Confirmation page (secure token URL, already audited in D6) — there
is no fallback channel unless the webhook is configured and connected to
something that actually messages the customer.

## 8. Order Operations

Status lifecycle (unchanged, `admin_routes.py ORDER_STATUSES`): **New →
Confirmed → Packed → Sent to Courier → Delivered**, plus terminal
**Cancelled** / **Returned**. Customer-facing labels already mapped
(`customerStatusLabel` in `format.js`) — e.g. "New" displays as "Order
received."

This is a real, admin-editable 7-state workflow (`PUT` on the order record
via the admin dashboard) — sufficient for manual, founder-run order
operations at launch: every state a small operation needs (received →
being prepared → handed to courier → done, with cancel/return as escapes)
is present. No missing states identified for initial manual ops.

## 9. Public Settings / Privacy

`GET /api/settings` returns exactly the 19 keys in `db.website_settings` —
verified 1:1 against a direct database read. **Zero leaks**: no
`ADMIN_PASSWORD`, `JWT_SECRET`, `MONGO_URL`, `OBJECT_STORAGE_*`,
`EMERGENT_LLM_KEY`, or `ORDER_WEBHOOK_SECRET` present in the settings
collection or the public response (those live in environment variables,
never in the DB-backed settings the public endpoint reads from).

**Admin editability**, per setting:

| Setting | Editable in Admin UI | Notes |
|---|---|---|
| `brand_name`, `tagline`, `announcement_bar_text` | Yes | |
| `whatsapp_number`, `support_email`, `bkash_number`, `nagad_number` | Yes | |
| `instagram_url`, `facebook_url`, `tiktok_url` | Yes | `instagram_handle` (the `@handle` display string) is **not** in the admin form — only the URL is |
| `delivery_charge_inside_dhaka`, `delivery_charge_outside_dhaka` | Yes | |
| `cod_available` | Yes (toggle present) | Inert — see §5 |
| `hero_headline`, `hero_subtitle`, `hero_image_url` | **No** | DB-backed, editable only via raw `PUT /api/admin/settings` API call, not the Settings form |
| `free_delivery_threshold`, `website_domain`, `currency` | **No** | Same as above — API-only, and also unused in code (dead settings) |

## 10. Founder Decisions Required

1. **Footer/Contact placeholder exposure** — the raw `+8801XXXXXXXXX` is
   currently visible to every visitor (Footer) and forms a broken WhatsApp
   link (Contact page), because those two components don't use the
   `isPlaceholder()` gate the rest of the app already has. This needs a
   presentation fix once real contact numbers exist, or an explicit
   decision to hide contact rows entirely until then — **not applied in
   this audit** (L3 is read-only).
2. **Production customer-facing phone/WhatsApp number** — none exists yet;
   confirm the real number before launch.
3. **Production support email** — confirm `hello@aayna.xyz` is real/
   monitored, or provide the real one.
4. **Confirm Dhaka delivery fee** (currently ৳80 in dev) and **outside-Dhaka
   fee** (currently ৳130) for production.
5. **COD-only launch: confirm.** No explicit "COD only for launch" decision
   exists in source — it's simply the only enabled method today. Also flag
   that `cod_available` doesn't actually gate anything currently.
6. **bKash / Nagad at launch: YES/NO?** Currently correctly disabled by
   placeholder numbers. If NO (recommended for initial launch), no action
   needed. If YES, real merchant numbers are required.
7. **Return & Exchange policy** — ship with the current honest "still being
   finalized" language, or finalize real terms before launch?
8. **Privacy Policy's contact-channel claim** ("phone, WhatsApp, or SMS")
   — confirm whether an order-notification automation is actually
   connected in production, or soften the claim to match what's actually
   implemented (webhook-only, no guaranteed customer-facing delivery
   channel today).
9. **TikTok** — link is stored and resolves, but isn't shown anywhere on
   the site. Add it to Footer/Contact, or leave unused?

## 11. Launch Blockers

**Must resolve before launch:**
- Footer/Contact ungated placeholder phone number + Contact page's broken
  WhatsApp link (§1, §10.1) — a real customer-facing bug, not just a
  missing value.
- Delivery fee founder sign-off (§4, §10.4) — currently only a dev
  observation, not an approved production value.
- COD-only confirmation (§10.5) — should be an explicit decision, not an
  accident of what happens to be enabled.

**Can remain disabled/deferred:**
- bKash / Nagad (placeholder-gated, safe as-is).
- TikTok link (stored, unused, no harm either way).
- `free_delivery_threshold` / `website_domain` (dead settings, no launch
  impact either way).
- `cod_available` toggle being inert (worth fixing eventually, not a
  launch blocker since COD works regardless).

## Production settings changed: NO
