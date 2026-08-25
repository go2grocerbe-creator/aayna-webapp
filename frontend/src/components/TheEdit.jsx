import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";

// Shared product-discovery presentation (D2 "The Edit", concept-d2-the-edit.html).
// Used by both Shop.jsx (category = query param, unlocked) and Category.jsx
// (category = route param, locked) so there is exactly one discovery design,
// not two - the only difference between the two call sites is which category
// is active and whether the visitor can switch away from it inline.
//
// Reuses ProductCard's existing commerce/editorial/hero variants and their
// shared cart/stock/price logic - this component only decides layout roles
// and fetches real product data; it never reimplements pricing or cart
// behavior itself.
const SORTS = [
  { value: "newest", label: "Newest" },
  { value: "price_low", label: "Price, low to high" },
  { value: "price_high", label: "Price, high to low" },
];

// Deterministic 6-item editorial rhythm, one full 12-column row per beat:
//   pos 0 (featured, span 7) + pos 1 (span 5)        = row of 12
//   pos 2 + pos 3 + pos 4 (three equal, span 4 each) = row of 12
//   pos 5 (wide, span 12 alone)                      = row of 12
// Never randomized; the cycle repeats for longer catalogues.
function roleForPosition(pos) {
  if (pos === 0) return { variant: "hero", span: "col-span-2 md:col-span-7" };
  if (pos === 1) return { variant: "editorial", span: "col-span-1 md:col-span-5" };
  if (pos === 5) return { variant: "editorial", span: "col-span-2 md:col-span-12" };
  return { variant: "editorial", span: "col-span-1 md:col-span-4" };
}

function CategoryLetter({ hovered }) {
  const color = hovered === "necklaces" ? "#1A365D" : hovered === "rings" ? "#C85A42" : "#5A0E1A";
  const letter = { earrings: "E", necklaces: "N", rings: "R" }[hovered];
  return (
    <div aria-hidden="true" className="hidden md:block absolute inset-0 overflow-hidden pointer-events-none">
      <span
        className="absolute left-[2%] -top-[30%] font-display font-bold leading-[0.8] select-none transition-opacity duration-300"
        style={{ fontSize: "20vw", color, opacity: hovered ? 0.045 : 0 }}
      >
        {letter}
      </span>
    </div>
  );
}

export default function TheEdit({
  categories, // real categories from useCategories(), pre-filtered to Earrings/Necklaces/Rings by the caller
  activeCategory, // slug or null ("All")
  onCategoryChange, // (slug|null) => void — Shop.jsx updates a query param, Category.jsx navigates
  contextLabel, // optional "Your Edit — Earrings"-style line when arriving with a category preselected
  search, // optional search term (Shop.jsx's ?search=... — preserves the header search bar's existing behavior
}) {
  const [sort, setSort] = useState("newest");
  const [hovered, setHovered] = useState(null);

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["products", "the-edit", activeCategory, sort, search],
    queryFn: () =>
      getProducts({
        sort,
        ...(activeCategory ? { category: activeCategory } : {}),
        ...(search ? { search } : {}),
      }),
  });

  return (
    <div className="bg-aayna-cream">
      <section className="relative pt-9 md:pt-12 pb-7 md:pb-9">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">AAYNA · The Edit</p>
          <h1 className="font-display font-semibold text-3xl md:text-5xl text-aayna-burgundy-dark">The Edit</h1>
          <p className="text-aayna-taupe text-sm mt-2 max-w-lg">
            {search
              ? `Showing results for "${search}"`
              : "Earrings, necklaces and rings — the current AAYNA edit, ready to wear."}
          </p>
          {contextLabel && (
            <p className="font-display italic text-aayna-burgundy text-sm mt-1.5">{contextLabel}</p>
          )}

          <div className="relative mt-6 pt-4 border-t border-aayna-beige flex flex-wrap items-center justify-between gap-3.5">
            <CategoryLetter hovered={hovered} />
            <nav className="relative flex flex-wrap gap-5" aria-label="Filter by category">
              <button
                type="button"
                onClick={() => onCategoryChange(null)}
                aria-pressed={!activeCategory}
                className={`font-display font-semibold text-base md:text-xl min-h-[44px] py-1 border-b transition-colors ${
                  !activeCategory ? "text-aayna-burgundy border-aayna-burgundy" : "text-aayna-taupe border-transparent hover:text-aayna-charcoal"
                }`}
              >
                All
              </button>
              {categories.map((c) => (
                <button
                  key={c.slug}
                  type="button"
                  data-testid={`the-edit-cat-${c.slug}`}
                  onMouseEnter={() => setHovered(c.slug)}
                  onFocus={() => setHovered(c.slug)}
                  onMouseLeave={() => setHovered(null)}
                  onBlur={() => setHovered(null)}
                  onClick={() => onCategoryChange(c.slug)}
                  aria-pressed={activeCategory === c.slug}
                  className={`font-display font-semibold text-base md:text-xl min-h-[44px] py-1 border-b transition-colors ${
                    activeCategory === c.slug
                      ? "text-aayna-burgundy border-aayna-burgundy"
                      : "text-aayna-taupe border-transparent hover:text-aayna-charcoal"
                  }`}
                >
                  {c.name}
                </button>
              ))}
            </nav>
            <div className="relative flex items-center gap-4 text-xs text-aayna-taupe">
              <span>{products.length} piece{products.length === 1 ? "" : "s"}</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                aria-label="Sort"
                className="bg-transparent border-0 underline underline-offset-2 cursor-pointer text-aayna-charcoal"
              >
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    Sort: {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-12 gap-4 md:gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={`bg-aayna-mist animate-pulse aspect-[4/5] ${i === 0 ? "col-span-2 md:col-span-6" : "md:col-span-3"}`} />
            ))}
          </div>
        ) : products.length === 0 ? (
          <p className="text-aayna-taupe text-sm py-16 text-center">No pieces in this edit yet.</p>
        ) : (
          <TheEditRows products={products} />
        )}
      </section>
    </div>
  );
}

// Grouped into 6-item rows so each row's roles form one coherent unit
// (featured + 4 standard + 1 wide) rather than one long uninterrupted grid.
function TheEditRows({ products }) {
  const rows = [];
  for (let i = 0; i < products.length; i += 6) rows.push(products.slice(i, i + 6));

  return (
    <div className="flex flex-col gap-8 md:gap-10">
      {rows.map((row, rowIndex) => (
        <div key={rowIndex} className="grid grid-cols-2 md:grid-cols-12 gap-4 md:gap-6">
          {row.map((p, i) => {
            const { variant, span } = roleForPosition(i);
            return (
              <div key={p.id} className={span}>
                <ProductCard product={p} variant={variant} />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
