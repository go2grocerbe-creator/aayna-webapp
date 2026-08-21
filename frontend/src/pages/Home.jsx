import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Gem, Layers, HeartHandshake } from "lucide-react";
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

// Graceful hero fallback for when no campaign/product image is set yet
// (Section 22: hero must never depend on one exact image existing). Built
// from the Brand Book's own cover-page motif: concentric rings + a faint
// Bangla "আয়না" watermark (the book uses the identical device in its pull
// quotes), so it reads as intentional brand texture, not a broken image box.
function HeroFallback() {
  return (
    <div className="absolute inset-0 bg-aayna-burgundy overflow-hidden">
      <div className="absolute -right-16 -top-16 w-72 h-72 rounded-full border border-white/15" />
      <div className="absolute right-10 top-1/3 w-44 h-44 rounded-full border border-white/15" />
      <span
        aria-hidden="true"
        className="absolute -bottom-10 -right-4 font-display text-[10rem] leading-none text-white/5 select-none"
      >
        আয়না
      </span>
    </div>
  );
}

export default function Home() {
  const { data: settings } = useSettings();
  const { data: categories = [] } = useCategories();
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
      "AAYNA — trendy, affordable women's accessories in Bangladesh. Earrings, necklaces, rings and more. Cash on delivery available.",
  });

  const secondaryHeroLink = categories[0] ? `/category/${categories[0].slug}` : "/shop";
  const secondaryHeroLabel = categories[0] ? `Explore ${categories[0].name}` : "Explore the Collection";

  return (
    <div>
      {/* Hero */}
      <section className="relative bg-aayna-mist overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid md:grid-cols-2 items-center gap-8 py-10 md:py-0">
          <div className="order-2 md:order-1 md:py-24 animate-fade-up">
            <p className="text-aayna-burgundy font-medium text-sm tracking-[0.15em] uppercase mb-3">
              {settings?.brand_name || "AAYNA"} · Bangladesh
            </p>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold text-aayna-charcoal leading-[1.08]">
              {settings?.hero_headline || "Everyday Luxury, Reflected."}
            </h1>
            <p className="mt-5 text-base md:text-lg text-aayna-taupe max-w-md">
              {settings?.hero_subtitle ||
                "Beautiful enough to notice. Easy enough to live in. Personal enough to feel like yours."}
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-8">
              <Link
                to="/shop"
                data-testid="hero-shop-now"
                className="h-12 px-8 bg-aayna-coral text-white font-semibold inline-flex items-center justify-center hover:bg-aayna-coral-dark transition-colors"
              >
                Shop Now
              </Link>
              <Link
                to={secondaryHeroLink}
                className="h-12 px-8 border border-aayna-burgundy text-aayna-burgundy font-semibold inline-flex items-center justify-center hover:bg-white transition-colors"
              >
                {secondaryHeroLabel}
              </Link>
            </div>
          </div>
          <div className="order-1 md:order-2 relative h-64 sm:h-80 md:h-[480px]">
            {settings?.hero_image_url ? (
              <img
                src={settings.hero_image_url}
                alt="AAYNA accessories"
                className="absolute inset-0 w-full h-full object-cover"
              />
            ) : (
              <HeroFallback />
            )}
          </div>
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
              className="group relative overflow-hidden aspect-[4/3] bg-aayna-mist"
            >
              {c.image_url ? (
                <img src={c.image_url} alt={c.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              ) : (
                <div className="w-full h-full bg-aayna-mist flex items-center justify-center">
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
