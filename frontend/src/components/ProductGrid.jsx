import ProductCard from "@/components/ProductCard";

export default function ProductGrid({ products = [], loading = false, emptyText = "No products found." }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="bg-white border border-aayna-beige animate-pulse">
            <div className="aspect-square bg-aayna-mist/60" />
            <div className="p-4 space-y-2">
              <div className="h-3 w-1/3 bg-aayna-mist/60" />
              <div className="h-4 w-3/4 bg-aayna-mist/60" />
              <div className="h-4 w-1/4 bg-aayna-mist/60" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!products.length) {
    return <p data-testid="empty-products" className="text-aayna-taupe text-center py-16">{emptyText}</p>;
  }

  return (
    <div data-testid="product-grid" className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  );
}
