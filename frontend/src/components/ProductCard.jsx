import { Link } from "react-router-dom";
import { ShoppingBag } from "lucide-react";
import { toast } from "sonner";
import { useCart } from "@/context/CartContext";
import { formatBDT, effectivePrice, discountPercent, isOutOfStock } from "@/lib/format";
import ProductImage from "@/components/ProductImage";

// AAYNA Product Presentation System (DESIGN.md "Product Presentation System").
// One data/cart/stock/price source, three visual variants selected by
// `variant`. Do not fork business logic (price/discount/stock/cart) per
// variant - only the returned JSX differs.
//
//   commerce  (default) - Shop/Category/Cart grids. Unchanged from the
//             pre-existing ProductCard so /shop never regresses.
//   editorial - homepage storytelling supporting items (Scene III/V, not
//             built yet). 4:5 image, Playfair name, price only, no badge,
//             no quick-add - tap routes straight to PDP.
//   hero      - homepage storytelling lead item (Scene III, not built yet).
//             Largest image/type, optional real short_description, a
//             visible (not hover-only) Add to Cart.
export default function ProductCard({ product, variant = "commerce" }) {
  const { addItem } = useCart();
  const oos = isOutOfStock(product);
  const discount = discountPercent(product);
  const image = product.images?.[0]?.image_url;
  const imageAlt = product.images?.[0]?.alt_text || product.product_name;

  const handleAdd = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (oos) return;
    addItem(product, 1);
    toast.success(`${product.product_name} added to cart`);
  };

  if (variant === "editorial") {
    return (
      <Link
        to={`/product/${product.slug}`}
        data-testid={`product-card-editorial-${product.slug}`}
        className="group flex flex-col"
      >
        <div className="relative aspect-[4/5] w-full overflow-hidden">
          <ProductImage
            src={image}
            alt={imageAlt}
            className="absolute inset-0"
            imgClassName="group-hover:scale-105 transition-transform duration-500"
            iconClassName="h-8 w-8"
          />
          {oos && (
            <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
              <span className="bg-aayna-charcoal text-white text-xs font-semibold px-3 py-1.5 uppercase tracking-wide">
                Out of Stock
              </span>
            </div>
          )}
        </div>
        <div className="pt-3 flex flex-col gap-1">
          <h3 className="font-display text-lg text-aayna-charcoal leading-snug line-clamp-1">
            {product.product_name}
          </h3>
          <span className="font-semibold text-aayna-burgundy text-sm">{formatBDT(effectivePrice(product))}</span>
        </div>
      </Link>
    );
  }

  if (variant === "hero") {
    return (
      <div data-testid={`product-card-hero-${product.slug}`} className="flex flex-col">
        <Link to={`/product/${product.slug}`} className="group relative aspect-[4/5] w-full overflow-hidden block">
          <ProductImage
            src={image}
            alt={imageAlt}
            className="absolute inset-0"
            imgClassName="group-hover:scale-105 transition-transform duration-700"
            iconClassName="h-12 w-12"
            eager
          />
          {oos && (
            <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
              <span className="bg-aayna-charcoal text-white text-sm font-semibold px-4 py-2 uppercase tracking-wide">
                Out of Stock
              </span>
            </div>
          )}
        </Link>
        <div className="pt-4 flex flex-col gap-2">
          <Link to={`/product/${product.slug}`}>
            <h3 className="font-display text-2xl md:text-3xl text-aayna-charcoal leading-snug hover:text-aayna-burgundy transition-colors">
              {product.product_name}
            </h3>
          </Link>
          <div className="flex items-center gap-2">
            <span className="font-bold text-aayna-burgundy text-xl">{formatBDT(effectivePrice(product))}</span>
            {discount > 0 && (
              <span className="text-aayna-taupe line-through text-sm">{formatBDT(product.selling_price)}</span>
            )}
          </div>
          {product.short_description && (
            <p className="text-aayna-taupe text-sm max-w-md">{product.short_description}</p>
          )}
          <button
            data-testid={`hero-add-to-cart-${product.slug}`}
            onClick={handleAdd}
            disabled={oos}
            className="mt-2 h-11 px-6 w-fit bg-aayna-coral text-white text-sm font-semibold hover:bg-aayna-coral-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {oos ? "Out of Stock" : "Add to Cart"}
          </button>
        </div>
      </div>
    );
  }

  // commerce (default) - unchanged from the pre-refactor ProductCard.
  return (
    <Link
      to={`/product/${product.slug}`}
      data-testid={`product-card-${product.slug}`}
      className="group bg-white border border-aayna-beige flex flex-col overflow-hidden hover:shadow-md transition-shadow duration-300"
    >
      <div className="relative aspect-square w-full overflow-hidden">
        <ProductImage
          src={image}
          alt={imageAlt}
          className="absolute inset-0"
          imgClassName="group-hover:scale-105 transition-transform duration-500"
          iconClassName="h-8 w-8"
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
            className="absolute bottom-3 right-3 h-10 w-10 bg-aayna-coral text-white rounded-full flex items-center justify-center opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300 hover:bg-aayna-coral-dark"
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
          <span className="font-bold text-aayna-burgundy text-base">{formatBDT(effectivePrice(product))}</span>
          {discount > 0 && (
            <span className="text-aayna-taupe line-through text-xs">{formatBDT(product.selling_price)}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
