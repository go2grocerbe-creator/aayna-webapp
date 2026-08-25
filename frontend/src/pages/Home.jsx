import { Link } from "react-router-dom";
import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getProducts } from "@/lib/api";
import { useSettings, useCategories } from "@/hooks/useStore";
import ProductCard from "@/components/ProductCard";
import ProductImage from "@/components/ProductImage";
import { useSeo } from "@/lib/seo";
import { effectivePrice, formatBDT, isOutOfStock } from "@/lib/format";

// The Digital Mirror homepage (D1.6). Replaces the previous module-stack
// homepage (Shop by Category grid / New Arrivals grid / Material Trust
// block / Best Sellers grid / three gradient editorial rectangles / Why
// Shop With AAYNA badges) with the three-scene Arrival -> Reflection ->
// Your Edit sequence approved in concept-d1-6-single-hover-letter.html.
//
// Scoped to the three curated categories only (Earrings/Necklaces/Rings) -
// Hair Accessories and any zero-inventory category are intentionally not
// part of this experience, though they remain fully reachable via the
// header/footer category links, which are unchanged.
const MIRROR_CATEGORIES = [
  { slug: "earrings", label: "Earrings", letter: "E" },
  { slug: "necklaces", label: "Necklaces", letter: "N" },
  { slug: "rings", label: "Rings", letter: "R" },
];
const PREF_KEY = "aayna.selectedCategory";

function useLocalPreference() {
  const [preference, setPreference] = useState(() => {
    try {
      return localStorage.getItem(PREF_KEY) || null;
    } catch {
      return null;
    }
  });
  const choose = useCallback((slug) => {
    setPreference(slug);
    try {
      if (slug) localStorage.setItem(PREF_KEY, slug);
      else localStorage.removeItem(PREF_KEY);
    } catch {
      /* localStorage unavailable — preference just won't persist */
    }
  }, []);
  return [preference, choose];
}

export default function Home() {
  const { data: settings } = useSettings();
  const { data: allCategories = [] } = useCategories();
  const availableMirror = MIRROR_CATEGORIES.filter((c) =>
    allCategories.some((real) => real.slug === c.slug && (real.product_count || 0) > 0)
  );
  const availableSlugs = new Set(availableMirror.map((c) => c.slug));

  const [preference, choosePreference] = useLocalPreference();
  const [hovered, setHovered] = useState(null); // category slug currently hovered/focused, or null
  // Derived, not stored state — avoids an effect + a one-frame flicker back
  // to the unpersonalized default before the effect would otherwise run,
  // and only resolves to a category still actually shown in the nav.
  const committed = preference && availableSlugs.has(preference) ? preference : null;

  // One lightweight query per curated category for the Reflection preview
  // panel — real product data, cached, no per-hover network wait. Called
  // explicitly (not in a loop/map) since hooks must run in a fixed order;
  // MIRROR_CATEGORIES has exactly three entries.
  // limit: 3, not 1 - a sold-out piece shouldn't be the one thing a visitor
  // sees when previewing a category, so the first in-stock item among a
  // small candidate set leads (falls back to the top pick if the whole
  // category happens to be out of stock).
  const preferInStock = (data) => data.find((p) => !isOutOfStock(p)) || data[0];
  const earringsPreview = useQuery({
    queryKey: ["products", "mirror-preview", "earrings"],
    queryFn: () => getProducts({ category: "earrings", sort: "best_seller", limit: 3 }),
    select: preferInStock,
    staleTime: 5 * 60_000,
  });
  const necklacesPreview = useQuery({
    queryKey: ["products", "mirror-preview", "necklaces"],
    queryFn: () => getProducts({ category: "necklaces", sort: "best_seller", limit: 3 }),
    select: preferInStock,
    staleTime: 5 * 60_000,
  });
  const ringsPreview = useQuery({
    queryKey: ["products", "mirror-preview", "rings"],
    queryFn: () => getProducts({ category: "rings", sort: "best_seller", limit: 3 }),
    select: preferInStock,
    staleTime: 5 * 60_000,
  });
  const previewQueries = { earrings: earringsPreview, necklaces: necklacesPreview, rings: ringsPreview };

  const activeSlug = hovered || committed;
  const previewProduct = activeSlug ? previewQueries[activeSlug]?.data : null;

  const { data: editProducts = [] } = useQuery({
    queryKey: ["products", "your-edit", committed],
    queryFn: () =>
      committed
        ? getProducts({ category: committed, sort: "best_seller", limit: 4 })
        : getProducts({ new_arrival: true, limit: 4 }),
    // Featuring a sold-out piece as the hero recommendation isn't a real
    // storefront experience, so an in-stock item leads whenever one exists
    // in the fetched set - a stable reorder, not a different query/limit.
    select: (data) => [...data].sort((a, b) => Number(isOutOfStock(a)) - Number(isOutOfStock(b))),
  });
  const [heroProduct, ...supportProducts] = editProducts;

  useSeo({
    description:
      settings?.hero_subtitle ||
      "AAYNA — accessible premium jewelry for women in Bangladesh. Earrings, necklaces, rings and more. Cash on delivery available.",
  });

  const selectCategory = (slug) => {
    choosePreference(slug);
    setHovered(null);
  };

  return (
    <div className="bg-aayna-cream">
      {/* ================= SCENE I — ARRIVAL ================= */}
      <section className="relative min-h-screen flex flex-col justify-end overflow-hidden">
        <div
          aria-hidden="true"
          className="absolute rounded-full border border-aayna-burgundy/[0.13] w-[600px] h-[600px] left-[44%] -top-[18%]"
        />
        <div
          aria-hidden="true"
          className="absolute rounded-full border border-aayna-taupe/10 w-[760px] h-[760px] -right-[28%] -bottom-[40%]"
        />
        <span
          aria-hidden="true"
          className="font-bangla absolute right-[3%] bottom-[4%] text-[11vw] leading-[0.8] text-aayna-burgundy/[0.04] select-none pointer-events-none"
        >
          আয়না
        </span>
        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full pt-32 sm:pt-36 md:pt-40 pb-16 md:pb-24">
          <div className="max-w-xl">
            <p className="text-aayna-burgundy font-bold text-xs tracking-[0.24em] uppercase mb-4">
              {(settings?.brand_name || "AAYNA").toUpperCase()} · Bangladesh
            </p>
            <h1 className="font-display font-semibold leading-[0.98] tracking-tight">
              {settings?.hero_headline ? (
                <span className="block text-aayna-charcoal text-[46px] sm:text-6xl md:text-7xl lg:text-[108px]">
                  {settings.hero_headline}
                </span>
              ) : (
                <>
                  <span className="block text-aayna-charcoal text-[46px] sm:text-6xl md:text-7xl lg:text-[108px]">
                    Reflect Your
                  </span>
                  <span className="block text-aayna-burgundy text-[52px] sm:text-7xl md:text-8xl lg:text-[124px] mt-1">
                    Aura.
                  </span>
                </>
              )}
            </h1>
            <p className="mt-4 text-sm text-aayna-taupe">
              <span className="font-bangla text-aayna-burgundy mr-1.5">আয়না</span>— mirror.
            </p>
            <a
              href="#reflection"
              data-testid="hero-shop-now"
              className="group inline-flex items-center gap-2 mt-7 text-aayna-coral-dark text-base font-semibold w-fit border-b border-transparent hover:border-current hover:gap-3 transition-all"
            >
              Enter the Edit
              <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>
        <div className="absolute left-1/2 bottom-6 -translate-x-1/2 z-10 flex flex-col items-center gap-2 text-aayna-taupe">
          <span className="text-[10px] uppercase tracking-[0.2em]">Reflect</span>
          <span aria-hidden="true" className="w-px h-6 bg-gradient-to-b from-aayna-taupe to-transparent" />
        </div>
      </section>

      {/* ================= SCENE II — REFLECTION ================= */}
      <section id="reflection" className="relative py-24 md:py-28">
        {/* One shared reactive background letter — desktop hover/focus only,
            driven purely by `hovered` (never `committed`), so it can never
            be pinned by a selection and never appears on the Your Edit
            scene below. React state, not a CSS :has() hack. Clipped to its
            own decorative-only wrapper (not the section itself) so it can
            never affect the section's scrollable height or bleed sideways. */}
        <div aria-hidden="true" className="hidden md:block absolute inset-0 overflow-hidden pointer-events-none">
          <span
            className="absolute left-0 -top-[4%] font-display font-bold leading-[0.78] select-none transition-opacity duration-300"
            style={{
              fontSize: "36vw",
              color:
                hovered === "necklaces" ? "#1A365D" : hovered === "rings" ? "#C85A42" : "#5A0E1A",
              opacity: hovered ? 0.06 : 0,
            }}
          >
            {MIRROR_CATEGORIES.find((c) => c.slug === hovered)?.letter}
          </span>
        </div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-12 gap-x-8">
          <div className="md:col-span-7">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2.5">
              The Digital Mirror
            </p>
            <h2 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark">
              What are you drawn to today?
            </h2>
            <p className="font-display italic text-aayna-taupe text-sm mt-3 max-w-md">
              A mirror doesn't create you. It reveals you.
            </p>

            <div className="mt-11 flex flex-col gap-1.5">
              {availableMirror.map((c, i) => (
                <button
                  key={c.slug}
                  type="button"
                  data-testid={`mirror-category-${c.slug}`}
                  onMouseEnter={() => setHovered(c.slug)}
                  onFocus={() => setHovered(c.slug)}
                  onMouseLeave={() => setHovered(null)}
                  onBlur={() => setHovered(null)}
                  onClick={() => selectCategory(c.slug)}
                  style={{ marginLeft: i === 1 ? "14%" : i === 2 ? "4%" : 0 }}
                  className={`font-display font-bold text-left min-h-[44px] py-2.5 transition-opacity w-fit ${
                    i === 1 ? "text-aayna-burgundy" : "text-aayna-charcoal"
                  } ${
                    committed && committed !== c.slug && hovered !== c.slug ? "opacity-40" : "opacity-100"
                  } text-4xl sm:text-5xl md:text-[54px]`}
                >
                  {c.label}
                </button>
              ))}
              <Link
                to="/shop"
                data-testid="mirror-show-everything"
                onClick={() => choosePreference(null)}
                className="mt-5 text-sm font-semibold text-aayna-taupe hover:text-aayna-burgundy transition-colors w-fit min-h-[44px] flex items-center"
              >
                Show me everything →
              </Link>
            </div>
          </div>

          {/* Response field — real product, revealed on hover/focus only */}
          <div className="hidden md:flex md:col-span-5 flex-col justify-center">
            {previewProduct ? (
              <div key={activeSlug} className="animate-fade-up">
                <div className="relative aspect-[3/4] border border-aayna-beige overflow-hidden">
                  <ProductImage
                    src={previewProduct.images?.[0]?.image_url}
                    alt={previewProduct.images?.[0]?.alt_text || previewProduct.product_name}
                    className="absolute inset-0"
                    iconClassName="h-8 w-8"
                  />
                </div>
                <p className="mt-3 text-[11px] uppercase tracking-[0.14em] text-aayna-taupe">
                  Previewing — {MIRROR_CATEGORIES.find((c) => c.slug === activeSlug)?.label}
                </p>
                <p className="font-display italic text-aayna-charcoal">{previewProduct.product_name}</p>
                <p className="font-bold text-aayna-burgundy text-sm">{formatBDT(effectivePrice(previewProduct))}</p>
              </div>
            ) : (
              <p className="font-display italic text-aayna-taupe text-sm">Explore an edit</p>
            )}
          </div>
        </div>
      </section>

      {/* ================= SCENE III — YOUR EDIT ================= */}
      <section className="relative py-20 md:py-24 border-t border-aayna-beige">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-baseline justify-between gap-4 flex-wrap mb-10">
            <div>
              <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase">Your Reflection</p>
              <p className="font-display italic text-aayna-burgundy text-lg mt-1">
                {committed
                  ? `Because you're drawn to ${MIRROR_CATEGORIES.find((c) => c.slug === committed)?.label}`
                  : "New This Season"}
              </p>
            </div>
            {committed && (
              <button
                type="button"
                onClick={() => choosePreference(null)}
                data-testid="mirror-reset"
                className="text-xs text-aayna-taupe underline underline-offset-2 hover:text-aayna-burgundy min-h-[44px]"
              >
                Reset your preference
              </button>
            )}
          </div>

          {heroProduct ? (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8 md:gap-10">
              <div className="md:col-span-7">
                <ProductCard product={heroProduct} variant="hero" />
              </div>
              <div className="md:col-span-5 flex flex-row md:flex-col gap-5 overflow-x-auto md:overflow-visible">
                {supportProducts.slice(0, 3).map((p) => (
                  <div key={p.id} className="flex-none w-40 md:w-auto">
                    <ProductCard product={p} variant="editorial" />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-aayna-taupe text-sm">No products to show yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
