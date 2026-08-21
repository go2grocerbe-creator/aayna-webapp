# AAYNA_FRONTEND_VISION.md

Focused implementation-art-direction companion to `DESIGN.md`. `DESIGN.md` remains the concept/narrative/data authority (Digital Mirror mechanism, six-scene structure, personalization model, protected architecture). This file makes the specific visual-craft decisions DESIGN.md's own sketches deliberately left open, using three real prototypes as evidence rather than description alone.

No production React was touched to produce this. Three standalone HTML prototypes were built, screenshotted, and visually reviewed at 390px and 1440px before writing this document.

---

## Design Skills Used

- **`frontend-design` (official Anthropic plugin)** — installed this session (`claude plugin install frontend-design@claude-plugins-official -s user`, confirmed via `claude plugin list`: enabled, user scope). Not yet loaded into *this* live session's skill registry (plugins load at session start; will activate automatically next session) — read its `SKILL.md` directly from `~/.claude/plugins/cache/claude-plugins-official/frontend-design/unknown/skills/frontend-design/SKILL.md` and applied its brainstorm→critique→build process by hand for this pass. **Status: ACTIVE** (installed + enabled; applied manually this session, will auto-load going forward).
- **`ui-ux-pro-max`** — already available this session, invoked directly. **Status: ACTIVE.**

## Source Files Used

- AAYNA Brand Book 2026 — `E:\Obsidian_Second_Brain\KJ OS Template\03 Projects\AAYNA\06 Tofail Files\AAYNA - Brand Book.html` (re-read in full from disk this session)
- `E:\deMarkt\aayna-webapp\Aayna-Webapp\DESIGN.md` (re-read in full from disk this session)
- **Exact Apple reference path:** no pre-existing Apple design file was found anywhere under `E:\deMarkt\aayna-webapp\Aayna-Webapp` or `E:\Obsidian_Second_Brain\KJ OS Template\03 Projects\AAYNA` (searched by filename and `git ls-files`). Created one via Firecrawl research instead: `.design-research/apple/apple-motion-spacing.md` (gitignored). It documents technique only (spatial rhythm, staged-entrance timing, crossfade-over-hard-cuts, restrained scale, focus discipline) and explicitly lists Apple's colors/typography/button shapes/copy as **not** transferable — confirmed in the file itself, re-confirmed here.

## UI/UX Pro Max Findings

Ran `--design-system` for "editorial luxury accessible-premium jewelry ecommerce storytelling", plus targeted `--domain ux`, `--domain landing`, `--domain gsap`, `--domain product` queries.

**Rejected outright** (per the explicit instruction not to let it override the Brand Book):
- Its default "E-commerce Luxury" product-type match recommends **Liquid Glass / Glassmorphism** as the primary style — directly conflicts with DESIGN.md's Shape rules and the founder's repeated "no glassmorphism" instruction. Not used.
- Its generated color palette (near-black `#1C1917` + gold accent) and typography pairing (Cormorant/Montserrat) — AAYNA's palette and Playfair Display/DM Sans pairing are already fixed by the Brand Book. Not used.
- "Horizontal Scroll Journey" pattern (pinned horizontal track) — its own `gsap` domain results independently warn "don't pin more than 1-2 sections... hurts mobile UX," which is exactly the scroll-jacking DESIGN.md and the founder both explicitly forbid. Considered and rejected.

**Kept:**
- The full pre-delivery checklist (44px touch targets, 150-300ms hover transitions, 4.5:1 contrast, visible focus states, `prefers-reduced-motion`, no horizontal scroll, responsive at 375/768/1024/1440) — used as the QA baseline for all three prototypes.
- Concrete motion timing values from the `gsap` domain (translated to native CSS, not the GSAP library — DESIGN.md's performance budget forbids a new animation dependency): Scroll Reveal Subtle tier (~300-400ms, small 8-16px y-offset, ease-out), Stagger List Standard tier (~80-150ms offset per element). These match and slightly extend DESIGN.md's existing Motion System table.
- "Scroll-Triggered Storytelling" landing pattern's core idea (chapter-based pacing, mini-CTA per chapter) — already essentially what DESIGN.md's Experience Storyboard does; confirms the approach rather than changing it.

## Frontend-Design Direction

Applied the skill's brainstorm→critique→build process directly (see Concepts A/B/C below for the actual token-system-per-concept output). Its most load-bearing instruction for this project: **AI-generated design right now clusters around three defaults** — warm-cream-serif-terracotta, near-black-with-one-bright-accent, or broadsheet-hairline-newspaper. AAYNA's *existing* build (pre-this-pass) was closest to the first cluster without ever deliberately choosing it — burgundy-on-ivory-serif is dangerously close to "the generic default for this kind of brief" if executed without a genuine signature move. All three concepts below were built specifically to avoid landing back in that default by giving AAYNA one real, ownable, non-decorative signature element rather than relying on the palette alone to read as distinctive.

## Signature Experience Moment

**The Reflection Crossfade.** The moment a visitor taps one Digital Mirror choice and the very next scene visibly, immediately changes to reflect it — new dominant product, new heading voice, new tone — is the one interaction every visitor will remember, because it's the literal mechanism of AAYNA's own name (আয়না, mirror) rather than a decorative reference to it. All three concepts implement this same mechanism; they differ in the visual craft of *how* the choice registers and how the reflection resolves. This is the through-line DESIGN.md already specified (Digital Mirror Panel → Scene III transition) — this pass is about executing it with enough visual conviction that it reads as AAYNA's signature, not a filtered product grid.

---

## Concept A — Editorial Mirror

**Core idea:** Magazine-plate composition. Asymmetric-width "vitrine" panels (not equal ecommerce cards), an oversized cropped letterform per category standing in for missing photography, typography treated as a structural/graphic element crossing toward the seam between zones. Closest to the Prounis reference lesson (tease-then-deliver, named curated moments, restrained type-carries-weight).

- **Desktop:** Scene I is a 40/60 asymmetric field (type lower-left, media right, ivory fade-blend seam) — the corrected Scene I composition from the prior pass, kept as-is since it was founder-approved after the correction round. Scene II's four choice panels are **unequal width** (`1.3fr / 1fr / 1fr / 0.85fr-link`), thin 6px gaps, cropped serif letterform bleeding off each panel's edge. Scene III is a 60/40 dominant-product + stacked-support layout.
- **Mobile:** Scene II panels become a native horizontal scroll-snap row (next panel peeks at the edge). Scene III's supporting products become a horizontal row beneath the full-width hero product. No JS carousel anywhere.
- **Motion:** Load-in fade+translate-up (already in DESIGN.md's Motion System); panel hover is a slow 600ms 1.0→1.03 scale (calmer than the product-card's existing 300ms/1.05); selecting a panel dims the others via a CSS `filter` transition rather than a border/checkmark.
- **Prototype path:** `.frontend-design/aayna/concept-a-editorial-mirror.html`
- **Screenshot path (this session, not committed):** `concept-a-1440-v2.png`, `concept-a-390.png` (scratchpad, reviewed inline)

## Concept B — Cinematic Reflection

**Core idea:** Full-viewport, Apple-pacing-informed scenes. Centered-but-off-axis focal points, background-color transitions between scenes as the primary pacing device (validated directly by the Apple research), smaller/quieter choice panels that scale and dim on selection, a genuine crossfade when Scene III's content updates.

- **Desktop:** Each scene is close to 100vh, one idea at a time — Scene I is centered text on solid burgundy (no image needed to feel intentional), Scene II's panels are small (200×260px) and centered, Scene IV switches to Slate Blue (alternating tone from Scene I, per the Apple research's "background-shift-as-pacing" finding) with a masked concentric-ring reveal.
- **Mobile:** Panels stack centered, full scenes remain close to one-viewport-each.
- **Motion:** The most animation-forward of the three — staggered entrance (kicker → headline → actions, ~80ms offset each, matching the Apple research's staged-entrance finding), panel `scale(1.04)` on selection, Scene III content cross-fades (opacity only, no slide) on every choice change.
- **Honest risk, not resolved here:** repeating a mostly-empty full-viewport centered block six times risks reading as *more* of the "large empty field" the founder already rejected once in Home.jsx's first Scene I attempt — Apple can afford this pacing because every one of those sparse moments is carrying a single hero product photograph; AAYNA doesn't have that photography yet, so several of these scenes are emptier in practice than the Apple reference they're modeled on. Scored down for this reason below, not because the technique itself is wrong.
- **Prototype path:** `.frontend-design/aayna/concept-b-cinematic-reflection.html`
- **Screenshot path:** `concept-b-1440.png`, `concept-b-390.png`

## Concept C — Modern Bengali Atelier

**Core idea:** Bengali typography used as real structural/graphic material (not a small corner watermark) — an oversized আয়না rendering fills Scene I's otherwise-empty field directly, a circular motif in Scene IV frames the tagline's Bangla line, a subtle dot-grain texture warms the whole page. Bordered, tactile tile cards (gold border on selection) rather than borderless vitrines.

- **Desktop:** Scene I's large burgundy field is filled by the oversized আয়না mark itself rather than depending on the fade-blend/letterform-crop technique alone — this incidentally solves the "empty field" problem the most directly of the three concepts, since the Bengali mark *is* the content, not decoration around empty space. Scene II uses a bordered 2×2/1×4 tile grid with a gold inset-border selected state.
- **Mobile:** Tiles become a clean 2×2 grid (not a scroll row) — a genuinely different, valid mobile pattern from A/B, still 44px+ targets.
- **Motion:** Quietest of the three — load-in fade only, tile selection is a border-color transition, no scale/dim tricks.
- **Important constraint respected:** no Bengali category-name translations were invented. Bengali text is limited to what the Brand Book itself already provides verified (আয়না, and the tagline's Bangla rendering) — category labels stay English-only rather than guessing at translations on a real cultural brand asset.
- **Founder-taste flag, not a defect:** this concept leans more culturally forward than A/B. The Brand Book's own audience research skews toward urban, Instagram-fluent, English-first shoppers (Personas A/B) with heritage cues as *reframed*, not foregrounded, motifs — worth an explicit founder gut-check on whether this concept's emphasis matches that intended audience balance, independent of its execution quality.
- **Prototype path:** `.frontend-design/aayna/concept-c-bengali-atelier.html`
- **Screenshot path:** `concept-c-1440.png`, `concept-c-390.png`

---

## Comparison Matrix

Scored qualitatively (High / Medium / Low) against the required criteria, not by "prettiest screenshot":

| Criterion | A — Editorial Mirror | B — Cinematic Reflection | C — Bengali Atelier |
|---|---|---|---|
| AAYNA distinctiveness | **High** | Medium (full-viewport-centered-hero is itself a common template shape) | **High** |
| Brand Book fidelity | High | High | High |
| Storytelling | High | Medium-High | High |
| Digital Mirror meaning | High (dim + crop-letterform reads as clear reflection) | High (scale/tone-shift/crossfade) | Good (border-select is more conventional) |
| Memorability | High | Medium | High |
| Mobile experience | Good (scroll-snap row) | Good (stacked panels) | Good (2×2 grid — most "considered" of the three) |
| Product discoverability | Good | Good | Good |
| Purchase clarity | Good | Good | Good |
| Performance realism | High (pure CSS, no dependency) | High | High |
| Accessibility | Good (verify gold-on-burgundy label contrast in implementation) | Good | Good (bordered tiles give the clearest native focus affordance) |
| Ease of implementation into existing React | **High** — the vitrine panel maps almost directly onto DESIGN.md's already-written Digital Mirror Panel spec | Medium — full-viewport scene restructuring is the biggest rewrite of Home.jsx's current structure | Medium-High |

## Recommended Direction

**Concept A — Editorial Mirror**, with two specific borrowings from the others rather than a blend of all three:

1. From **Concept C**: use the oversized আয়না/letterform-as-content technique to fill Scene I's media field more assertively — it solves the "empty field" problem more directly than the fade-blend approach alone.
2. From **Concept B**: adopt the background-tone-shift-as-pacing device for Scene IV specifically (switch to Slate Blue there instead of staying on Burgundy) — confirmed by the Apple research as a cheap, effective pacing signal, and it gives Blue a real moment on the page per the Brand Book's own "Blue sharpens" usage rule, which the current build underuses.

**Why A over B and C outright:** A scores highest or tied-highest on distinctiveness, memorability, and Digital Mirror clarity, while being the *lowest-risk* to actually build — DESIGN.md already wrote a detailed Digital Mirror Panel spec that Concept A's vitrine is a direct execution of, rather than a competing idea. B's core technique (Apple-informed pacing) is real and worth keeping as a *motion/pacing* input, but its full-viewport-per-scene structure is the concept most likely to recreate the exact "empty field" complaint already raised once, given AAYNA has no photography yet. C is a very close second and arguably more culturally ownable, but its heavier Bengali-forward emphasis is a founder taste call this document shouldn't make unilaterally — flagged for explicit sign-off rather than decided here.

---

## Motion Language

Extends DESIGN.md's existing Motion System table — durations/easings below were the ones actually used and screenshotted in the prototypes, not just proposed:

| Moment | Treatment | Duration/Easing |
|---|---|---|
| Page load-in | Fade + translate-up (8-16px), staggered by ~80-100ms between kicker → headline → CTA | 400-700ms `ease-out` (matches Apple research + UI/UX Pro Max's Scroll Reveal Subtle tier) |
| Digital Mirror panel hover | Slight image scale (1.0→1.03), calmer than product-card hover | 500-600ms ease |
| Digital Mirror panel selection | Dim unselected panels via `filter` (saturate/brightness), no border/checkmark | 500-550ms ease |
| Scene III content update | Cross-fade only (opacity), never a slide/wipe | 300-350ms ease |
| Scene-to-scene background tone | Plain `background` transition, no imagery required | ~1s ease (pacing device, not attention-grabbing) |
| Reduced motion | All of the above collapse to instant/no-animation; only the Scene III content swap itself still happens (it's a state change, not decoration) | — |

No animation library added in any prototype — all three are pure CSS transitions/keyframes plus a small vanilla-JS click handler. Confirms DESIGN.md's performance budget is achievable with the chosen visual direction.

## Responsive Philosophy

All three concepts were designed and screenshotted at 390px *first*, not shrunk from a 1440px design — confirmed by the fact that each concept's mobile layout is a genuinely different composition (scroll-snap row / stacked panels / 2×2 grid), not the same desktop grid with fewer columns. Recommended (Concept A) mobile behavior: horizontal scroll-snap for the Digital Mirror panels (peeking next-panel affordance), stacked hero+horizontal-support-row for Scene III, no JS carousel anywhere, 44px+ touch targets throughout.

## Component Visual Rules

(Applies to the recommended Concept A, informed by what actually rendered well across all three)

- **Digital Mirror Panel**: unequal-width row (desktop) / scroll-snap row (mobile), portrait aspect, cropped-letterform fallback, dim-not-border selected state, real `<button>` markup.
- **Hero Product / Editorial Product**: as specified in DESIGN.md's Product Presentation System — this pass didn't change that spec, it only proved it renders correctly with real product names/prices/discounts.
- **Scene background rhythm**: Ivory (I-text-zone) → Ivory (II) → White (III) → Burgundy-or-Blue, alternating by scene (IV) → Ivory (V) → Burgundy/Ivory (VI, per DESIGN.md, not re-prototyped this pass). Never more than one saturated-color full-bleed scene in a row.
- **Type**: Playfair Display for every headline/product-name/panel-label; DM Sans for body/UI/kicker labels; kicker labels always uppercase, `0.2-0.24em` tracking.
- **Buttons**: one coral text-link primary CTA per scene, never a filled rectangle in an editorial scene (filled coral stays reserved for actual cart/checkout actions, per the existing Product Presentation System's Hero Product Add to Cart).

## What Must Be Deleted From Current UI

Per explicit founder permission (Section 19 of the brief) — customer-facing *presentation* only, not the underlying data/routes/logic:

- Current homepage hero composition (already mid-revision; superseded by whichever concept is selected)
- Current "Shop by Category" tile presentation (superseded by the Digital Mirror Panel)
- The equal-weight four-card homepage product grid sections (New Arrivals/Best Sellers as currently laid out) — replaced by Scene III's dominant+supporting composition
- Current Material Trust three-icon-card presentation — replaced by Scene IV's asymmetric statement layout
- Current three-gradient-rectangle editorial panels — replaced by the richer Fallback World-Building vocabulary already defined in DESIGN.md and proven out further in these prototypes
- "Why Shop With AAYNA" badge-card presentation — visual treatment only; the underlying trust content stays, just not as generic icon cards inside a Scene
- Header/footer visual styling (not architecture) — open to the same visual language, not yet touched in these prototypes

## What Functional Logic Must Be Preserved

Unchanged from DESIGN.md and every prior milestone on this project — restated here because this pass had explicit permission to delete visual markup and that permission does not extend to any of the following:

- Backend, API contracts, routes
- Public/private product-field security (whitelist architecture)
- Order confirmation token requirement
- Track Order dual-verification
- Admin authentication — Admin is untouched entirely
- Checkout: secure order creation, guest checkout, `client_request_id` duplicate protection, the 4-step structure — visual polish only, never storytelling content inside it
- Inventory/stock behavior, payment method architecture
- SEO architecture (meta/OG/JSON-LD/sitemap)
- Product Presentation System's underlying data/cart/stock logic (Milestone 1 of implementation) — only its *visual variants* were explored further here, not its data layer
- CLAUDE.md's claim-safety rules — no new product/service claims were introduced in any prototype; all copy is either Brand-Book-sourced or pulled from real product `short_description` fields

---

## Files Created This Pass

- `AAYNA_FRONTEND_VISION.md` (this file)
- `.frontend-design/aayna/concept-a-editorial-mirror.html`
- `.frontend-design/aayna/concept-b-cinematic-reflection.html`
- `.frontend-design/aayna/concept-c-bengali-atelier.html`
- `.design-research/apple/apple-motion-spacing.md`
- `.gitignore` — added `.frontend-design/`

**Production React files changed: NONE.**
