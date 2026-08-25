import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Minus, Plus, AlertCircle } from "lucide-react";
import { useCart } from "@/context/CartContext";
import { validateCart } from "@/lib/api";
import { formatBDT } from "@/lib/format";
import { useSeo } from "@/lib/seo";
import ProductImage from "@/components/ProductImage";

// D4 "The Selection" (concept-d4-the-selection). Same cart data/logic as
// before - CartContext, validateCart, quantity/remove/subtotal - this is a
// presentation pass only. No card shells, no shadows: items are separated by
// hairlines and space, matching D2/D3's restrained editorial treatment.
export default function Cart() {
  const { items, updateQty, removeItem, subtotal } = useCart();
  useSeo({ title: "The Selection", description: "Review the pieces you've chosen.", noindex: true });

  const { data: validation } = useQuery({
    queryKey: ["cart-validate", items.map((i) => `${i.product_id}:${i.quantity}`).join(",")],
    queryFn: () =>
      validateCart({ items: items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })) }),
    enabled: items.length > 0,
  });

  const issueMap = {};
  (validation?.items || []).forEach((v) => {
    issueMap[v.product_id] = v;
  });
  const hasIssue = validation?.has_issue;

  if (items.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-32 text-center">
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">AAYNA · The Selection</p>
        <h1 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark">The Selection</h1>
        <p className="text-aayna-taupe text-sm mt-3">Nothing reflected here yet.</p>
        <Link
          to="/shop"
          data-testid="empty-cart-shop-button"
          className="inline-flex items-center gap-1.5 mt-7 text-aayna-burgundy font-medium min-h-[44px] hover:underline underline-offset-2"
        >
          Explore The Edit <span aria-hidden="true">→</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="hidden md:block absolute rounded-full border border-aayna-burgundy/[0.08] w-[420px] h-[420px] right-[-10%] top-[-4%]"
      />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-16">
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">AAYNA · The Selection</p>
        <h1 className="font-display font-semibold text-3xl md:text-5xl text-aayna-burgundy-dark">The Selection</h1>
        <p className="text-aayna-taupe text-sm mt-2">Your chosen pieces.</p>

        <div className="mt-10 md:mt-14 grid grid-cols-1 md:grid-cols-12 gap-10 md:gap-12">
          <div className="md:col-span-7">
            <div className="border-t border-aayna-beige">
              {items.map((item) => {
                const v = issueMap[item.product_id];
                const unavailable = v && !v.available;
                const hasCompare = item.discount_price && item.discount_price > 0;
                return (
                  <div
                    key={item.product_id}
                    data-testid={`cart-item-${item.slug}`}
                    className="flex gap-5 py-6 border-b border-aayna-beige"
                  >
                    <Link to={`/product/${item.slug}`} className="flex-shrink-0">
                      <ProductImage src={item.image} alt={item.name} className="h-28 w-28 md:h-44 md:w-44" />
                    </Link>
                    <div className="flex-1 min-w-0 flex flex-col">
                      <div className="flex justify-between gap-4">
                        <div className="min-w-0">
                          <Link
                            to={`/product/${item.slug}`}
                            className="font-display text-base md:text-lg text-aayna-charcoal hover:text-aayna-burgundy line-clamp-2"
                          >
                            {item.name}
                          </Link>
                          <p className="text-xs text-aayna-taupe mt-1">{item.sku}</p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <span className="font-semibold text-aayna-charcoal">
                            {formatBDT(item.unit_price * item.quantity)}
                          </span>
                          {hasCompare && (
                            <p className="text-xs text-aayna-taupe line-through mt-0.5">
                              {formatBDT(item.selling_price * item.quantity)}
                            </p>
                          )}
                        </div>
                      </div>

                      {unavailable && (
                        <p className="text-xs text-red-700 flex items-center gap-1 mt-2">
                          <AlertCircle className="h-3 w-3" />
                          {v.out_of_stock ? "Out of stock" : `Only ${v.available_quantity} available`}
                        </p>
                      )}

                      <div className="flex items-center justify-between mt-auto pt-4">
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            data-testid={`cart-decrease-${item.slug}`}
                            onClick={() => updateQty(item.product_id, item.quantity - 1)}
                            aria-label={`Decrease quantity of ${item.name}`}
                            className="h-11 w-11 flex items-center justify-center border border-aayna-beige hover:border-aayna-burgundy transition-colors"
                          >
                            <Minus className="h-3.5 w-3.5" />
                          </button>
                          <span className="w-6 text-center text-sm font-semibold" aria-live="polite">
                            {item.quantity}
                          </span>
                          <button
                            type="button"
                            data-testid={`cart-increase-${item.slug}`}
                            onClick={() => updateQty(item.product_id, item.quantity + 1)}
                            aria-label={`Increase quantity of ${item.name}`}
                            className="h-11 w-11 flex items-center justify-center border border-aayna-beige hover:border-aayna-burgundy transition-colors"
                          >
                            <Plus className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <button
                          type="button"
                          data-testid={`remove-item-${item.slug}`}
                          onClick={() => removeItem(item.product_id)}
                          aria-label={`Remove ${item.name} from selection`}
                          className="text-xs text-aayna-taupe hover:text-aayna-burgundy underline underline-offset-2 min-h-[44px] px-2 -mr-2"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Summary — anchored by hairlines and type, not a boxed card */}
          <div className="md:col-span-5">
            <div className="md:sticky md:top-28">
              <h2 className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-4">Order Summary</h2>
              <div className="space-y-3 text-sm border-t border-aayna-beige pt-4">
                <div className="flex justify-between">
                  <span className="text-aayna-taupe">Subtotal</span>
                  <span data-testid="cart-subtotal" className="font-medium text-aayna-charcoal">
                    {formatBDT(subtotal)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-aayna-taupe">Delivery</span>
                  <span className="text-aayna-taupe">Calculated at checkout</span>
                </div>
              </div>
              <div className="border-t border-aayna-beige mt-4 pt-4 flex justify-between items-baseline">
                <span className="font-display text-lg text-aayna-charcoal">Total</span>
                <span className="font-display text-2xl font-semibold text-aayna-burgundy">
                  {formatBDT(subtotal)}
                </span>
              </div>

              {hasIssue && (
                <p className="text-xs text-red-700 flex items-center gap-1.5 mt-4">
                  <AlertCircle className="h-3.5 w-3.5" /> Please update unavailable items before checkout.
                </p>
              )}

              <Link
                to="/checkout"
                data-testid="proceed-to-checkout"
                aria-disabled={hasIssue || undefined}
                className={`mt-6 w-full h-12 md:h-14 flex items-center justify-center font-semibold text-white transition-colors ${
                  hasIssue ? "bg-aayna-beige text-aayna-taupe pointer-events-none" : "bg-aayna-coral hover:bg-aayna-coral-dark"
                }`}
              >
                Proceed to Checkout
              </Link>
              <Link
                to="/shop"
                className="mt-4 flex items-center justify-center text-sm text-aayna-burgundy hover:underline underline-offset-2 min-h-[44px]"
              >
                Continue the Edit
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
