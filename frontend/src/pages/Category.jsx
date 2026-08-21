import { useParams, Link } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { getProducts, getCategory } from "@/lib/api";
import ProductGrid from "@/components/ProductGrid";
import { useSeo } from "@/lib/seo";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const SORTS = [
  { value: "newest", label: "Newest" },
  { value: "price_low", label: "Price: Low to High" },
  { value: "price_high", label: "Price: High to Low" },
  { value: "best_seller", label: "Best Sellers" },
];

export default function Category() {
  const { slug } = useParams();
  const [sort, setSort] = useState("newest");

  const { data: category } = useQuery({
    queryKey: ["category", slug],
    queryFn: () => getCategory(slug),
  });
  const { data: products = [], isLoading } = useQuery({
    queryKey: ["products", "category", slug, sort],
    queryFn: () => getProducts({ category: slug, sort }),
  });

  useSeo({
    title: category?.name || "Category",
    description: category?.description
      ? `${category.description} Shop ${category?.name || "accessories"} — women's accessories in Bangladesh from AAYNA.`
      : `Shop ${category?.name || "accessories"} — women's accessories in Bangladesh from AAYNA.`,
    image: category?.image_url,
  });

  return (
    <div>
      {/* Compact editorial banner — real category image when set, graceful
          burgundy fallback (never a broken/empty image box) otherwise. */}
      <div className="relative h-40 md:h-56 overflow-hidden bg-aayna-burgundy">
        {category?.image_url ? (
          <img src={category.image_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
        ) : (
          <div className="absolute -right-10 -top-10 w-56 h-56 rounded-full border border-white/15" />
        )}
        <div className="absolute inset-0 bg-aayna-burgundy-dark/45" />
        <div className="relative h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col justify-end pb-6">
          <h1 className="font-display text-3xl md:text-5xl font-bold text-white">
            {category?.name || "Category"}
          </h1>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <nav className="flex items-center gap-1.5 text-xs text-aayna-taupe mb-6">
          <Link to="/" className="hover:text-aayna-burgundy">Home</Link>
          <ChevronRight className="h-3 w-3" />
          <Link to="/shop" className="hover:text-aayna-burgundy">Shop</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="text-aayna-charcoal">{category?.name || slug}</span>
        </nav>

        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
          {category?.description ? (
            <p className="text-aayna-taupe max-w-2xl">{category.description}</p>
          ) : (
            <span />
          )}
          <div className="w-full md:w-56">
            <Select value={sort} onValueChange={setSort}>
              <SelectTrigger data-testid="category-sort" className="bg-white border-aayna-beige h-11">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORTS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <p className="text-sm text-aayna-taupe mb-4">{products.length} products</p>
        <ProductGrid products={products} loading={isLoading} emptyText="No products in this category yet." />
      </div>
    </div>
  );
}
