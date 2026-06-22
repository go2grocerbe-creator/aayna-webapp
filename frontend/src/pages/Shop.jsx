import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getProducts } from "@/lib/api";
import { useCategories } from "@/hooks/useStore";
import ProductGrid from "@/components/ProductGrid";
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

export default function Shop() {
  const [params, setParams] = useSearchParams();
  const { data: categories = [] } = useCategories();

  const category = params.get("category") || "all";
  const sort = params.get("sort") || "newest";
  const search = params.get("search") || "";

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["products", "shop", category, sort, search],
    queryFn: () =>
      getProducts({
        sort,
        ...(category !== "all" ? { category } : {}),
        ...(search ? { search } : {}),
      }),
  });

  const updateParam = (key, value) => {
    const next = new URLSearchParams(params);
    if (value && value !== "all") next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
      <div className="mb-8">
        <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal">Shop All</h1>
        <p className="text-aayna-taupe mt-2">
          {search ? `Showing results for "${search}"` : "Browse our full collection of accessories."}
        </p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-8">
        <div className="flex-1">
          <label className="block text-xs text-aayna-taupe mb-1.5">Category</label>
          <Select value={category} onValueChange={(v) => updateParam("category", v)}>
            <SelectTrigger data-testid="filter-category" className="bg-white border-aayna-beige h-11">
              <SelectValue placeholder="All categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c.slug} value={c.slug}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex-1">
          <label className="block text-xs text-aayna-taupe mb-1.5">Sort by</label>
          <Select value={sort} onValueChange={(v) => updateParam("sort", v)}>
            <SelectTrigger data-testid="filter-sort" className="bg-white border-aayna-beige h-11">
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
      <ProductGrid products={products} loading={isLoading} />
    </div>
  );
}
