import { useParams, Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronRight, Minus, Plus, Truck, RefreshCw, ShieldCheck } from "lucide-react";
import { getProduct } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useSettings } from "@/hooks/useStore";
import { formatBDT, effectivePrice, discountPercent, isOutOfStock } from "@/lib/format";
import ProductCard from "@/components/ProductCard";
import { useSeo } from "@/lib/seo";

export default function ProductDetail() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();
  const { data: settings } = useSettings();
  const [qty, setQty] = useState(1);
  const [activeImg, setActiveImg] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["product", slug],
    queryFn: () => getProduct(slug),
  });

  useSeo({
    title: data?.product?.name,
    description: data?.product?.description || data?.product?.short_description,
    image: data?.product?.images?.[0],
  });

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-2 gap-10 animate-pulse">
          <div className="aspect-square bg-aayna-mist/60" />
          <div className="space-y-4">
            <div className="h-8 w-3/4 bg-aayna-mist/60" />
            <div className="h-6 w-1/3 bg-aayna-mist/60" />
            <div className="h-24 bg-aayna-mist/60" />
          </div>
        </div>
      </div>
    );
  }

  if (!data?.product) {
    return <div className="max-w-7xl mx-auto px-4 py-20 text-center text-aayna-taupe">Product not found.</div>;
  }

  const product = data.product;
  const images = product.images?.length ? product.images : [{ image_url: "", alt_text: product.product_name }];
  const oos = isOutOfStock(product);
  const discount = discountPercent(product);
  const price = effectivePrice(product);

  const handleAddToCart = () => {
    if (oos) return;
    addItem(product, qty);
    toast.success(`${product.product_name} added to cart`);
  };

  const buyNow = () => {
    if (oos) return;
    addItem(product, qty);
    navigate("/cart");
  };

  const waDigits = (settings?.whatsapp_number || "").replace(/[^0-9]/g, "");
  const waLink = `https://wa.me/${waDigits}?text=${encodeURIComponent(
    `Hi AAYNA, I'm interested in "${product.product_name}" (${product.sku}).`
  )}`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-12 pb-28 md:pb-12">
      <nav className="flex items-center gap-1.5 text-xs text-aayna-taupe mb-6 flex-wrap">
        <Link to="/" className="hover:text-aayna-rose">Home</Link>
        <ChevronRight className="h-3 w-3" />
        <Link to={`/category/${product.category_slug}`} className="hover:text-aayna-rose">{product.category_name}</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-aayna-charcoal line-clamp-1">{product.product_name}</span>
      </nav>

      <div className="grid md:grid-cols-2 gap-8 lg:gap-14">
        {/* Gallery */}
        <div>
          <div className="relative aspect-square bg-aayna-cream border border-aayna-beige overflow-hidden">
            <img
              data-testid="product-main-image"
              src={images[activeImg]?.image_url}
              alt={images[activeImg]?.alt_text || product.product_name}
              className="w-full h-full object-cover"
            />
            {discount > 0 && !oos && (
              <span className="absolute top-3 left-3 bg-aayna-gold text-aayna-charcoal text-xs font-bold px-2.5 py-1.5">
                -{discount}%
              </span>
            )}
            {oos && (
              <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
                <span className="bg-aayna-charcoal text-white text-sm font-semibold px-4 py-2 uppercase tracking-wide">
                  Out of Stock
                </span>
              </div>
            )}
          </div>
          {images.length > 1 && (
            <div className="flex gap-3 mt-3 overflow-x-auto no-scrollbar">
              {images.map((img, i) => (
                <button
                  key={i}
                  onClick={() => setActiveImg(i)}
                  className={`h-20 w-20 flex-shrink-0 border ${i === activeImg ? "border-aayna-rose" : "border-aayna-beige"}`}
                >
                  <img src={img.image_url} alt={img.alt_text} className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div>
          <p className="text-xs uppercase tracking-wider text-aayna-taupe">{product.category_name}</p>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal mt-1.5 leading-tight">
            {product.product_name}
          </h1>

          <div className="flex items-center gap-3 mt-4">
            <span data-testid="product-price" className="text-2xl md:text-3xl font-bold text-aayna-rose">{formatBDT(price)}</span>
            {discount > 0 && (
              <>
                <span className="text-aayna-taupe line-through text-lg">{formatBDT(product.selling_price)}</span>
                <span className="bg-aayna-gold text-aayna-charcoal text-xs font-bold px-2 py-1">Save {discount}%</span>
              </>
            )}
          </div>

          <p className="text-aayna-taupe mt-4 leading-relaxed">{product.short_description}</p>

          {/* Attributes */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2.5 mt-6 text-sm border-t border-aayna-beige pt-5">
            {product.material && (<><dt className="text-aayna-taupe">Material</dt><dd className="text-aayna-charcoal font-medium text-right">{product.material}</dd></>)}
            {product.color && (<><dt className="text-aayna-taupe">Color</dt><dd className="text-aayna-charcoal font-medium text-right">{product.color}</dd></>)}
            {product.size && (<><dt className="text-aayna-taupe">Size</dt><dd className="text-aayna-charcoal font-medium text-right">{product.size}</dd></>)}
            <dt className="text-aayna-taupe">SKU</dt><dd className="text-aayna-charcoal font-medium text-right">{product.sku}</dd>
            <dt className="text-aayna-taupe">Availability</dt>
            <dd className={`font-medium text-right ${oos ? "text-red-700" : "text-green-700"}`}>
              {oos ? "Out of stock" : `${product.stock_quantity} in stock`}
            </dd>
          </dl>

          {/* Quantity + actions */}
          {!oos && (
            <div className="flex items-center gap-4 mt-6">
              <div className="flex items-center border border-aayna-beige bg-white">
                <button
                  data-testid="qty-decrease"
                  onClick={() => setQty((q) => Math.max(1, q - 1))}
                  className="h-12 w-12 flex items-center justify-center text-aayna-charcoal hover:bg-aayna-mist"
                >
                  <Minus className="h-4 w-4" />
                </button>
                <span data-testid="qty-value" className="w-12 text-center font-semibold">{qty}</span>
                <button
                  data-testid="qty-increase"
                  onClick={() => setQty((q) => Math.min(product.stock_quantity, q + 1))}
                  className="h-12 w-12 flex items-center justify-center text-aayna-charcoal hover:bg-aayna-mist"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          <div className="hidden md:flex flex-col sm:flex-row gap-3 mt-5">
            <button
              data-testid="add-to-cart-button"
              onClick={handleAddToCart}
              disabled={oos}
              className="flex-1 h-12 bg-aayna-rose text-white font-semibold hover:bg-aayna-rose-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {oos ? "Out of Stock" : "Add to Cart"}
            </button>
            <button
              onClick={buyNow}
              disabled={oos}
              className="flex-1 h-12 border border-aayna-rose text-aayna-rose font-semibold hover:bg-aayna-mist transition-colors disabled:opacity-50"
            >
              Buy Now
            </button>
          </div>

          <a
            data-testid="whatsapp-inquiry"
            href={waLink}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 hidden md:flex items-center justify-center gap-2 h-11 w-full border border-aayna-beige text-aayna-charcoal text-sm font-medium hover:border-aayna-rose transition-colors"
          >
            Have a question? Inquire on WhatsApp
          </a>

          {/* Notes */}
          <div className="mt-6 space-y-3 text-sm border-t border-aayna-beige pt-5">
            <div className="flex items-start gap-3"><Truck className="h-4 w-4 text-aayna-rose mt-0.5" /><span className="text-aayna-taupe">Delivery in Dhaka 1–2 days, outside Dhaka 3–5 days. Cash on Delivery available.</span></div>
            <div className="flex items-start gap-3"><RefreshCw className="h-4 w-4 text-aayna-rose mt-0.5" /><span className="text-aayna-taupe">Easy 3-day exchange for damaged or wrong items (earrings excluded for hygiene).</span></div>
            <div className="flex items-start gap-3"><ShieldCheck className="h-4 w-4 text-aayna-rose mt-0.5" /><span className="text-aayna-taupe">Quality checked before dispatch.</span></div>
          </div>
        </div>
      </div>

      {/* Full description */}
      {product.full_description && (
        <div className="mt-12 md:mt-16 max-w-3xl">
          <h2 className="font-display text-2xl font-bold text-aayna-charcoal mb-3">Description</h2>
          <p className="text-aayna-taupe leading-relaxed">{product.full_description}</p>
        </div>
      )}

      {/* Related */}
      {data.related?.length > 0 && (
        <div className="mt-14 md:mt-20">
          <h2 className="font-display text-2xl md:text-3xl font-bold text-aayna-charcoal mb-7">You May Also Like</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
            {data.related.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}

      {/* Sticky mobile add to cart */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white border-t border-aayna-beige p-3 flex items-center gap-3">
        <div className="flex-shrink-0">
          <p className="text-xs text-aayna-taupe">Price</p>
          <p className="font-bold text-aayna-rose text-lg leading-none">{formatBDT(price)}</p>
        </div>
        <button
          data-testid="add-to-cart-button-mobile"
          onClick={handleAddToCart}
          disabled={oos}
          className="flex-1 h-12 bg-aayna-rose text-white font-semibold disabled:opacity-50"
        >
          {oos ? "Out of Stock" : "Add to Cart"}
        </button>
      </div>
    </div>
  );
}
