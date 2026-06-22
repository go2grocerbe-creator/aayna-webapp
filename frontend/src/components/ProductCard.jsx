import { Link } from "react-router-dom";
import { ShoppingBag } from "lucide-react";
import { toast } from "sonner";
import { useCart } from "@/context/CartContext";
import { formatBDT, effectivePrice, discountPercent, isOutOfStock } from "@/lib/format";

export default function ProductCard({ product }) {
  const { addItem } = useCart();
  const oos = isOutOfStock(product);
  const discount = discountPercent(product);
  const image = product.images?.[0]?.image_url;

  const handleAdd = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (oos) return;
    addItem(product, 1);
    toast.success(`${product.product_name} added to cart`);
  };

  return (
    <Link
      to={`/product/${product.slug}`}
      data-testid={`product-card-${product.slug}`}
      className="group bg-white border border-aayna-beige flex flex-col overflow-hidden hover:shadow-md transition-shadow duration-300"
    >
      <div className="relative aspect-square w-full overflow-hidden bg-aayna-cream">
        <img
          src={image}
          alt={product.images?.[0]?.alt_text || product.product_name}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
        {discount > 0 && !oos && (
          <span className="absolute top-2 left-2 bg-aayna-gold text-aayna-charcoal text-[11px] font-bold px-2 py-1 z-10">
            -{discount}%
          </span>
        )}
        {oos && (
          <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
            <span className="bg-aayna-charcoal text-white text-xs font-semibold px-3 py-1.5 uppercase tracking-wide">
              Out of Stock
            </span>
          </div>
        )}
        {!oos && (
          <button
            data-testid={`quick-add-${product.slug}`}
            onClick={handleAdd}
            aria-label="Add to cart"
            className="absolute bottom-3 right-3 h-10 w-10 bg-aayna-rose text-white rounded-full flex items-center justify-center opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300 hover:bg-aayna-rose-dark"
          >
            <ShoppingBag className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="p-3 md:p-4 flex flex-col gap-1.5 flex-1">
        <p className="text-[11px] uppercase tracking-wider text-aayna-taupe">{product.category_name}</p>
        <h3 className="font-body text-sm md:text-base text-aayna-charcoal leading-snug line-clamp-2">
          {product.product_name}
        </h3>
        <div className="flex items-center gap-2 mt-auto pt-1">
          <span className="font-bold text-aayna-rose text-base">{formatBDT(effectivePrice(product))}</span>
          {discount > 0 && (
            <span className="text-aayna-taupe line-through text-xs">{formatBDT(product.selling_price)}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
