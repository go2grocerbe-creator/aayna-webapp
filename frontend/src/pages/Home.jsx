import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Gem, Layers, HeartHandshake, ChevronDown } from "lucide-react";
import { getProducts } from "@/lib/api";
import { useSettings, useCategories } from "@/hooks/useStore";
import ProductGrid from "@/components/ProductGrid";
import TrustBadges from "@/components/TrustBadges";
import { useSeo } from "@/lib/seo";

function SectionHeading({ title, subtitle, link, linkLabel }) {
  return (
    <div className="flex items-end justify-between mb-7 md:mb-9">
      <div>
        <h2 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal">{title}</h2>
        {subtitle && <p className="text-aayna-taupe mt-2 text-sm md:text-base max-w-xl">{subtitle}</p>}
      </div>
      {link && (
        <Link to={link} className="hidden sm:flex items-center gap-1.5 text-sm font-medium text-aayna-burgundy hover:gap-2.5 transition-all whitespace-nowrap">
          {linkLabel} <ArrowRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

// Scene I (Arrival) fallback world — DESIGN.md "Fallback World-Building".
// No campaign photography exists yet, so this must look like an intentional
// AAYNA artboard, not a placeholder: concentric rings + faint "আয়না"
// watermark (from the Brand Book's own cover/quote-block device), an
// oversized cropped letterform (typography-as-image), a paired/echoed ring
// pair (a restrained, structural nod to reflection), and a thin gold hairline
// rule. CSS/type only — no images, no WebGL, no glassmorphism, no literal
// mirror chrome.
function HeroFallback() {
  return (
    <div className="absolute inset-0 bg-aayna-burgundy overflow-hidden">
      <div className="absolute -right-16 -top-16 w-72 h-72 rounded-full border border-white/15" />
      <div className="absolute right-10 top-1/3 w-44 h-44 rounded-full border border-white/15" />
      {/* paired/echoed shape — two offset thin rings, positioned toward the seam
          so they relate to the transition into the type zone rather than
          sitting isolated in a corner */}
      <div className="absolute left-6 md:left-10 bottom-28 w-24 h-24 rounded-full border border-aayna-gold/25" />
      <div className="absolute left-12 md:left-16 bottom-20 w-24 h-24 rounded-full border border-aayna-gold/15" />
      {/* oversized cropped letterform — type as visual material, positioned at
          the left (seam) edge so it approaches the type zone rather than
          sitting inert in the field's outer corner (Scene I correction pass) */}
      <span
        aria-hidden="true"
        className="absolute -bottom-16 -left-16 md:-left-24 font-display text-[16rem] leading-none text-white/[0.05] select-none"
      >
        A
      </span>
      <span
        aria-hidden="true"
        className="absolute -bottom-10 -right-4 font-display text-[10rem] leading-none text-white/5 select-none"
      >
        আয়না
      </span>
      {/* thin hairline rule */}
      <div className="absolute right-16 bottom-16 w-16 h-px bg-aayna-gold/40" />
    </div>
  );
}

export default function Home() {
  const { data: settings } = useSettings();
  const { data: allCategories = [] } = useCategories();
  // Merchandising surfaces only show categories that actually have something
  // to buy right now (Visual QA Fix Sprint item 4) - the category itself
  // stays untouched in Admin/DB either way, this is display-only.
  const categories = allCategories.filter((c) => (c.product_count || 0) > 0);
  const { data: newArrivals = [], isLoading: loadingNew } = useQuery({
    queryKey: ["products", "new"],
    queryFn: () => getProducts({ new_arrival: true, limit: 8 }),
  });
  const { data: bestSellers = [], isLoading: loadingBest } = useQuery({
    queryKey: ["products", "best"],
    queryFn: () => getProducts({ best_seller: true, limit: 8 }),
  });

  useSeo({
    description:
      settings?.hero_subtitle ||
      "AAYNA — accessible premium jewelry for women in Bangladesh. Earrings, necklaces, rings and more. Cash on delivery available.",
  });

  return (
    <div>
      {/* SCENE I — ARRIVAL (DESIGN.md Experience Storyboard, Scene I correction
          pass). Media occupies a true full-bleed rectangle via `absolute
          inset-0 md:left-[40%]` rather than a CSS-grid column — a grid
          column's auto-sized row was collapsing to the (short) text content's
          height, leaving unfilled space above the image. This approach
          guarantees the media field fills exactly top:0/right:0/bottom:0/
          left:40% with no dependency on sibling content height. The type
          block shares the header's own `max-w-7xl mx-auto px-4 sm:px-6
          lg:px-8` container so the kicker/headline/CTA align to the same
          left edge as the header logo, instead of floating at an unrelated
          inset. An ivory fade-blend at the media zone's seam edge (rather
          than a hard color cut) plus the fallback's letterform/rings
          positioned toward that same edge make the scene read as one
          composed field instead of two independent rectangles. */}
      <section className="relative bg-aayna-burgundy md:bg-aayna-cream overflow-hidden h-[82vh] min-h-[560px] md:h-[90vh] md:min-h-[640px]">
        {/* Media layer — full-bleed rectangle, right 60% on desktop */}
        <div className="absolute inset-0 md:left-[40%] z-0">
          {settings?.hero_image_url ? (
            <img
              src={settings.hero_image_url}
              alt="AAYNA accessories"
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            <HeroFallback />
          )}
          {/* mobile legibility scrim behind the lower text block */}
          <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-aayna-burgundy-dark/90 via-aayna-burgundy-dark/40 to-transparent md:hidden" />
          {/* ivory fade-blend at the seam edge — the two zones dissolve into
              one field instead of meeting at a hard, "two rectangles" cut */}
          <div className="hidden md:block absolute inset-y-0 left-0 w-28 lg:w-36 bg-gradient-to-r from-aayna-cream to-transparent" />
        </div>

        {/* Thin seam rule, drawn on top of the fade-blend */}
        <div className="hidden md:block absolute inset-y-0 left-[40%] w-px bg-aayna-gold/40 z-[1]" />

        {/* Type layer — same container system as the header, so the kicker/
            headline/CTA align to the logo's left edge, not a floating inset */}
        <div className="relative z-10 h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="h-full flex flex-col justify-end md:max-w-[38%] pb-14 sm:pb-16 md:pb-24 animate-fade-up">
            <p className="text-aayna-gold md:text-aayna-burgundy font-medium text-xs sm:text-sm tracking-[0.2em] uppercase mb-3">
              {(settings?.brand_name || "AAYNA").toUpperCase()} · Bangladesh
            </p>
            <h1 className="font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-semibold text-white md:text-aayna-charcoal leading-[1.03]">
              {settings?.hero_headline || "Reflect Your Aura."}
            </h1>
            <Link
              to="/shop"
              data-testid="hero-shop-now"
              className="group inline-flex items-center gap-2 mt-7 text-white md:text-aayna-coral text-base sm:text-lg font-semibold w-fit border-b border-transparent hover:border-current transition-colors"
            >
              Shop Now
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>

        {/* Scroll cue — static, no bounce/loop; respects prefers-reduced-motion
            by simply not animating (it never animated to begin with). */}
        {/* Positioned at 50% of the full section width, which always falls
            inside the media zone (40-100%) on desktop too - stays white/70
            at every breakpoint rather than switching to a dark color that
            would lose contrast against the burgundy/photo background here. */}
        <div className="flex absolute bottom-5 md:bottom-6 left-1/2 -translate-x-1/2 flex-col items-center gap-1.5 text-white/70 z-10">
          <span className="text-[10px] uppercase tracking-[0.2em]">Reflect</span>
          <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
        </div>
      </section>

      {/* Shop by Category */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
        <SectionHeading title="Shop by Category" subtitle="Find your everyday favourites." />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
          {categories.map((c) => (
            <Link
              key={c.slug}
              to={`/category/${c.slug}`}
              data-testid={`home-category-${c.slug}`}
              className="group relative overflow-hidden aspect-[4/3] bg-aayna-cream"
            >
              {c.image_url ? (
                <img src={c.image_url} alt={c.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              ) : (
                <div className="w-full h-full bg-aayna-cream flex items-center justify-center">
                  <Gem className="h-8 w-8 text-aayna-burgundy/40" />
                </div>
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-aayna-burgundy-dark/60 to-transparent" />
              <div className="absolute bottom-0 left-0 p-4 md:p-5">
                <h3 className="font-display text-xl md:text-2xl font-bold text-white">{c.name}</h3>
                <span className="text-white/85 text-xs md:text-sm">{c.product_count} items</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* New Arrivals */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-14 md:pb-20">
        <SectionHeading title="New Arrivals" subtitle="Fresh picks just added to the collection." link="/shop" linkLabel="View all" />
        <ProductGrid products={newArrivals.slice(0, 8)} loading={loadingNew} />
      </section>

      {/* Material / brand-proof — brand-level Material Trust positioning only.
          No per-SKU technical claims (PVD/316L/waterproof/hypoallergenic) are
          made here; those require SKU-level supplier evidence per CLAUDE.md
          and only belong on a product page once verified. */}
      <section className="bg-aayna-burgundy">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
          <div className="max-w-2xl">
            <p className="text-aayna-gold text-xs font-bold tracking-[0.2em] uppercase mb-3">Material Trust</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-white leading-tight">
              Made for how you actually wear jewelry.
            </h2>
            <p className="text-white/70 mt-4 text-base md:text-lg">
              Humidity, long days, layering, the odd nap with your earrings still on — we choose finishes
              built for real wear, not just display cases. Every piece lists what it's actually made from.
            </p>
          </div>
          <div className="grid sm:grid-cols-3 gap-6 md:gap-8 mt-10 md:mt-12">
            <div className="border-t-2 border-aayna-gold/60 pt-5">
              <Gem className="h-5 w-5 text-aayna-gold mb-3" />
              <h3 className="font-display text-lg text-white font-semibold">Material, stated plainly</h3>
              <p className="text-white/60 text-sm mt-1.5 leading-relaxed">
                Each product page lists the actual base material — no guessing what's under the finish.
              </p>
            </div>
            <div className="border-t-2 border-aayna-gold/60 pt-5">
              <Layers className="h-5 w-5 text-aayna-gold mb-3" />
              <h3 className="font-display text-lg text-white font-semibold">Everyday-first design</h3>
              <p className="text-white/60 text-sm mt-1.5 leading-relaxed">
                Pieces sized and finished for daily rotation, not just a single occasion.
              </p>
            </div>
            <div className="border-t-2 border-aayna-gold/60 pt-5">
              <HeartHandshake className="h-5 w-5 text-aayna-gold mb-3" />
              <h3 className="font-display text-lg text-white font-semibold">Checked before it ships</h3>
              <p className="text-white/60 text-sm mt-1.5 leading-relaxed">
                Every order is quality-checked before dispatch from our Bangladesh team.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Best Sellers */}
      <section className="bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
          <SectionHeading title="Best Sellers" subtitle="Loved by our customers across Bangladesh." link="/shop" linkLabel="View all" />
          <ProductGrid products={bestSellers.slice(0, 8)} loading={loadingBest} />
        </div>
      </section>

      {/* Editorial / styling moment — abstract duotone panels rather than
          stock "luxury jewelry" photography we don't have yet (Brand Book:
          avoid generic stock language). Real campaign photography can replace
          these panels directly later without changing the layout. */}
      <section className="border-t border-aayna-beige">
        <div className="grid sm:grid-cols-3">
          <div className="relative aspect-[4/5] sm:aspect-auto sm:h-96 overflow-hidden bg-gradient-to-br from-aayna-burgundy-dark via-aayna-burgundy to-[#a8503a] flex items-end p-6">
            <div className="relative z-10">
              <span className="block text-white/60 text-[11px] uppercase tracking-[0.2em]">Heritage Reframed</span>
              <strong className="block font-display text-2xl text-white mt-1.5 leading-tight">Modern jhumka,<br />new proportion.</strong>
            </div>
          </div>
          <div className="relative aspect-[4/5] sm:aspect-auto sm:h-96 overflow-hidden bg-gradient-to-br from-aayna-blue via-[#274a75] to-aayna-mist flex items-end p-6">
            <div className="relative z-10">
              <span className="block text-white/70 text-[11px] uppercase tracking-[0.2em]">Everyday Sculptural</span>
              <strong className="block font-display text-2xl text-white mt-1.5 leading-tight">Layer it,<br />your way.</strong>
            </div>
          </div>
          <div className="relative aspect-[4/5] sm:aspect-auto sm:h-96 overflow-hidden bg-gradient-to-br from-aayna-coral via-[#c85a3f] to-aayna-burgundy-dark flex items-end p-6">
            <div className="relative z-10">
              <span className="block text-white/70 text-[11px] uppercase tracking-[0.2em]">Reflection</span>
              <strong className="block font-display text-2xl text-white mt-1.5 leading-tight">Reflect<br />Your Aura.</strong>
            </div>
          </div>
        </div>
      </section>

      {/* Trust, care & delivery */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
        <div className="text-center mb-9">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal">Why Shop With AAYNA</h2>
          <p className="text-aayna-taupe mt-2">Pretty pieces, fair prices, and a shopping experience you can trust.</p>
        </div>
        <TrustBadges />
      </section>
    </div>
  );
}
