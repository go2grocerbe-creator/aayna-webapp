# AAYNA — DESIGN.md

**DESIGN.md is the current authoritative digital experience/design source for AAYNA.** Older `design_guidelines.json` (Milestone-1 dusty-rose scaffold spec) is historical and must not override this file. Where the two disagree, this file wins.

This document is research + creative-direction synthesis only. **No application code was changed while producing it.** It exists so a coding agent (Claude/Codex) can implement the next redesign phase without re-researching the three references or re-deriving the creative direction below.

**Revision note (Founder Creative Review pass):** The first version of this document was rejected for creative conservatism — it protected too much of the current storefront's generic visual presentation under the banner of "reuse existing components." This revision keeps every functional/security/business-logic protection from v1 and removes/softens every protection that was really just defending the generic look the founder rejected. Read this document as: **the application engine survives; the customer-facing composition changes materially.**

---

## Vision

AAYNA is not "another jewelry ecommerce template." It is a small, real, Bangladesh-born accessories business (currently ~10-16 SKUs across earrings/necklaces/rings/bracelets/hair-accessories/gift-sets) whose founder has explicitly rejected the current build as generic and AI-templated. The fix is not decoration layered on top of the existing modules — it is a structural recomposition of the customer-facing experience into an original AAYNA digital boutique, built **on top of** the existing (approved, working) ecommerce engine: secure checkout, order confirmation, tracking, admin, SEO, product data.

State this plainly for whoever implements this next: **this document does not describe "add a personalization feature to the current site." It describes recomposing the current site into something else, using the current engine.**

## The Digital Mirror

AAYNA means mirror. The site should behave like one: it does not create the visitor's taste, it **reveals and reflects it back**, a little more clearly with every choice they make. Concretely:

- A short, optional, first-visit moment where the visitor indicates what they're drawn to (grounded in AAYNA's *real* product categories — see Personalization Model).
- The homepage quietly recomposes around that choice for the rest of the session — not just a swapped query, a **visibly different scene** (see Experience Storyboard, Scene III).
- The reflection is always **visible and reversible** — the visitor can see what's shaping their view and clear it in one tap. Never invisible, never "AI knows you."
- Skipping the mirror moment costs nothing — the full catalogue is one tap away regardless.

This is a session/browser-local mechanism (`localStorage`), not a login, not a recommendation model, not third-party tracking. It must degrade to a perfectly normal ecommerce site with zero personalization for any visitor who skips or has JS/storage disabled.

## Brand Foundation

Source of truth: AAYNA Brand Book 2026 (`E:\Obsidian_Second_Brain\KJ OS Template\03 Projects\AAYNA\06 Tofail Files\AAYNA - Brand Book.html`, read in full for this and prior work in this project).

- Colors (research-defined by the Brand Book): Deep Burgundy `#5A0E1A`, Slate Blue `#1A365D`, Warm Coral `#E06D53`, plus proposed supporting neutrals Mirror Ivory `#F8F3EC` and Muted Gold `#C9A66B`.
- Usage principle (Brand Book, verbatim intent): *Burgundy anchors. Ivory breathes. Blue sharpens. Coral activates. Gold finishes.*
- Primary line: **"Reflect Your Aura."** Bangla: আপনার আভাকে প্রতিফলিত করুন। AAYNA = mirror / আয়না.
- The Brand Book's own mirror philosophy, worth building the whole site around, not just quoting: *"AAYNA should feel like a mirror — not a mask. The brand reflects confidence, individuality and an evolving personal style."* Its strongest emotional territory is **recognition**, not transformation: "this is me, seen more clearly." Avoid any copy implying the site changes who the visitor is.
- Voice: confident and poised, artistic and graceful, intimately familiar. Never a discount-page voice, never fake urgency, never unverified product claims (CLAUDE.md governs this project-wide and is unchanged by this document).
- Typography direction (Brand Book-proposed, already implemented): Playfair Display (display/headings) + DM Sans (body/UI), Noto Sans Bengali for Bangla script.
- **No approved final logo exists.** Continue the restrained text wordmark already in place, marked `FOUNDER ASSET REQUIRED — FINAL LOGO`. This document does not change that — a wordmark is not what's being redesigned here, the *composition around it* is.

## Research Sources

Three reference experiences were studied for **structural and interaction principles only** — never for literal copy, imagery, or trademarks. This creative-direction revision does **not** add new research; it works from the evidence already gathered. Full write-ups remain in `.design-research/*.md` (gitignored, working notes, not part of the shipped design system).

| Reference | URL | Role |
|---|---|---|
| A — Prounis Jewelry | https://www.prounisjewelry.com/ | Storytelling / world-building / editorial rhythm |
| B — Mignon Faget | https://www.mignonfaget.com/ | Commerce rhythm / curated shopping / story-inside-shopping |
| C — Pandora "Create a Custom Charm Bracelet" | https://us.pandora.net/en/create-a-custom-charm-bracelet/ | Participation / guided choice interaction model only (not visual design) |

Evidence was gathered with the Firecrawl CLI against homepage + one collection/PDP-equivalent page per site. No third-party screenshots, images, or scraped assets were committed to this repository.

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
- **Shipping/trust micro-copy placed immediately next to Add to Cart**, not lower on the page — AAYNA already does this; keep it.
- **Real stock-count urgency** ("Only 6 left!") is legitimate *only* when wired to the actual `stock_quantity` field, never fabricated.
- Reject: financing widgets (irrelevant to AAYNA's COD/bKash/Nagad payment methods), fake "returning to the vault" scarcity framing, mega-menu-scale taxonomy (AAYNA has ~10-16 SKUs, not hundreds), physical-gallery modules, stacked multi-message promo bars, any bundle-discount mechanic not yet founder-approved.

### From Pandora (dominant: personalization, interaction model only)
- The "custom bracelet builder" is **not a 3D configurator** — it's a 4-step guided *browse* journey where each step is a category filter wearing an emotional label, all steps visible and non-linear, and every step is already a real, immediately-shoppable product grid.
- **The guided step and the product grid are the same UI element** — this is the single most important transferable lesson for AAYNA: a personalization "step" can be nothing more than large, well-photographed choice tiles that set a filter and immediately show real AAYNA products.
- No gate, no lock, always shoppable — never delay a purchase behind "finish choosing first."
- Reject outright: building any product configurator, a multi-screen linear wizard with forward/back navigation, any login requirement.

## Experience Principles

1. **World before catalogue, but not at conversion's expense.** The visitor should feel they entered something considered — but a real product must be reachable within the first two homepage scenes, not buried behind five editorial screens.
2. **Reflection is structural, not decorative.** The mirror motif is expressed through *content responding to choice*, not through literal chrome/glass UI everywhere.
3. **Restraint over noise.** One CTA color (coral) reserved for the one real action per screen. One narrow palette moment per section (Brand Book's "don't use all five colors at equal strength").
4. **Honesty over hype.** No claim, no urgency device, no "AI knows you" language that isn't literally true of the (deterministic, local, non-AI) mechanism actually running.
5. **Small catalogue, treated with respect, not padded.** Don't fake scale; make the real ~6 categories and handful of curated moments feel intentional.
6. **Mobile is the primary medium, not a breakpoint.** Every principle above must survive being described at 375px width before it's considered valid.
7. **Distinctiveness is the point.** If a screen could be mistaken for a generic Shopify theme, a luxury-brand pastiche, or a literal copy of any of the three references, it has failed this document — regardless of how "on-brand" its colors are.

## Visual Architecture vs Application Architecture

**Component reuse does not mean visual reuse.** An implementation agent should read every row below as: keep the wiring, redesign the presentation, unless the row says otherwise.

| Area | Functional architecture (preserve) | Visual architecture (freedom) |
|---|---|---|
| Header | Routes, cart state, search, mobile Sheet drawer behavior, 44px touch targets | **Open.** Composition, wordmark treatment, nav visual language may all change |
| Announcement bar | Single-line, fact-only content (policy-safe copy already established) | Open — color/typography treatment may change |
| Digital Mirror (homepage category choice) | Uses real `category_slug`/`product_count>0` data, sets one `localStorage` preference | **Fully open — must NOT reuse the existing category-tile component.** New original panel (see Digital Mirror Panel) |
| Homepage composition | None — this whole document replaces the current module sequence | **Fully open** — see Experience Storyboard |
| ProductCard / product data | Product fields, `useCart` add-to-cart behavior, stock/OOS logic, `ProductImage` fallback mechanics | **Open** — new editorial variants allowed (see Product Presentation System). Underlying data/behavior identical across variants |
| ProductGrid | Fetching, loading, empty-state logic | Open — composition can vary per narrative section (grid vs. hero+support vs. filmstrip) |
| Shop (`/shop`) | Category/sort query params, real filters only, no fake filters | **Narrow.** Shop is commerce-first by design (see Section: Storytelling Tiers) — light editorial polish only, not a Scene |
| Category (`/category/:slug`) | Category API, product grid, sort | **Medium.** Banner/heading may carry stronger editorial treatment; the grid itself stays commerce-predictable |
| PDP | Product fields, cart/add-to-cart, JSON-LD/SEO, security-safe notes copy | **Open — layout/presentation may substantially evolve.** Gallery, info hierarchy, and story placement can be redesigned; business fields (material/color/size/SKU/availability/price) and Add to Cart behavior cannot be removed or fabricated |
| Cart | Cart logic, stock validation, quantity/remove behavior | **Light rebrand only.** This is a functional utility screen — see Storytelling Tiers |
| Checkout | Secure order creation, guest checkout, `client_request_id` idempotency, validation, field set | **Frozen.** Keep highly conventional. No storytelling content inside checkout, full stop |
| Order Confirmation | Confirmation-token requirement, no PII exposure | Brand presentation allowed (already partly done — Milestone 2) |
| Track Order | Dual order-number+phone verification, generic failure messaging | Light brand presentation allowed |
| Admin | Everything | **Frozen.** Out of scope entirely, as in every prior phase of this project |
| Backend / API / security | Everything | **Frozen.** This document is presentation-layer only |

## Storytelling Tiers

Not every page is a Scene. Getting this wrong (making Shop or Checkout into an art installation) is as bad as the generic-template problem this document exists to fix.

```
Homepage   = strongest storytelling   (all six Experience Storyboard scenes)
Category   = medium storytelling      (editorial banner, commerce-predictable grid below)
PDP        = story + factual commerce (one story beat, then plain facts — Prounis's split)
Shop       = commerce-first           (fast, filterable, minimal narrative)
Cart       = functional               (light rebrand of an inherently utility screen)
Checkout   = purely functional        (zero storytelling, maximum clarity)
```

---

## Experience Storyboard

The homepage is not a stack of ecommerce modules. It is six scenes. Each scene has one emotional job. Products must still be reachable within the first two scenes — this is not negotiable, and every scene below is written to preserve it.

### SCENE I — ARRIVAL

**Emotional objective:** the visitor crosses a threshold into AAYNA. Quiet confidence, an invitation, not a sales pitch. Not a splash screen, not a gate — products remain one scroll away.

**Desktop composition (1440px):** Not a 50/50 copy-left/image-right split. An asymmetric ~60/40 field: the image (or `HeroFallback`, evolved — see Fallback World-Building) occupies the right ~60% of the viewport, full-bleed to the edges top and bottom. The left ~40% holds the type block, but positioned in the **lower third**, not vertically centered — kicker ("AAYNA · Bangladesh", small, tracked) sits above a large Playfair Display rendering of the brand line, "Reflect Your Aura." A single thin vertical rule (1px, burgundy at low opacity) marks the seam between the two zones, reinforcing the mirror-line idea without being literal chrome. Height: ~90vh, not 100vh (100vh reads as a gate; 90vh leaves a visible sliver of the next scene, an implicit promise there's more immediately below).

**Mobile composition (390px):** Image/fallback fills the top ~65% of a ~85vh section. Text block sits in the bottom ~35% over a soft scrim (a burgundy-to-transparent gradient behind the type, not a full solid block) for legibility without hiding the image. Kicker + brand line, left-aligned (not centered — centered reads as generic hero template).

**Typography placement:** Brand line is the single largest text element on the page. No secondary marketing headline competing with it ("Everyday Luxury, Reflected" and similar taglines are retired from the hero — the Brand Book's own primary line carries the whole scene).

**First CTA behavior:** **One** action, not a button-plus-outline-button pair. A quiet coral text link with a trailing arrow — "Enter the collection →" or "Shop Now →" — positioned just below the brand line, sized like a confident sentence, not a large filled button block. The second, generic "explore [category]" button from the current build is removed entirely; Scene II is the real second action.

**Scroll cue:** a single thin vertical line or small chevron in the lower-center of the viewport, optionally paired with a one-word cue ("Reflect ↓" or similar) — not an animated bouncing arrow (that reads as generic template).

**Media treatment / surface:** background is Burgundy (anchor color) behind the fallback state, or the real campaign image once available — this is the one scene allowed a strongly saturated anchor surface, since it's a single threshold moment, not a repeated pattern.

### SCENE II — REFLECTION

**Emotional objective:** the first Digital Mirror choice. The visitor is invited to indicate what they're drawn to, using AAYNA's real categories, presented as **editorial vitrines** — not ecommerce cards. Full spec for the tile/panel component itself lives in **Digital Mirror Panel** below; this scene defines how that component is used on the homepage.

**Composition:** kicker + one-line prompt ("What are you drawn to today?" or refined equivalent) sits above a row of vitrine panels. Panels are **not equal-width thirds/quarters** — use an asymmetric rhythm (e.g. one wider "hero" category — the one with the most stock — flanked by 2-3 narrower panels), so the row itself reads as composed, not templated.

**Desktop:** panels sit in a single row, unequal-width flex/grid (e.g. `1.3fr 1fr 1fr 0.9fr`), portrait aspect ratio (see Digital Mirror Panel), thin 4-8px gaps (adjoining vitrines, not separated cards with big gutters).

**Mobile:** a native horizontal scroll-snap row (`overflow-x-auto snap-x`, no JS carousel), each panel ~68vw wide so the next panel peeks at the edge as an affordance to keep scrolling sideways. Section height ~70vh total (prompt + row + skip link).

**"Show me everything":** not a fifth matching vitrine (that would just be five ecommerce cards instead of four). A clearly legible text link, generous type size, positioned at the end of the row (desktop) or below it (mobile) — equal in legitimacy to any category choice, distinct in form.

**Skippability:** scrolling past without tapping anything is a complete, valid, silent choice — no nag, no re-prompt.

Full panel visual spec: see **Digital Mirror Panel**.

### SCENE III — YOUR EDIT

**Emotional objective:** visible, honest reaction to the visitor's choice (or the default state if skipped). This must look like a **different scene**, not the same product grid with a different query string.

**Data personalization vs. experience personalization (see also Personalization Model):** the *data* filter may be as simple as one category — but the *experience* response is richer: composition, heading, ordering, and scale all change, not just which products are shown.

**Desktop composition:** one **dominant** product (Hero Product presentation variant — see Product Presentation System) at ~60% width, large image, generous type for name/price, one short story line pulled from the product's real `short_description`. Beside it, 2-3 **supporting** products (Editorial Product variant) in a narrower stacked column — not four equal grid cards. The dominant product is chosen deterministically: first `is_best_seller` in the chosen category, else first `is_new_arrival`, else first by default sort — never random, never "AI picked."

**Heading/caption:** short, honest, specific — "Because you're drawn to Earrings" (or the skip-path default, "New This Season" / equivalent unpersonalized heading) — styled as an editorial line (Playfair italic or a DM Sans kicker), not a generic "Recommended For You" SaaS label.

**Mobile:** one strong lead item (Hero Product, full-width) followed by a native horizontal scroll-snap row of the supporting products (no JS carousel dependency, per Mobile Rules). A visible "View the full [Category] edit →" link always present, routing to `/category/:slug`.

**Skip-path fallback:** if no preference is set, this scene shows New Arrivals (existing default query) — same visual treatment (dominant + supporting), just unpersonalized. The scene's *composition* doesn't depend on personalization existing; only its *heading and product source* do.

### SCENE IV — WORLD OF AAYNA

**Emotional objective:** make AAYNA memorable, not make a sale. This is the one scene with no product grid and (at most) one quiet, optional link — not a "Why Choose Us" checklist, not trust badges (those live in Scene-adjacent functional areas, not here).

**Composition:** a large asymmetric split (desktop: ~55/45, image or fallback on one side, statement type on the other, alternating which side from Scene I to avoid visual monotony) with generous negative space — this should feel like the quietest, most spacious moment on the page.

**Content, concretely (not fabricated — grounded in the Brand Book's own words):**
- A large Playfair Display statement, e.g. built from the Brand Book's own mirror philosophy: *"A mirror doesn't create you. It reveals you."* (an original AAYNA line derived from the Brand Book's documented "mirror not mask" concept — not invented from nothing, not copied from a reference site).
- One short material/wear-philosophy line in the established Material Trust voice ("We choose finishes built for real wear, not display cases") — brand-level, no per-SKU technical claims.
- A restrained Bengali typographic detail: the tagline's Bangla rendering (আপনার আভাকে প্রতিফলিত করুন।) set small, as texture/caption, not as a parallel UI language requirement.
- Optional single quiet link ("Our Story →" to `/contact` or a future about page) — do not fabricate an About page's content to fill this scene; if no real story content exists yet, the statement + material line alone are sufficient and honest.

**Explicitly not:** a 3-column icon checklist, delivery/COD/quality badges (those belong in the existing Trust/Care/Delivery functional section, which still exists elsewhere on the page, just not here).

### SCENE V — SECOND REFLECTION

**Emotional objective:** reinforce that the store is progressively responding to the visitor, without overstating the mechanism.

**Composition:** reuses the personalized-category data from Scene III but with a **different visual treatment** — not a repeat of the hero+support layout. Use a horizontal editorial filmstrip instead (Editorial Product variant, 4-5 items, first item slightly larger, native scroll-snap on mobile, a real row on desktop) — so the *experience* clearly differs from Scene III even though both may draw on the same category. Framing copy: "Still drawn to Earrings? Here's what's loved most" (or the honest skip-path equivalent, e.g. "Best Sellers").

**Signal roadmap (design intent, not all built in Phase 1):**

```
MVP (build now):        category selection only (Scene II's single choice)
Phase 1.5 (next):       view-history/category reinforcement — if a visitor
                         views 2+ products in a category without an explicit
                         Scene II choice, treat that as an implicit signal
                         (same localStorage mechanism, same transparency rule)
Future (data-dependent): controlled mood / metal-tone / occasion tags, once
                         the catalogue has a consistent, admin-enforced
                         vocabulary — see Personalization Model
```

Never build UI that implies Phase 1.5/Future signals exist before they're actually wired.

### SCENE VI — DEPARTURE

**Emotional objective:** an intentional ending. The narrative resolves before the functional footer begins — not trust cards, not social links, not a fade straight into the footer.

**Composition:** a contained, **centered** panel (deliberate exception to the asymmetry used elsewhere — closing rituals read as resolved when they're symmetric) on a Burgundy or Ivory field, generous vertical padding (more than any other scene), the concentric-ring/আয়না watermark motif faint in the background, a thin rule, and the brand line once more: "Reflect Your Aura." — possibly with the Bangla line beneath, small.

**No links, no CTA, no product grid in this scene.** A visible seam (a border or deliberate color change) separates it from the footer immediately below, so Departure doesn't blend into the footer — it closes, then the functional footer begins.

**Rationale for scene count vs. conversion:** a real, shoppable product moment appears in Scene III — the third scene, second scroll if the visitor skips Scene II's choice entirely by scrolling past it. This is the same "products early" guarantee as v1 of this document, preserved through a materially different visual composition.

---

## Digital Mirror Panel (component spec)

This replaces the earlier instruction to reuse the existing "Shop by Category" tile. It does not. This is a new, original component.

- **Aspect ratio:** portrait, 3:4 on desktop, 4:5 on mobile (taller than AAYNA's existing square product-card imagery — the point is to read as a vitrine, not a product thumbnail).
- **Text position:** category name set large (Playfair Display, 600-700 weight), positioned so it slightly overlaps the panel's lower or side edge — an intentional "cropped masthead" treatment, not centered caption text in a bottom-left corner box.
- **Image behavior:** full-bleed within the panel, `object-cover`. On hover (desktop only): a very subtle scale (1.0 → 1.03, slower than the existing product-card hover, ~600ms) — restrained, not the product-card's snappier 1.05/300ms treatment, so vitrines feel calmer than commerce cards.
- **Fallback (no photography):** a duotone/gradient field (see Fallback World-Building for the palette rules) overlaid with a large, cropped first-letter treatment of the category name in Playfair Display — e.g. a huge serif "E" bleeding off one edge of the panel for Earrings — rather than a small centered icon. This must look art-directed, not like a loading placeholder.
- **Selected state:** no colored border, no checkmark badge. Unselected panels dim slightly (a fine burgundy scrim at low opacity, or a slight desaturation via CSS filter) while the selected panel stays at full clarity; a thin burgundy underline (2px) appears beneath its name only.
- **Hover/focus state:** the subtle image scale above, plus the category name's letter-spacing tightens marginally (a "coming into focus" micro-interaction) — keyboard focus gets the same visual treatment as hover (never a default browser outline alone; use a visible custom focus ring consistent with the rest of the codebase's focus-ring pattern).
- **Mobile interaction:** tap selects and immediately triggers the Scene III transition (see below); no separate "confirm" step.
- **Desktop interaction:** click selects; the panel's selected state persists visually while Scene III below updates.
- **Transition into Your Edit:** selecting a panel triggers a single crossfade (~250ms opacity) of Scene III's content in place — never a page navigation, never a modal, never a loading spinner (the data is a synchronous local filter of already-fetched categories/products where possible, or a fast query — treat as instant).
- **Markup requirement:** real `<button>` elements (or `<a>` if they double as direct category links), not `<div onClick>` — accessibility non-negotiable, matches the rest of the codebase's existing pattern.

## Product Presentation System

Three **visual variants around the same underlying product data and cart behavior** — not three data models, not three components with separate logic. Implementation should be one product-rendering system with a `variant` prop (or equivalent), sharing `ProductImage`, `useCart`, stock/OOS logic, and pricing formatting across all three.

### Commerce Card
Used on `/shop`, `/category/:slug` grids, Cart/Checkout line items. Fast, predictable, compact — this is close to the existing `ProductCard`: square image, category label, name, price + muted compare-at, one restrained discount badge, coral quick-add. **Do not add editorial flourish here** — Shop is commerce-first by design (see Storytelling Tiers).

### Editorial Product
Used inside homepage storytelling (Scene III's supporting items, Scene V's filmstrip). Larger image aspect (4:5, not square), less UI chrome — price shown, but no badge clutter, no quick-add button (tapping/clicking the item goes to PDP; the "buy fast" affordance is Commerce Card's job, not this variant's). Name set in Playfair Display at a larger size than Commerce Card's DM Sans label.

### Hero Product
Used for the single dominant item in Scene III and as a lead-item treatment in Scene V's filmstrip. One large, near-full-bleed image (largest of the three variants), name and price in the largest type of any product presentation, plus one short story line (real `short_description`, never fabricated if empty), and — uniquely among the three variants — a visible Add to Cart action (coral), since this is the one editorial product moment intended to convert directly without a PDP visit first.

**Mobile behavior (all three variants):** Commerce Card stays in its existing responsive grid. Editorial Product and Hero Product both go full-width or near-full-width on mobile (Editorial Product inside its horizontal scroll-snap row, Hero Product as the lead full-width block above that row) — never shrink the editorial variants down to Commerce-Card-sized tiles on small screens; if space is tight, show fewer items rather than smaller ones.

---

## Photography & Art Direction

The Imagery Direction from v1 was technically safe but creatively thin. This is the actual vocabulary to design toward and, eventually, shoot toward — guidance, not fabricated assets.

### Product truth
Macro/detail shots of clasps, posts, plating edges; accurate finish and material rendering (no color-grading that misrepresents actual tone); clean silhouettes against a controlled background; honest scale references (on ear/hand/wrist/neck, not floating in space with no size cue).

### Editorial
Skin, movement, fabric — real wear, not a static product-only shot. South Asian/Bangladesh visual context where it's authentic (real styling, real settings, real skin tones) — never a generic "diverse stock model" substitute. Close crops on hands/ears/neck/wrist rather than full-face-forward catalogue poses. Intentional, directional shadow (not flat studio lighting on every shot). A subtle mirror/reflection framing device where it occurs naturally (a reflective surface, a paired earring shot suggesting symmetry) — not forced into every image.

### Still life
Ivory and burgundy as the dominant surface colors, slate blue as an occasional accent, gold used only as a restrained highlight (foil, a thin line, a small prop detail) — never as a dominant surface. Tactile surfaces (linen, paper, stone, wood grain) over glossy/plastic ones. Purposeful negative space — a still life with room to breathe reads as premium; a crowded flatlay reads as marketplace.

### Explicitly avoid
Generic "Unsplash woman wearing jewelry" stock photography; generic marble flatlays (the single most overused jewelry-ecommerce cliché); velvet-cliché fake-luxury staging; obviously AI-generated imagery unless specifically art-directed and founder-approved as such; any Product-Demo-Batch-1-style supplier/sourcing photography (already confirmed unusable — cost prices burned into pixels, factory packaging, personal backgrounds — treat as `INTERNAL SOURCING REFERENCE ONLY`, never public); a plain white-background catalogue shot as the *only* presentation style for any given product (fine as one image in a gallery, wrong as the sole visual language of the site).

## Fallback World-Building

AAYNA currently has no launch photography. The site must look intentionally designed **before** photography arrives, not like a placeholder waiting for content. The existing three-gradient-rectangle editorial panel (Milestone 1's `Home.jsx`) is not sufficient on its own going forward — it's one ingredient, not the whole language.

**The upgraded no-photo vocabulary, built only from approved brand tokens:**
- Large-scale editorial typography as the primary visual event (a single oversized word or the brand line itself, cropped by the viewport edge) — type *as* image, not type *on top of* an empty rectangle.
- The আয়না watermark (already built as part of `HeroFallback`) — reused at varying scale and opacity across fallback surfaces, not confined to the hero alone.
- The concentric-ring/reflection motif (already built) — reused as a background texture on any large fallback surface, not just Scene I.
- Cropped, oversized first-letter treatments per category (see Digital Mirror Panel) — a distinctive, designed device rather than a generic icon-in-a-circle.
- Thin hairline rules (1px, burgundy or gold at low opacity) used to divide or frame a fallback panel — a small detail that reads as "designed," not "empty."
- Paired/echoed shapes — two offset circles, or a shape and its slightly-shifted duplicate — a restrained, structural nod to reflection without literal mirror chrome.
- Duotone gradient fields (the existing burgundy/blue/coral panels) remain valid **as a background layer**, combined with at least one of the devices above on top — never shipped bare as the entire fallback.

**Explicitly avoid:** literal mirror/glass/chrome UI skins, glassmorphism (blurred translucent panels), gradient rectangles with nothing else on them, generic "coming soon" placeholder language or iconography.

## Mirror Motif

Not literal chrome or mirror-shaped UI. The reflection metaphor is expressed structurally and through the fallback vocabulary above:

1. **Choice → reflected result.** The clearest expression: tapping a Digital Mirror panel visibly changes Scene III to reflect that choice. The mechanism *is* the metaphor.
2. **The concentric-ring + faint "আয়না" watermark device** is the one literal visual motif approved for reuse — now expanded across the Fallback World-Building vocabulary rather than confined to one hero state.
3. **Soft echo, not duplication**: where Scene V reflects an earlier choice, a small recurring visual cue (the same category's accent tint, a one-line "because you chose X" caption, the paired/echoed-shape device) is sufficient — do not render literal mirrored/duplicated product images or symmetric photo compositions as a design gimmick.
4. **Restraint is the sophistication.** A brand called "Mirror" does not need visual mirrors on every screen — one well-placed motif family (ring/watermark/letterform-crop/paired-shapes) plus a structural reflection mechanism (choice → tailored content) is sufficient and avoids the "gimmicky" trap.

## Motion System

**Revised philosophy: motion supports narrative and confirms state** — not "motion only confirms state." A scene entrance, a masked reveal, or a slow image reveal are allowed to exist purely to support the storytelling mood, as long as they stay cheap, purposeful, and never gratuitous or looping.

| Moment | Treatment | Approx. duration/easing |
|---|---|---|
| Scene entrance (first paint) | Above-fold Scene I elements may use a single fade+translate-up on load | 0.6s `cubic-bezier(0.16, 1, 0.3, 1)` (existing keyframe) |
| Scene reveal (scroll) | CSS-only via a single shared `IntersectionObserver`, triggered once per scene as it enters viewport — no scroll-jacking, no pinning | Fade-up timing above, or a masked reveal (clip-path inset animating open) for Scene IV/VI's large imagery |
| Slow editorial image reveal | Scene IV/VI large images may use a very slow, subtle scale-down (1.04 → 1.0 over first viewport entry only, never looping) — restrained "breathing" effect, not a Ken Burns pan | 1.2-1.5s ease-out, once only |
| Digital Mirror panel hover | Subtle image scale (1.0 → 1.03) + letter-spacing tighten | 500-600ms ease (slower/calmer than product-card hover) |
| Digital Mirror panel selection | Border/dim-state transition (unselected panels dim, selected clarifies) | 200-250ms ease |
| Scene III transition after a choice | Cross-fade the scene's content, not a slide/wipe | ~250ms opacity fade |
| Product card hover (Commerce Card) | `scale-105` on image, existing pattern, unchanged | 300-500ms ease |
| Quick-add reveal | Opacity + translate-y, existing pattern, unchanged | 300ms ease |
| Drawer/menu (mobile nav, cart) | Existing Radix `Sheet` transitions — reuse | Existing Radix defaults |
| Loading | Existing skeleton pattern (`bg-aayna-beige/60` pulse) — reuse, no spinners for content loading | Existing `animate-pulse` |
| Reduced motion | `prefers-reduced-motion: reduce` disables every scroll-reveal/scale/masked-reveal effect above — content shows in final state immediately. Only functional transitions (drawer open/close, focus states, the Scene III cross-fade, since it communicates real state change) remain | — |

**Still explicitly out of scope:** WebGL, scroll-jacking/pinned sections, cursor-follow effects, parallax beyond the single subtle image-scale treatment above, heavy JS animation libraries, autoplay video/motion on the homepage.

## Navigation

**Function preserved, presentation open.** Routes, cart state/badge, search, and the mobile Sheet drawer's *behavior* (open/close, 44px touch targets, focus trapping) are unchanged. The header's *visual composition* — wordmark treatment, spacing, how category links are presented, whether the header is transparent-over-Scene-I and solidifies on scroll — is open to redesign as part of recomposing the site, since a generic-feeling header contributes to the "AI-templated" impression as much as the homepage does. The Digital Mirror does not add a new top-level nav item; its effect is felt on the homepage and in the (still-existing) category links.

## Components

Read against the Visual Architecture table above — this list only calls out what's genuinely new or notably changed.

- **Digital Mirror entry module** *(new)* — Scene II, built from the new Digital Mirror Panel component. Not the existing category-tile component.
- **Preference selector** — the panels themselves are the selector (Pandora lesson); no separate form control.
- **Personalization state indicator** — no progress bar; a small "Because you're drawn to X — Reset" line above any personalized scene is sufficient state communication.
- **Editorial chapter (Scene IV)** *(new visual treatment)* — asymmetric split, large statement type, no icon checklist.
- **Product Presentation System** *(new)* — Commerce Card / Editorial Product / Hero Product, one shared data/behavior layer, three visual variants (see above).
- **ProductGrid** — fetching/loading/empty-state logic unchanged; composition wrapping it varies per scene (grid on Shop/Category, hero+support on Scene III, filmstrip on Scene V).
- **Product carousel** — if a horizontal row is needed anywhere (Scene II mobile, Scene III mobile, Scene V), it is a native CSS scroll-snap row, never a JS carousel library.
- **PDP** — structurally free to evolve (gallery, info hierarchy, story placement); business fields, Add to Cart, and security-relevant copy unchanged. See Product Detail Pattern below.
- **Cart / Checkout / Order Confirmation / Track Order / Admin** — see Visual Architecture table; functional logic frozen in all cases, presentation freedom scales from "none" (Checkout, Admin) to "light" (Cart, Confirmation, Track Order).
- **Image fallback (`ProductImage`)** — unchanged mechanism, reused everywhere; extended conceptually by the Fallback World-Building vocabulary for non-product imagery surfaces (Scene panels, editorial fallbacks).
- **Loading skeleton** — unchanged (`bg-aayna-beige/60` pulse).

## Personalization Model

### Data personalization vs. experience personalization

These are not the same thing, and conflating them is what made v1 of this document feel thin. **Data personalization** in Phase 1 is genuinely simple — one category filter. **Experience personalization** is everything Scene III and Scene V do with that one signal: different composition, different heading voice, different product scale/ordering, different section rhythm from the unpersonalized default. A visitor should feel meaningfully reflected back by the *experience*, even though the underlying *data* signal is honestly minimal. This is how Phase 1 can feel considered without claiming intelligence it doesn't have.

### Grounded in AAYNA's real product schema (`backend/server.py` `PUBLIC_PRODUCT_FIELDS`, verified directly, not assumed)

Public product fields actually available today: `product_name`, `category_name`, `category_slug`, `selling_price`, `discount_price`, `images`, `short_description`, `full_description`, `material`, `color`, `size`, `weight`, `status`, `stock_quantity`, `is_featured`, `is_best_seller`, `is_new_arrival`, `tags`.

**AVAILABLE NOW** (reliable, always populated, safe to build on today):
- `category_slug`/`category_name` — 6 real categories. The *only* field guaranteed consistently populated and structurally clean across every SKU.
- `is_new_arrival`, `is_best_seller`, `is_featured` — booleans, already used by existing query params.
- `stock_quantity` — real inventory count, usable for genuine low-stock messaging (Mignon Faget lesson), only below a real threshold.
- Locally-tracked session signals requiring no backend change: categories/products viewed this session, products added to cart, which Digital Mirror panel (if any) was picked. One `localStorage` key, one-tap clearable.

**REQUIRES FUTURE PRODUCT TAGGING** (do not build a preference picker on these until they exist):
- `tags` is free-text and inconsistently applied per SKU today. Not a controlled vocabulary. A mood/occasion preference picker is only honest once every SKU carries a consistent tag from a fixed, admin-enforced list — flag to the founder/admin workflow before building.
- `color` is free-text ("Gold and white," "Rose pink and gold") — not a clean "metal tone" facet. Needs a schema field or a disciplined admin-entry convention first.
- Occasion/styling-context tagging does not exist in the schema at all today.

### The MVP taxonomy

Because only `category_slug` is reliably clean today, the Scene II choice is category-based, not a mood taxonomy — this reuses Pandora's core lesson (the panel *is* the filter) and Mignon Faget's lesson (one data structure serves both story and filter). Do not default to "Minimal / Romantic / Bold / Classic" — unsupported by the schema.

Proposed first-visit prompt (framing, not literal final copy): **"What are you drawn to today?"** — 3-4 Digital Mirror panels, each a real category with `product_count > 0`, plus the equal-legitimacy "Show me everything" exit.

## First-Visit Journey

1. Visitor lands on `/`. Scene I (Arrival) renders.
2. Scene II (Reflection) — the Digital Mirror invitation — is the very next section. No scroll-jacking, no modal takeover.
3. Visitor taps a panel, taps "Show me everything," or scrolls past without interacting.
4. If a panel was tapped: preference written to `localStorage`; Scene III (Your Edit) renders content sourced from that category with the honest caption pattern.
5. If skipped: no preference stored; Scene III renders its unpersonalized default (New Arrivals), same visual composition.

## Returning Journey

- On any later page load in the same browser, the stored preference is read and applied the same way — Scene III/V reappear pre-filled, no re-asking.
- A visible, low-friction **"Not feeling this? Reset"** control sits near any personalized scene — one tap clears `localStorage`, no confirmation dialog needed (not destructive/irreversible).
- No account, no server-side profile, no cross-device sync. Clearing storage or switching devices simply shows the first-visit journey again — this is transparency, not data loss, and must never be described to the visitor as a loss of "their" data.
- Never imply the site "remembers you" psychologically ("we know you love gold"). Transparent, poetic-but-honest framing only ("Picking up where you left off").

## Design Tokens

All values below are **already implemented** in `frontend/tailwind.config.js` and `frontend/src/index.css` — this section documents them as the system of record.

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
| success | Tailwind `green-700` (existing usage) | — |
| warning / low-stock | pick one Tailwind `amber-700`-range class on first use, then reuse | — |
| error | Tailwind `red-700` (existing usage) | — |

**Usage rule, unchanged and still the most important sentence in this section: Ivory is the dominant page surface. Burgundy is for anchors — never every card. Coral is reserved for the one real action per screen — never decoration. Blue is sparing. Gold never becomes a large background.** Scene I and Scene VI are the two deliberate exceptions where Burgundy may dominate a full section, because they are singular threshold/closing moments, not repeated patterns.

## Typography

| Role | Family | Notes |
|---|---|---|
| Display / editorial title | Playfair Display, 500-700 | Hero headlines, Scene statements, Digital Mirror panel labels, Hero Product names |
| H1 | Playfair Display 700 | `text-4xl md:text-5xl` |
| H2 | Playfair Display 600-700 | `text-3xl md:text-4xl` |
| H3 | Playfair Display 600 | `text-xl md:text-2xl` |
| Body | DM Sans 400 | 16px base |
| Caption / kicker | DM Sans 500-600, uppercase, tracked | `text-[11px]`-`text-xs`, `tracking-[0.15em]`-`[0.2em]` |
| Navigation | DM Sans 500 | `text-sm` |
| Price (Commerce Card) | DM Sans 700, `aayna-burgundy` | Existing |
| Price (Hero/Editorial Product) | Playfair Display 600, larger scale | New — editorial variants may set price in the display face, not just DM Sans |
| Bengali | Noto Sans Bengali | Cultural/editorial texture (Scene IV, VI, the mirror watermark) — never the primary commerce-UI language |

## Layout & Spatial System

**Spacing:** base unit 4px (Tailwind default). Section vertical rhythm `py-14 md:py-20` for functional sections; Scenes I/IV/VI may use larger, more generous padding (`py-20 md:py-32`+) since they are the deliberately spacious moments. Content width `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8` for commerce content; Scenes may go full-bleed with internally constrained text. Product grid gaps `gap-4 md:gap-6`.

**Shape (protection kept — this defends a real, founder-endorsed decision, not the generic-look problem):** near-zero border radius throughout — `rounded-sm` on buttons/inputs, no radius on images/cards/panels, `rounded-full` only for genuinely circular elements. **No glassmorphism. No fake mirror-chrome UI.** Borders: `border border-aayna-beige` standard. Shadows minimal — `hover:shadow-md` on interactive commerce cards only, no ambient shadows on editorial panels (flat, print-like surfaces, per Prounis/Mignon Faget).

**Asymmetry, revised:** v1 restricted asymmetric layout to "editorial only." That restriction is loosened: Scene I, II, III, IV, and V should all use asymmetric composition as their default (per their individual specs above) — symmetry is now the deliberate exception (Scene VI's closing moment), not the commerce-section default. Shop/Category/Cart/Checkout remain symmetric/predictable, per Storytelling Tiers — that protection stays, because those are the tiers where a small-catalogue mobile shopper needs speed over novelty.

## Accessibility

- Every Digital Mirror panel and any new scene-level interactive element is a real `<button>`/`<a>`, visible focus states, never `<div onClick>`.
- The "Reset" control has a clear accessible label ("Reset your preference"), not just an icon.
- `prefers-reduced-motion` respected across every effect in the Motion System table.
- Alt text preserved on all product imagery via `ProductImage`, including fallback states.
- Color contrast: burgundy/charcoal-on-ivory already meets WCAG AA. Any new coral-on-white, gold-on-white, or white-on-image (Scene I/II/IV text-over-photo) combination must be checked before shipping — text over photography needs the scrim treatment specified in each Scene, not raw white text on an uncontrolled image.

## Performance

Immersive does not mean heavy.

- No WebGL, no video backgrounds, no autoplay-heavy homepage content.
- Scene imagery: same lazy-loading, `object-cover` treatment as existing patterns — no new image pipeline. Scene I's hero image is the one exception that should load eagerly (it's above the fold at first paint).
- Scroll-reveal via one shared `IntersectionObserver` instance, not one per element.
- No new client-side dependency (carousel, animation, or 3D library) for any effect described in this document — everything above is achievable with existing Tailwind/CSS/React patterns.
- `localStorage` read/write for the personalization preference is synchronous and trivial — no loading state needed for it.
- Preserve the existing bundle-size discipline (current production build ≈193KB gzip main bundle) — evaluate any new module against that baseline.

## Content & Voice

- Confident, poised, artistic, intimately familiar — never a discount-page voice.
- No fabricated urgency, no fake personalization claims ("Our AI thinks..."), no unverified product/material claims.
- Digital Mirror copy is poetic but **transparent**: a way to browse faster based on what you tap, not a psychological profile. "Picking up where you left off" is honest; "We know exactly what you love" is not.
- Bangla is used for cultural texture at specific brand moments (Scene IV, Scene VI, the mirror watermark), not as a parallel UI language requirement for this phase.

## Product Detail Pattern

Tier: story + factual commerce (see Storytelling Tiers). Layout/presentation may substantially evolve; the underlying fields, cart behavior, and security-relevant copy do not.

```
Hero product image (gallery, ProductImage fallback — presentation may evolve,
  e.g. a larger/more editorial crop than the current square gallery, as long
  as the full image set remains viewable)
↓
Product identity: category label, name, price + muted compare-at, one
  discount badge (unchanged restraint rule from the Visual QA Fix Sprint)
↓
"Why it belongs in the edit" — ONE short sentence of story-voice copy from
  the product's real short_description — never invented, falls back to
  nothing if the field is empty
↓
Product facts — attributes (material/color/size/SKU/availability) — may be
  presented with a stronger editorial layout than the current two-column dl,
  but every fact currently shown must remain shown
↓
Styling context — OPTIONAL, only if full_description/tags genuinely support
  it — never invented
↓
Add to Cart / Buy Now (coral/burgundy-outline pairing — unchanged)
↓
Delivery/quality/returns notes (unchanged, already policy-safe)
↓
Full description (unchanged)
↓
Related products — if a Digital Mirror preference is active and the current
  product isn't in that category, surface 1-2 items from the preferred
  category here — optional
```

Never invent factual product claims — unchanged from CLAUDE.md and every prior milestone.

## Cart/Checkout Pattern

**Unchanged, and this protection is correct, not a symptom of creative conservatism.** Secure order creation, guest checkout, duplicate-click protection (`client_request_id`), the Contact/Delivery/Payment/Summary structure, and the confirmation-token flow are explicitly protected. Cart gets a light rebrand (token/color/type updates only, structure unchanged); Checkout stays purely functional and highly conventional — no storytelling content inside checkout, full stop. This is the one place in the experience where speed and clarity outrank narrative.

---

## Page Wireframes

Concrete enough to compose from, not just a component list.

### Homepage — mobile, 390px

```
Announcement bar          ~32px  (unchanged)
Header                    ~64px  (unchanged behavior, open presentation)
SCENE I — Arrival         ~85vh  image/fallback top 65%, text+CTA bottom 35%
                                  over scrim, left-aligned, single scroll cue
SCENE II — Reflection     ~70vh  kicker+prompt ~15%, horizontal snap panel
                                  row ~55% (each panel ~68vw, 4:5 aspect,
                                  next panel peeking), "show everything"
                                  link ~10%
SCENE III — Your Edit     ~90vh  caption ~10%, Hero Product full-width
                                  ~55%, horizontal Editorial Product row ~35%
SCENE IV — World of AAYNA ~80vh  large statement type + one image/fallback,
                                  generous padding, no grid
SCENE V — 2nd Reflection  ~70vh  caption + horizontal filmstrip (Editorial
                                  Product variant, first item larger)
SCENE VI — Departure      ~40vh  centered, contained, no links
Trust/Care/Delivery       existing TrustBadges section, unchanged
Footer                    unchanged
```

Total pre-footer scroll on mobile is long by ecommerce-homepage standards but each scene is short (~1 viewport), and a real product is reachable by the third scene (worst case: visitor scrolls past Scene II without tapping).

### Homepage — desktop, 1440px

```
Announcement + Header                     unchanged behavior, open presentation
SCENE I — Arrival            ~90vh   asymmetric 60/40 (image/text), text
                                      block lower-left, thin vertical rule seam
SCENE II — Reflection        ~70vh   unequal-width panel row (e.g.
                                      1.3fr/1fr/1fr/0.9fr-link), thin gaps
SCENE III — Your Edit        ~85vh   asymmetric 60/40 (Hero Product left,
                                      2-3 stacked Editorial Products right)
SCENE IV — World of AAYNA    ~80vh   asymmetric 55/45 (image/statement,
                                      alternate side from Scene I)
SCENE V — 2nd Reflection     ~60vh   horizontal filmstrip, first card larger,
                                      4-5 items total
SCENE VI — Departure         ~50vh   centered, max-w-2xl, full-bleed field
Trust/Care/Delivery, Footer          unchanged
```

### PDP — mobile, 390px

```
Breadcrumb                unchanged
Gallery                   full-width, may crop taller/more editorial than
                           current square treatment; swipeable
Category label + name + price + compare-at + one discount badge
"Why it belongs" story line (one sentence, conditional on real data)
Attributes (material/color/size/SKU/availability) — editorial layout allowed
Add to Cart / Buy Now (unchanged pairing)
Delivery/quality/returns notes (unchanged)
Full description
Related products
Sticky mobile Add-to-Cart bar (unchanged, incl. WhatsApp-clearance fix)
```

### PDP — desktop, 1440px

```
Two-column: gallery left (~55%, may be larger/more editorial than current),
info right (~45%): category, name, price block, story line, attributes,
CTAs, notes — same vertical order as mobile, just alongside the gallery
instead of below it. Full description and related products remain full-width
below the two-column block.
```

## Mobile Rules

- Every scene above is authored mobile-first; heights given are targets, not hard limits.
- Digital Mirror panels: horizontal scroll-snap or a considered 2-up grid at 360-430px, never page-level horizontal scroll.
- Sticky Add to Cart (PDP) and the WhatsApp float never overlap — already fixed via the route-aware offset pattern; any new sticky UI follows the same "reserved bottom zone" approach.
- Touch targets: 44px minimum, applied identically to Digital Mirror panels/controls.
- Kicker labels and captions fit on one line at 360px without awkward wrapping — test actual copy at that width before shipping.
- Any horizontal product row uses native CSS scroll-snap, never a JS carousel — stays light on low-end Android devices common in the target market.

## Do / Don't

**Do:**
- Recompose the homepage into the six-scene structure; reuse underlying data/logic (`ProductGrid` fetching, `useCart`, `ProductImage`) across all three Product Presentation variants.
- Keep the Digital Mirror choice reversible, visible, and skippable at all times.
- Ground every personalization signal in a real, currently-populated schema field.
- Keep coral as the only CTA color, burgundy as the only anchor color, at every screen — including new editorial scenes.
- Test every new pattern at 375px before 1440px.
- Treat Shop, Cart, and Checkout as commerce-first/functional tiers — resist the urge to "scene-ify" them too.

**Don't:**
- Don't build a product configurator (Pandora's literal product, not the principle to copy).
- Don't invent a mood/style taxonomy the product data can't back up yet.
- Don't add a login requirement anywhere in this phase.
- Don't add WebGL, scroll-jacking, or autoplay video.
- Don't let "world-building" push the first real product below Scene III.
- Don't use Product Demo Batch 1 photos anywhere, ever, including internal previews.
- Don't touch Cart/Checkout/order-security/Admin architecture — explicitly out of scope.
- Don't invent delivery timelines, exchange windows, or other business-policy claims.
- Don't reuse the existing category-tile component for the Digital Mirror — it needs its own component (see spec above).
- Don't ship a "Why Choose Us" checklist in Scene IV.
- Don't use glassmorphism or literal mirror/chrome UI anywhere.
- Don't ship an editorial fallback that's just a bare gradient rectangle — combine at least one Fallback World-Building device with it.

## Implementation Guidance

Suggested build order, sized to keep each step reviewable and revertible (inspect → plan → implement → build → test → commit):

1. **Product Presentation System**: refactor the product-rendering layer to support Commerce Card / Editorial Product / Hero Product variants sharing one data/cart layer. Lowest risk, unlocks everything else.
2. **Digital Mirror data layer**: a small `usePreference()` hook wrapping `localStorage` (get/set/clear a single `category_slug` string + timestamp) — no backend change.
3. **Digital Mirror Panel component**: build fresh, per spec — do not adapt the existing category tile.
4. **Scene II + Scene III**: wire the panel component into Scene II; build Scene III's dominant+supporting layout using the Product Presentation System from step 1.
5. **Scene I, IV, VI**: the three non-product-dependent scenes — can be built in parallel with 2-4 once the Fallback World-Building assets/CSS exist.
6. **Scene V**: filmstrip layout, reuses Scene III's data with a different composition.
7. **Reset control + honest captioning**: small addition once Scenes II/III exist.
8. **PDP evolution**: apply the story/fact separation and editorial gallery treatment — independent of the homepage scenes, can proceed in parallel.
9. **Category page banner** (medium-storytelling tier): lighter-weight pass, independent.
10. **Optional/Phase 1.5+**: view-history signal, Shop pre-selected filter, PDP related-products preference weighting, named "Edits" nav concept once real curated groupings exist.

Each step gets its own commit on a dedicated implementation branch (not this research branch), its own build+test pass, its own `git diff` review. This document does not authorize skipping that process.

## Available Now vs Requires Future Data

**Available now** (buildable without any backend/schema/admin-workflow change):
- Category-based Digital Mirror (all 6 real categories, `product_count > 0` filter already exists).
- The full six-scene homepage recomposition, Product Presentation System, Fallback World-Building vocabulary, and Motion System — no schema dependency.
- Real (non-fabricated) low-stock messaging via `stock_quantity`.
- Session-local view/cart-history signals for Phase 1.5 (not required for MVP).

**Requires future product data work** (do not build UI that presumes these exist):
- Mood/style/occasion preference picker — needs a controlled, admin-enforced tag vocabulary.
- Metal-tone preference — needs a schema field or a normalized `color` entry convention.
- Named curated "Edits" as a persistent nav concept — needs 2+ genuinely coherent groupings in the real catalogue, not a fabricated one.
- Any "styling context" copy on PDP beyond what a SKU's existing `full_description`/`tags` already states.
- Real photography for any scene — the Fallback World-Building vocabulary is the interim, not a placeholder to be embarrassed about.

## Source URLs

- https://www.prounisjewelry.com/
- https://www.prounisjewelry.com/products/small-antique-red-coral-oval-pendant
- https://www.mignonfaget.com/
- https://www.mignonfaget.com/jewelry/necklaces/petit-mother-of-pearl-daisy-necklace-4535/
- https://us.pandora.net/en/create-a-custom-charm-bracelet/
- AAYNA Brand Book 2026 (local file, not a public URL): `E:\Obsidian_Second_Brain\KJ OS Template\03 Projects\AAYNA\06 Tofail Files\AAYNA - Brand Book.html`
