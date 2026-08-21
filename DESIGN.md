# AAYNA — DESIGN.md

**DESIGN.md is the current authoritative digital experience/design source for AAYNA.** Older `design_guidelines.json` (Milestone-1 dusty-rose scaffold spec) is historical and must not override this file. Where the two disagree, this file wins.

This document is research + synthesis only. **No application code was changed while producing it.** It exists so a coding agent (Claude/Codex) can implement the next redesign phase without re-researching the three references below.

---

## Vision

AAYNA is not "another jewelry ecommerce template." It is a small, real, Bangladesh-born accessories business (currently ~10-16 SKUs across earrings/necklaces/rings/bracelets/hair-accessories/gift-sets) that wants its website to feel considered, editorial, and personal — while still converting real customers on real phones, on real Bangladesh mobile networks, buying real BDT-priced items with Cash on Delivery.

The founder's rejection of the current build is specific: it reads as generic/AI-templated. The fix is not more decoration. It's a **structural, narrative, and interaction** rethink — how sections relate to each other, how the visitor's own choices shape what they see next, and how the brand's own meaning (আয়না — mirror) becomes a mechanism, not just a metaphor in copy.

## The Digital Mirror

AAYNA means mirror. The site should behave like one: it does not create the visitor's taste, it **reveals and reflects it back**, a little more clearly with every choice they make. Concretely, this means:

- A short, optional, first-visit moment where the visitor indicates what they're drawn to (grounded in AAYNA's *real* product categories — see Personalization Model).
- The homepage and shop quietly reorder/highlight around that choice for the rest of the session.
- The reflection is always **visible and reversible** — the visitor can see what's shaping their view and clear it in one tap. Never invisible, never "AI knows you."
- Skipping the mirror moment costs nothing — the full catalogue is one tap away regardless.

This is a session/browser-local mechanism (`localStorage`), not a login, not a recommendation model, not third-party tracking. It must degrade to a perfectly normal ecommerce site with zero personalization for any visitor who skips or has JS/storage disabled.

## Brand Foundation

Source of truth: AAYNA Brand Book 2026 (`E:\Obsidian_Second_Brain\KJ OS Template\03 Projects\AAYNA\06 Tofail Files\AAYNA - Brand Book.html`, read in full for this and prior work in this project). Already implemented in code as of the `redesign/brand-book-v1` branch (Milestones 1-2, Visual QA Fix Sprint) — this document does not re-litigate the palette, it *uses* it.

- Colors (research-defined by the Brand Book): Deep Burgundy `#5A0E1A`, Slate Blue `#1A365D`, Warm Coral `#E06D53`, plus proposed supporting neutrals Mirror Ivory `#F8F3EC` and Muted Gold `#C9A66B`.
- Usage principle (Brand Book, verbatim intent): *Burgundy anchors. Ivory breathes. Blue sharpens. Coral activates. Gold finishes.*
- Primary line: **"Reflect Your Aura."** Bangla: আপনার আভাকে প্রতিফলিত করুন। AAYNA = mirror / আয়না.
- Voice: confident and poised, artistic and graceful, intimately familiar. Never a discount-page voice, never fake urgency, never unverified product claims (CLAUDE.md governs this project-wide and is unchanged by this document).
- Typography direction (Brand Book-proposed, already implemented): Playfair Display (display/headings) + DM Sans (body/UI), Noto Sans Bengali for Bangla script.
- **No approved final logo exists.** Continue the restrained text wordmark already in place (`Header.jsx`/`Footer.jsx`, marked `FOUNDER ASSET REQUIRED — FINAL LOGO`). This document does not change that.

## Research Sources

Three reference experiences were studied for **structural and interaction principles only** — never for literal copy, imagery, or trademarks. Full write-ups (with more evidence and citations) are kept in `.design-research/*.md` (gitignored, this session's working notes, not part of the shipped design system).

| Reference | URL | Role |
|---|---|---|
| A — Prounis Jewelry | https://www.prounisjewelry.com/ | Storytelling / world-building / editorial rhythm |
| B — Mignon Faget | https://www.mignonfaget.com/ | Commerce rhythm / curated shopping / story-inside-shopping |
| C — Pandora "Create a Custom Charm Bracelet" | https://us.pandora.net/en/create-a-custom-charm-bracelet/ | Participation / guided choice interaction model only (not visual design) |

Evidence was gathered with the Firecrawl CLI (`firecrawl scrape`, `branding`+`images`+`markdown`+`links` formats) against homepage + one collection/PDP-equivalent page per site (Pandora: the builder page only, since AAYNA doesn't need a PDP-equivalent reference for a configurator it won't build). No third-party screenshots, images, or scraped assets were committed to this repository; raw evidence lived only in `.firecrawl/` and `.design-research/` (both gitignored) for the duration of this research session.

## Reference Lessons

### From Prounis (dominant: world-building)
- **Tease-then-deliver**: introduce a themed micro-collection as a single atmospheric image early on the homepage (no price, no grid), then deliver its real shoppable grid later on the same page. Story and commerce are the *same* collection at two different moments, not two different modules.
- **Typographic restraint**: let imagery and whitespace carry visual weight; headline type doesn't need to shout to feel premium.
- **Story vs. fact separation on PDP**: a short poetic paragraph and a plain factual materials line are different UI moments, not one merged paragraph.
- **Named curated collections as first-class navigation**, not just a filter.
- Reject: the ancient-artifact/archaeological concept itself, ultra-slow single-product-at-position-6 pacing (wrong for AAYNA's mobile/Instagram-driven, lower-price-point traffic), "Enquire instead of price" (AAYNA is in-stock retail, not one-of-a-kind antiques).

### From Mignon Faget (dominant: commerce rhythm)
- **One data structure serves both story and shop filter**: a named collection is simultaneously a narrative device and the actual category/tag filter. AAYNA's existing `category` and `tags` fields can carry this without new schema.
- **Cheap personalization-flavored labeling** ("curated for you," "recommended for you") can be genuinely rule-based and still read as tailored.
- **Shipping/trust micro-copy placed immediately next to Add to Cart**, not lower on the page — AAYNA already does this (Milestone 2); keep it.
- **Real stock-count urgency** ("Only 6 left!") is legitimate *only* when wired to the actual `stock_quantity` field, never fabricated.
- Reject: financing widgets (irrelevant to AAYNA's COD/bKash/Nagad payment methods), fake "returning to the vault" scarcity framing, mega-menu-scale taxonomy (AAYNA has ~10-16 SKUs, not hundreds), physical-gallery modules, stacked multi-message promo bars (conflicts with AAYNA's single-line, fact-only announcement bar), any bundle-discount mechanic not yet founder-approved.

### From Pandora (dominant: personalization, interaction model only)
- The "custom bracelet builder" is **not a 3D configurator** — it's a 4-step guided *browse* journey where each step is a category filter wearing an emotional label ("Add Charms to Tell Your Story," not "Charms"), all steps visible and non-linear, and every step is already a real, immediately-shoppable product grid.
- **The guided step and the product grid are the same UI element** — no separate wizard/modal is needed. This is the single most important transferable lesson for AAYNA: a personalization "step" can be nothing more than large, well-photographed choice tiles that set a filter and immediately show real AAYNA products, reusing the existing Shop/Category grid component.
- No gate, no lock, always shoppable — never delay a purchase behind "finish choosing first."
- Reject outright: building any product configurator, a multi-screen linear wizard with forward/back navigation, any login requirement, assuming Pandora-scale taxonomy depth.

## Experience Principles

1. **World before catalogue, but not at conversion's expense.** The visitor should feel they entered something considered — but a real product must be reachable within the first two homepage sections (hero, then the Digital Mirror choice tiles / first product row), not buried behind five editorial screens.
2. **Reflection is structural, not decorative.** The mirror motif is expressed through *content responding to choice*, not through literal chrome/glass UI everywhere.
3. **Restraint over noise.** One CTA color (coral) reserved for the one real action per screen. One narrow palette moment per section (Brand Book's "don't use all five colors at equal strength").
4. **Honesty over hype.** No claim, no urgency device, no "AI knows you" language that isn't literally true of the (deterministic, local, non-AI) mechanism actually running.
5. **Small catalogue, treated with respect, not padded.** Don't fake scale (no 24-collection mega-menu); make the real ~6 categories and handful of curated "Edits" feel intentional.
6. **Mobile is the primary medium, not a breakpoint.** Every principle above must survive being described at 375px width before it's considered valid.

## Personalization Model

### Grounded in AAYNA's real product schema (`backend/server.py` `PUBLIC_PRODUCT_FIELDS`, verified directly, not assumed)

Public product fields actually available today: `product_name`, `category_name`, `category_slug`, `selling_price`, `discount_price`, `images`, `short_description`, `full_description`, `material`, `color`, `size`, `weight`, `status`, `stock_quantity`, `is_featured`, `is_best_seller`, `is_new_arrival`, `tags`.

**AVAILABLE NOW** (reliable, always populated, safe to build personalization on today):
- `category_slug` / `category_name` — 6 real categories: Earrings, Necklaces, Rings, Bracelets, Hair Accessories, Gift Sets. This is the *only* field guaranteed consistently populated and structurally clean across every SKU.
- `is_new_arrival`, `is_best_seller`, `is_featured` — booleans, already used by the existing `/api/products?new_arrival=true` / `best_seller=true` query params (see `Home.jsx`).
- `stock_quantity` — real inventory count, usable for genuine (non-fabricated) low-stock messaging à la Mignon Faget, *only* below a real low threshold.
- Locally-tracked session signals requiring no backend change: categories/products viewed this session, products added to cart, which Digital-Mirror tile (if any) the visitor picked. All storable in a single `localStorage` key, all clearable in one action.

**REQUIRES FUTURE PRODUCT TAGGING** (do not build a preference picker on these until they exist):
- `tags` is free-text and inconsistently applied per SKU today (e.g. `"New Arrival, Gift Friendly, Pearl, Gold Tone, Everyday Wear"` on one product, a different vocabulary on the next). It is **not** currently a controlled vocabulary. A mood/occasion preference picker ("Everyday" / "Statement" / "Gifting") is only honest once every SKU carries a consistent tag from a fixed, admin-enforced list. Flag this to the founder/admin workflow before building it — do not invent a taxonomy the data can't back up.
- `color` is free-text ("Gold and white," "Rose pink and gold," "Silver") — not a clean "metal tone" facet yet. A normalized `metal_tone` enum (Gold / Silver / Rose / Mixed) would need either a backend migration or a disciplined admin-entry convention. Until then, do not offer a "pick your metal tone" personalization tile.
- Occasion/styling-context tagging (e.g. "office," "festive," "daily") does not exist in the schema at all today.

### The MVP taxonomy (what to actually build first)

Because only `category_slug` is reliably clean today, **the first-visit Digital Mirror choice is category-based, not a mood taxonomy** — this directly reuses Pandora's core lesson (the choice tile *is* the filter, not a separate wizard) and Mignon Faget's lesson (one data structure serves both story and filter). Do not default to "Minimal / Romantic / Bold / Classic" — that taxonomy has no backing in AAYNA's schema and was explicitly flagged against in the brief.

Proposed first-visit prompt (framing, not literal final copy — align final wording with whoever owns brand copy):

> "What are you drawn to today?" — 3-4 large image tiles, each a real AAYNA category (e.g. Earrings, Necklaces, Rings — pick the 3-4 with actual stock, hide empty categories exactly as the storefront already does elsewhere), plus a clearly equal-weight **"Show me everything"** tile that dismisses the moment entirely.

Selecting a tile does two things simultaneously: (1) sets a local preference, (2) *is itself navigation* — it can literally route to `/category/:slug` or filter the homepage's next product section, exactly like Pandora's step tiles. There is no submit button, no multi-step form.

## First-Visit Journey

1. Visitor lands on `/`. Hero renders as normal (Entry/Mirror Moment, below).
2. Immediately below the hero: the Digital Mirror invitation (Personal Choice) — one screen's worth of content, no scroll-jacking, no modal takeover. It is a normal homepage section, not an interstitial.
3. Visitor taps a category tile **or** "Show me everything" **or** simply scrolls past without interacting.
4. If a tile was tapped: preference is written to `localStorage` (see below), and the page's next section ("Your Edit") renders product content sourced from that category. A small, honest label marks this ("Because you're drawn to Earrings" or similar — never "Our AI picked this for you").
5. If skipped/scrolled past: no preference is stored; the homepage falls back to its existing non-personalized order (New Arrivals next, as already built).

## Returning Journey

- On any later page load in the same browser, a stored preference is read from `localStorage` and applied the same way — "Your Edit" reappears pre-filled, no re-asking.
- A visible, low-friction **"Not feeling this? Reset"** control sits near any personalized module — one tap clears `localStorage` and reverts to the default experience immediately (no confirmation dialog needed; this is not a destructive/irreversible action).
- No account, no server-side profile, no cross-device sync. If the visitor clears cookies/storage or switches devices, they simply see the first-visit journey again — this is a feature (transparency), not a bug, and must not be described to the visitor as a loss of "their" data.
- Never use language implying the site "remembers you" psychologically ("we know you love gold") — use transparent, poetic-but-honest framing ("Picking up where you left off" / "Still drawn to Earrings?").

## Design Tokens

All values below are **already implemented** in `frontend/tailwind.config.js` and `frontend/src/index.css` on `redesign/brand-book-v1` — this section documents them as the system of record, it does not propose new ones.

### Colors (semantic roles → Brand Book hex)

| Role | Token / class | Hex |
|---|---|---|
| brand-anchor | `aayna-burgundy` | `#5A0E1A` |
| brand-anchor (deep) | `aayna-burgundy-dark` | `#3B0811` |
| action (CTA) | `aayna-coral` | `#E06D53` |
| action hover | `aayna-coral-dark` | `#C85A42` |
| informational-accent | `aayna-blue` | `#1A365D` |
| background-primary | `aayna-cream` (Mirror Ivory) | `#F8F3EC` |
| background-secondary / small accent | `aayna-mist` | `#F4E8EA` |
| surface (cards) | white | `#FFFFFF` |
| text-primary | `aayna-charcoal` | `#211A1C` |
| text-secondary | `aayna-taupe` | `#796D70` |
| border | `aayna-beige` | `#EAD9DA` |
| premium-accent (finishing only) | `aayna-gold` | `#C9A66B` |
| success | Tailwind `green-700` (existing usage, e.g. in-stock text) | — |
| warning / low-stock | Tailwind `amber-700`-class range (not yet standardized — pick one on first use, then reuse) | — |
| error | Tailwind `red-700` (existing usage, e.g. out-of-stock, cancelled status) | — |

**Usage rule (Brand Book, enforced by the Visual QA Fix Sprint already done on this branch): Ivory is the dominant page surface. Burgundy is for anchors (nav, footer, headings, section dividers) — never every card. Coral is reserved for the one real action per screen — never decoration. Blue is sparing (one editorial/informational accent per page at most). Gold never becomes a large background.** Do not re-litigate this in implementation; it's already correct in the current codebase — preserve it.

## Typography

| Role | Family | Notes |
|---|---|---|
| Display / editorial title | Playfair Display, 500-700 | Hero headlines, section titles, product-story moments |
| H1 | Playfair Display 700 | `text-4xl md:text-5xl` (≈36px/48px) |
| H2 | Playfair Display 600-700 | `text-3xl md:text-4xl` (≈30px/36px) |
| H3 | Playfair Display 600 | `text-xl md:text-2xl` |
| Body | DM Sans 400 | 16px base, `text-sm md:text-base` for secondary copy |
| Caption / label | DM Sans 500-600, uppercase, tracked | `text-[11px]` to `text-xs`, `tracking-[0.15em]`-`[0.2em]` — already the established kicker-label pattern |
| Navigation | DM Sans 500 | `text-sm` |
| Price | DM Sans 700, `aayna-burgundy` | Already established |
| Bengali | Noto Sans Bengali | Used sparingly for cultural/editorial moments (e.g. the existing "আয়না" hero-fallback watermark), never as the primary reading language of commerce UI |

Responsive scale: mobile sizes are the base Tailwind class, desktop is the `md:` variant one or two steps up — this pattern is already consistent across the codebase; continue it rather than introducing a new scale.

## Layout & Spatial System

**Spacing**
- Base unit: 4px (Tailwind default `spacing` scale) — unchanged.
- Section vertical rhythm: `py-14 md:py-20` — already the established standard across Home/Shop/Category/PDP; reuse for every new section rather than inventing new paddings.
- Content width: `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8` for standard commerce content; `max-w-2xl`/`max-w-3xl` for narrow reading content (Track Order, static policy pages, order confirmation).
- Editorial/full-bleed width: full viewport width, content constrained only where text sits inside (see the existing 3-panel duotone editorial section in `Home.jsx` for the pattern).
- Product grid gaps: `gap-4 md:gap-6`, `grid-cols-2 md:grid-cols-3 lg:grid-cols-4` — unchanged, already correct for a small catalogue at all breakpoints.
- Card padding: `p-3 md:p-4` (product cards), `p-5 md:p-6` (content cards e.g. checkout/cart panels).

**Shape**
- Border radius: **near-zero throughout** — `rounded-sm` on buttons/inputs/interactive controls, no radius on images/cards/panels, `rounded-full` reserved *only* for genuinely circular elements (icon badges, avatar-style accent circles, the WhatsApp float, cart-count pill). Do not introduce `rounded-lg`/`rounded-xl` "soft SaaS card" styling anywhere — this was an explicit anti-goal in the Visual QA Fix Sprint and must stay that way.
- Borders: `border border-aayna-beige` is the standard card/panel border.
- Shadows: minimal — `hover:shadow-md` only on interactive product cards; no ambient drop-shadows on static panels. Prounis/Mignon Faget both favor flat, print-like surfaces over soft shadow depth; AAYNA should too.
- Image treatment: `object-cover`, `aspect-square` for product thumbnails, graceful `ProductImage` fallback component for anything missing (already built, `frontend/src/components/ProductImage.jsx` — reuse it for any new product imagery surface, do not reinvent).

**Grid & narrative devices**
- Standard CSS Grid/Flexbox via Tailwind, no CSS Grid framework beyond what's already in use. Asymmetric editorial layouts (per Prounis) should be achieved with `md:grid-cols-2`/`md:grid-cols-3` combined with `order-*` utilities (already used in the existing hero for mobile image/text reordering) — not a new layout system.
- **Asymmetric moments**: reserve for editorial/story sections only (the "tease" panel, the "Your Edit" introduction, the mirror-choice section) — commerce sections (Shop grid, Cart, Checkout) stay symmetric/predictable, because a small-catalogue mobile shopper needs speed and clarity more than novelty there.
- **Vertical narrative markers**: small uppercase kicker labels (`text-aayna-burgundy text-xs font-bold tracking-[0.2em] uppercase`) above section headings — already the established device (see `Home.jsx`'s Material Trust section, `Checkout.jsx`'s "Step 1/2/3/4" labels). Reuse this exact pattern as the "chapter label" device for Digital Mirror sections rather than inventing a new one.

## Imagery Direction

- **Do not use the "Product Demo Batch 1" photos anywhere, including internal dev/testing** — already investigated and confirmed to be raw supplier-sourcing snapshots with cost prices burned into the pixels, factory packaging, and personal backgrounds. Treat as `INTERNAL SOURCING REFERENCE ONLY`, never a public or dev-preview website asset. This finding stands; this document does not revisit it.
- Until real campaign/product photography exists, every imagery-dependent surface must have a graceful non-photo fallback (the existing `ProductImage` component, `HeroFallback`, and the Category-page banner fallback are the reference implementations — extend this pattern to any new imagery surface, never ship a component that assumes a photo will always be present).
- When real photography does arrive: favor true product-truth macro/detail shots (Prounis's "story vs. fact" split calls for at least one honest, unstyled detail shot per hero product) over generic "lifestyle stock" — but this is a founder/content decision, not something this document can execute.
- Editorial/duotone gradient panels (already built in `Home.jsx`) remain the correct placeholder device for "world-building" moments until real photography exists — they are honest (not pretending to be photos) and on-brand (use the burgundy/blue/coral palette restrained per-panel).

## Mirror Motif

Not literal chrome or mirror-shaped UI. The reflection metaphor is expressed structurally:

1. **Choice → reflected result.** The clearest expression: tapping a Digital Mirror tile visibly changes the next section of the page to reflect that choice. The mechanism *is* the metaphor.
2. **The concentric-ring + faint "আয়না" watermark device** (already built as `HeroFallback` in `Home.jsx`, sourced directly from the Brand Book's own cover/quote-block CSS pattern) is the one literal visual motif approved for reuse — as a quiet background texture in low-content/fallback states, never as a dominant graphic.
3. **Soft echo, not duplication**: where a "Your Edit" section reflects an earlier choice, a small recurring visual cue (e.g. the same category's accent tint, or a one-line "because you chose X" caption) is sufficient — do not render literal mirrored/duplicated product images or symmetric photo compositions as a design gimmick.
4. **Restraint is the sophistication.** A brand called "Mirror" does not need visual mirrors on every screen — one well-placed motif (the ring/watermark) plus a structural reflection mechanism (choice → tailored content) is sufficient and avoids the "gimmicky" trap the brief explicitly warns against.

## Motion System

Philosophy: **motion confirms, it never decorates.** Every animation must communicate state change (loading, selection, reveal) — none should run simply because motion looks nice.

| Moment | Treatment | Approx. duration/easing |
|---|---|---|
| Page entrance | None globally; individual above-fold elements may use the existing `animate-fade-up` keyframe once, on first paint only | 0.6s `cubic-bezier(0.16, 1, 0.3, 1)` (already defined in `index.css`) |
| Section reveal (scroll) | CSS-only, via `IntersectionObserver` toggling the existing `.animate-fade-up` class when a section enters viewport — no scroll-jacking, no pinning | Same fade-up timing, triggered once per element |
| Image hover (product card) | `scale-105` on the image only, container clips overflow (already implemented) | 300-500ms ease |
| Product card CTA reveal (quick-add) | Opacity + translate-y, already implemented | 300ms ease |
| Choice-tile selection (Digital Mirror) | Border/background color transition to the selected state (same visual language as the existing Checkout payment-method radio selection) — no scale/bounce | 150-200ms ease |
| "Your Edit" transition after a choice | Cross-fade the product grid content, not a slide/wipe — keep it calm | ~250ms opacity fade |
| Drawer/menu (mobile nav, cart) | Already implemented via Radix `Sheet`/slide transitions — reuse, do not replace | Existing Radix defaults |
| Loading | Existing skeleton pattern (`bg-aayna-beige/60` pulse blocks) — reuse for any new loading surface, do not introduce spinners for content loading (spinners remain fine for button/submit-in-progress states, as already used in Checkout/Track Order) | Existing `animate-pulse` |
| Reduced motion | Respect `prefers-reduced-motion: reduce` — disable the fade-up/scroll-reveal transitions (show content in final state immediately), keep only functional transitions (drawer open/close, focus states) | — |

Explicitly out of scope for this design system (mark as `LATER / EXPERIMENTAL` if ever revisited): WebGL, scroll-jacking/pinned sections, cursor-follow effects, parallax beyond a single subtle background-position shift, autoplay video/motion on the homepage.

## Navigation

No change to header architecture (explicitly preserved per the brief). The Digital Mirror does not add new top-level nav items — it lives as a homepage section, and its effect (a filtered "Your Edit" state) is surfaced through existing category links, not new menu structure. If a future "Edits" concept (à la Prounis/Mignon Faget named curated collections) is added, it should sit inside the existing Header category dropdown/mobile menu as additional entries — not a new nav pattern — sized to however many real curated collections actually exist (2-4, not 20+).

## Components

Documented as design/behavior intent; implementation should reuse existing components wherever named below rather than rebuilding.

- **Announcement** — unchanged (single-line, fact-only, burgundy anchor bar).
- **Header** — unchanged architecture; desktop nav, mobile Sheet drawer, search, cart badge all preserved as-is (explicitly protected in the brief).
- **Desktop navigation** — unchanged.
- **Mobile navigation** — unchanged (Radix `Sheet`, 44px touch targets already fixed in a prior pass).
- **Digital Mirror entry module** *(new)* — a homepage section: kicker label + short one-line invitation + 3-5 large square/portrait tiles (existing category tile visual language from the homepage "Shop by Category" module — reuse that component's visual treatment rather than inventing a new tile style) + one equal-weight "Show me everything" tile. No modal, no multi-step wizard.
- **Preference selector** — the tiles *are* the selector (per the Pandora lesson); no separate form control needed. Selected state uses the same border/tint pattern as Checkout's payment-method selection for consistency.
- **Personalization progress/state** — no progress bar. State is communicated only by: (a) which tile shows a subtle "selected" treatment if the visitor returns to this section, (b) a small "Because you're drawn to X — Reset" line above any personalized module.
- **Editorial chapter** — a full-bleed or near-full-bleed section with a kicker label, one short line of brand-voice copy, and either a real image or the duotone-panel fallback. Reuses the pattern already built in `Home.jsx`'s Material Trust and editorial-panel sections.
- **Collection feature** — a named collection tile (image or duotone fallback + name + one CTA) — the Prounis/Mignon Faget "Edit" device, sized to AAYNA's real inventory (do not build more tiles than there are genuinely coherent groupings of in-stock products).
- **Product card** — unchanged (`ProductCard.jsx`): image via `ProductImage`, category label, name, price + muted compare-at price, one restrained discount badge, coral quick-add.
- **Personalized product card context** *(new, minimal)* — no new card component; when a card appears inside a "Your Edit" row, the *section* it's in carries the personalization context (via the section's caption), not the card itself. Do not add a badge/ribbon to individual cards for "picked for you" — that reintroduces visual noise the Brand Book warns against.
- **Product grid** — unchanged (`ProductGrid.jsx`), including its existing loading skeleton and empty state.
- **Product carousel** — not currently used; if introduced for a "Your Edit" horizontal row on mobile, must be a lightweight CSS scroll-snap row (`overflow-x-auto`, `snap-x`), not a JS carousel library — matches the performance budget below.
- **PDP gallery** — unchanged structurally (`ProductDetail.jsx`); see PDP Story below for the *content* evolution.
- **PDP information** — unchanged fields (material/color/size/SKU/availability), extended per PDP Story below with a story/fact separation already partially present.
- **Add to Cart** — unchanged (coral CTA, established in Milestone 2).
- **Sticky mobile CTA** — unchanged, including its resolved WhatsApp-float collision fix from the Visual QA Fix Sprint.
- **Cart** — unchanged.
- **Checkout** — unchanged (guest checkout, 4-step Contact/Delivery/Payment/Summary structure, secure order creation flow — explicitly protected).
- **Trust/material panel** — unchanged (`TrustBadges.jsx`, Material Trust homepage section).
- **Story section** — see Editorial chapter above.
- **Footer** — unchanged.
- **WhatsApp/contact affordance** — unchanged, including the route-aware sticky-bar-clearing fix already shipped.
- **Empty state** — unchanged pattern (icon + message, established in `ProductGrid.jsx`/`TrackOrder.jsx`) — reuse for the Digital Mirror's "no matches for this preference" edge case if it ever occurs (e.g. a chosen category temporarily has zero stock — should not happen given category tiles are already filtered to `product_count > 0`, but design for it anyway).
- **Image fallback** — unchanged (`ProductImage.jsx`) — the system of record for all product imagery going forward.
- **Loading skeleton** — unchanged (`bg-aayna-beige/60` pulse pattern).

## Homepage Pattern

```
Announcement (unchanged)
↓
Header (unchanged)
↓
ENTRY / MIRROR MOMENT — hero: brand line, kicker "AAYNA · Bangladesh", HeroFallback or real
  campaign image, one coral CTA ("Shop Now") + one burgundy-outline secondary CTA
↓
PERSONAL CHOICE — Digital Mirror invitation: "What are you drawn to today?" + category tiles
  (only categories with product_count > 0, per the existing homepage filter) + "Show me
  everything" — this section doubles as the existing "Shop by Category" module, not an
  addition on top of it
↓
YOUR EDIT (if a preference is set) — a product row sourced from the chosen category, honestly
  captioned ("Because you're drawn to Earrings")
    — OR, if no preference set —
NEW ARRIVALS (existing default, unchanged query) — products must appear here regardless of
  personalization state, preserving the "products early" conversion requirement
↓
EDITORIAL WORLD — one atmospheric moment (existing duotone panel(s) or, once available, one
  real campaign image), Prounis-style tease of a named collection if one exists
↓
REFINED EDIT / BEST SELLERS — second product row; if a preference is set, weight toward it
  where the existing best-seller query allows (e.g. best-sellers filtered to the chosen
  category first, falling back to overall best-sellers) — "second reflection" per the brief
↓
MATERIAL / CRAFT STORY — existing Material Trust section, unchanged
↓
COLLECTION EXPLORATION — existing "Shop by Category" full grid / "View all" link to /shop
↓
TRUST / CARE / DELIVERY — existing TrustBadges section, unchanged
↓
CLOSING BRAND MOMENT — a short reprise of "Reflect Your Aura." before the footer (new, minimal
  — a single centered line, not a new heavy section)
↓
Footer (unchanged)
```

Rationale for placement: a real, already-shoppable product row appears by the **third** homepage section in the worst case (skip path) and the Digital Mirror choice itself doubles as the second section's function (it was already going to be "Shop by Category") — so no net new "screens before shopping" are added versus the current build.

## Your Edit Pattern

A reusable section (not a full page in the MVP) that can appear on the homepage and, later, as a dedicated `/your-edit` view if the founder wants a persistent destination:

```
Kicker: "Your Edit" (or honest equivalent)
↓
One-line caption naming the active preference + inline "Reset" control
↓
ProductGrid sourced by category_slug filter (reuses existing /api/products?category= query)
↓
(if grid is empty for any edge-case reason) existing empty-state pattern + a link to /shop
```

No new backend endpoint is required for the MVP — this is the existing `getProducts({ category })` call already used by `Shop.jsx`/`Category.jsx`, just invoked from the homepage with a locally-stored category value instead of a URL param.

## Shop/Category Pattern

Unchanged from the current implementation (`Shop.jsx`, `Category.jsx` — kicker labels, bordered filter panel, real category/sort params, Category page's editorial banner with graceful fallback). If the visitor has an active Digital Mirror preference, `Shop.jsx` may pre-select that category in its filter Select on first load of a session (a small, optional enhancement, not required for MVP) — never silently filter the grid without the visitor being able to see and clear the pre-selection.

## Product Detail Pattern

Structure unchanged (gallery → title/price → attributes → notes → description → related → sticky mobile CTA). The evolution from this document, informed by both Prounis and Mignon Faget, is **content organization within the existing "Description" area**, not new sections:

```
Hero product image (existing gallery, existing ProductImage fallback)
↓
Product identity: category label, name, price + muted compare-at, one discount badge
↓
"Why it belongs in the edit" — ONE short sentence of story-voice copy, sourced from the
  product's real short_description field — never invented, never generic filler if the field
  is empty (fall back to nothing, not a fabricated sentence)
↓
Product facts — existing attributes dl (material/color/size/SKU/availability), unchanged
↓
Styling context — OPTIONAL, only if full_description or tags genuinely support it (e.g. "Pairs
  well with earrings and rings" already exists in some seed copy) — never invent styling advice
  a SKU's data doesn't support
↓
Add to Cart / Buy Now (unchanged, coral/burgundy-outline pairing)
↓
Delivery/quality/returns notes (unchanged, already policy-safe per the Visual QA Fix Sprint)
↓
Full description (existing, unchanged)
↓
Related products — "You May Also Like" (existing); if a Digital Mirror preference is active
  and the current product isn't in that category, this is the natural place to *also* surface
  1-2 items from the preferred category — optional enhancement, not required for MVP
```

Never invent factual product claims (materials, certifications, guarantees) — this rule is unchanged from CLAUDE.md and every prior milestone on this project.

## Cart/Checkout Pattern

**Unchanged.** Explicitly protected in the brief (secure order creation, guest checkout, duplicate-click protection via `client_request_id`, the 4-step Contact/Delivery/Payment/Summary structure, the confirmation-token flow). No personalization or storytelling content should be added inside the checkout flow itself — checkout is the one place in the experience where speed and clarity outrank narrative, full stop.

## Mobile Rules

- Every pattern above must be authored mobile-first; the Digital Mirror tiles should be a horizontally-scrollable or 2-column grid at 360-430px, never requiring horizontal scroll of the *page*.
- Digital Mirror section height on mobile: roughly one viewport including its kicker/heading, not more — it must not push the first product content below the fold on a 375px-tall viewport.
- Sticky Add to Cart (PDP) and the WhatsApp float must never overlap — already fixed (`Layout.jsx` route-aware offset); any new sticky UI must follow the same pattern (a shared "reserved bottom zone" concept) rather than hardcoding positions per page.
- Touch targets: 44px minimum, already the established standard across Header/Cart/Checkout — apply identically to any new Digital Mirror tiles/controls.
- Text length: kicker labels and captions should fit on one line at 360px without wrapping awkwardly — test the actual copy at that width before shipping.
- Horizontal product rows (if used for "Your Edit") must use native CSS scroll-snap, not a JS carousel, to stay light on low-end Android devices common in the target market.

## Accessibility

- All interactive Digital Mirror tiles must be real `<button>`/`<a>` elements with visible focus states (matching existing focus-ring patterns already in the codebase's shadcn-derived components), never `<div onClick>`.
- The "Reset" control must have a clear accessible label ("Reset your preference"), not just an icon.
- Respect `prefers-reduced-motion` (see Motion System).
- Alt text on all product imagery via the existing `ProductImage` component (already preserves real alt text even in the fallback state) — never omit alt text on new imagery surfaces.
- Color contrast: burgundy-on-ivory and charcoal-on-ivory (the dominant text/background pairing) already meet WCAG AA; any new coral-on-white or gold-on-white text combination must be checked before shipping (gold in particular is a mid-tone and should stay reserved for icons/small accents, not body text, consistent with the existing "gold never becomes a large surface or primary text color" rule).

## Performance

Immersive does not mean heavy. Budget guidance for the Digital Mirror and any new editorial modules:

- No WebGL, no video backgrounds, no autoplay-heavy homepage content.
- Digital Mirror tile images: same lazy-loading, `object-cover`, `aspect-square`/`aspect-[4/3]` treatment as existing category tiles — no new image pipeline.
- Scroll-reveal via a single shared `IntersectionObserver` instance (not one observer per element) if implemented — CSS transition, not a JS animation library.
- No new client-side dependency (carousel library, animation library, 3D library) should be added for this phase — everything above is achievable with existing Tailwind/CSS/React patterns already in the codebase.
- `localStorage` read/write for the personalization preference is synchronous and trivial — no measurable performance cost; do not add a loading state for reading it.
- Preserve the existing bundle-size discipline (current production build ≈193KB gzip main bundle as of this branch) — any new module should be evaluated against that baseline before merging.

## Content & Voice

Governed by the Brand Book and CLAUDE.md, unchanged by this document:
- Confident, poised, artistic, intimately familiar — never a discount-page voice.
- No fabricated urgency, no fake personalization claims ("Our AI thinks..."), no unverified product/material claims.
- Digital Mirror copy should be poetic but **transparent** about what it is: a way to browse faster based on what you tap, not a psychological profile. If in doubt, name the mechanism honestly ("Picking up where you left off" is honest; "We know exactly what you love" is not).
- Bangla is used for cultural texture at specific brand moments (the mirror watermark, the tagline's Bangla rendering), not as a parallel UI language requirement for this phase.

## Do / Don't

**Do:**
- Reuse existing components (`ProductGrid`, `ProductImage`, `ProductCard`, the category-tile visual language, the kicker-label pattern, the Checkout step-label pattern) for every new Digital Mirror surface.
- Keep the Digital Mirror choice reversible, visible, and skippable at all times.
- Ground every personalization signal in a real, currently-populated schema field.
- Keep coral as the only CTA color, burgundy as the only anchor color, at every screen.
- Test every new pattern at 375px before 1440px.

**Don't:**
- Don't build a product configurator (that's Pandora's literal product, not a principle to copy).
- Don't invent a mood/style taxonomy the product data can't back up yet.
- Don't add a login requirement anywhere in this phase.
- Don't add WebGL, scroll-jacking, or autoplay video.
- Don't let "world-building" push the first real product below the second homepage section.
- Don't use Product Demo Batch 1 photos anywhere, ever, including internal previews.
- Don't touch Cart/Checkout/order-security architecture — it is explicitly out of scope and already correct.
- Don't invent delivery timelines, exchange windows, or other business-policy claims — that remains a founder decision, unchanged from prior milestones on this project.

## Implementation Guidance

Suggested build order for whichever agent implements this next, sized to keep each step reviewable and revertible (matches this project's established loop-engineering pattern of inspect → plan → implement → build → test → commit):

1. **Digital Mirror data layer**: a small `usePreference()` hook wrapping `localStorage` (get/set/clear a single `category_slug` string + timestamp) — no backend change.
2. **Digital Mirror section component**: build as a replacement for (not an addition to) the homepage's existing "Shop by Category" section, reusing its tile visual language.
3. **"Your Edit" section**: a thin wrapper around the existing `ProductGrid` + `getProducts({ category })`, conditionally rendered based on the hook's state, with the New Arrivals section as the unconditional fallback.
4. **Reset control + honest captioning**: small, low-risk UI addition once 2-3 above exist.
5. **Closing brand moment**: a one-line addition near the footer — trivial, can ship independently.
6. **Optional enhancements** (only after founder sign-off on the MVP): Shop-page pre-selected filter, PDP related-products preference weighting, named "Edits" as a nav-level concept once 2+ genuinely coherent curated collections exist in the real catalogue.

Each step should get its own commit on a dedicated implementation branch (not this research branch), its own build+test pass, and its own `git diff` review — per this project's existing engineering discipline. This document does not authorize skipping that process.

## Available Now vs Requires Future Data

**Available now** (buildable without any backend/schema/admin-workflow change):
- Category-based Digital Mirror (all 6 real categories, `product_count > 0` filter already exists).
- "Your Edit" / "New Arrivals" fallback (existing query params).
- Real (non-fabricated) low-stock messaging via `stock_quantity`.
- Session-local view/cart-history signals for future refinement (not required for MVP).
- All visual/motion/component work described above (no schema dependency).

**Requires future product data work** (do not build UI that presumes these exist):
- Mood/style/occasion preference picker — needs a controlled, admin-enforced tag vocabulary applied consistently to every SKU.
- Metal-tone ("gold/silver/rose") preference — needs either a schema field or a normalized, disciplined `color` entry convention.
- Named curated "Edits" as a persistent nav concept — needs the founder/catalogue to actually have 2+ coherent groupings beyond the existing category structure (e.g. a real "Gifting" or "New Season" set), not a fabricated one.
- Any "styling context" copy on PDP beyond what a SKU's existing `full_description`/`tags` already states.

## Source URLs

- https://www.prounisjewelry.com/
- https://www.prounisjewelry.com/products/small-antique-red-coral-oval-pendant
- https://www.mignonfaget.com/
- https://www.mignonfaget.com/jewelry/necklaces/petit-mother-of-pearl-daisy-necklace-4535/
- https://us.pandora.net/en/create-a-custom-charm-bracelet/
- AAYNA Brand Book 2026 (local file, not a public URL): `E:\Obsidian_Second_Brain\KJ OS Template\03 Projects\AAYNA\06 Tofail Files\AAYNA - Brand Book.html`
