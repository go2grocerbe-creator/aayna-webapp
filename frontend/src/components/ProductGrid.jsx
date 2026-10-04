import { Gem } from "lucide-react";
import ProductCard from "@/components/ProductCard";

export default function ProductGrid({ products = [], loading = false, emptyText = "No products found." }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="bg-white border border-aayna-beige animate-pulse">
            <div className="aspect-square bg-aayna-beige/60" />
            <div className="p-4 space-y-2">
              <div className="h-3 w-1/3 bg-aayna-beige/60" />
              <div className="h-4 w-3/4 bg-aayna-beige/60" />
              <div className="h-4 w-1/4 bg-aayna-beige/60" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!products.length) {
    return (
      <div data-testid="empty-products" className="flex flex-col items-center text-center py-16 md:py-24">
        <span className="h-12 w-12 rounded-full bg-aayna-mist flex items-center justify-center mb-4">
          <Gem className="h-5 w-5 text-aayna-burgundy" />
        </span>
        <p className="text-aayna-taupe">{emptyText}</p>
      </div>
    );
  }

  return (
    <div data-testid="product-grid" className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  );
}
