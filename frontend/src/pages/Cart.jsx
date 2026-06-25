import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ShoppingBag, Minus, Plus, Trash2, AlertCircle } from "lucide-react";
import { useCart } from "@/context/CartContext";
import { validateCart } from "@/lib/api";
import { formatBDT } from "@/lib/format";
import { useSeo } from "@/lib/seo";

export default function Cart() {
  const { items, updateQty, removeItem, subtotal } = useCart();
  useSeo({ title: "Your Cart", description: "Review the items in your AAYNA shopping cart.", noindex: true });

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
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <div className="h-20 w-20 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-6">
          <ShoppingBag className="h-9 w-9 text-aayna-rose" />
        </div>
        <h1 className="font-display text-3xl font-bold text-aayna-charcoal">Your cart is empty</h1>
        <p className="text-aayna-taupe mt-2">Looks like you haven't added anything yet.</p>
        <Link
          to="/shop"
          data-testid="empty-cart-shop-button"
          className="inline-flex items-center justify-center h-12 px-8 bg-aayna-rose text-white font-semibold mt-6 hover:bg-aayna-rose-dark transition-colors"
        >
          Start Shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
      <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal mb-8">Your Cart</h1>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-4">
          {items.map((item) => {
            const v = issueMap[item.product_id];
            const unavailable = v && !v.available;
            return (
              <div
                key={item.product_id}
                data-testid={`cart-item-${item.slug}`}
                className="flex gap-4 bg-white border border-aayna-beige p-3 sm:p-4"
              >
                <Link to={`/product/${item.slug}`} className="h-24 w-24 sm:h-28 sm:w-28 flex-shrink-0 bg-aayna-cream overflow-hidden">
                  <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                </Link>
                <div className="flex-1 min-w-0 flex flex-col">
                  <div className="flex justify-between gap-3">
                    <Link to={`/product/${item.slug}`} className="font-medium text-aayna-charcoal hover:text-aayna-rose line-clamp-2">
                      {item.name}
                    </Link>
                    <button
                      data-testid={`remove-item-${item.slug}`}
                      onClick={() => removeItem(item.product_id)}
                      aria-label="Remove"
                      className="text-aayna-taupe hover:text-red-700 transition-colors p-1 -mr-1 h-fit"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <p className="text-xs text-aayna-taupe mt-0.5">{item.sku}</p>
                  {unavailable && (
                    <p className="text-xs text-red-700 flex items-center gap-1 mt-1">
                      <AlertCircle className="h-3 w-3" />
                      {v.out_of_stock ? "Out of stock" : `Only ${v.available_quantity} available`}
                    </p>
                  )}
                  <div className="flex items-center justify-between mt-auto pt-2">
                    <div className="flex items-center border border-aayna-beige">
                      <button
                        data-testid={`cart-decrease-${item.slug}`}
                        onClick={() => updateQty(item.product_id, item.quantity - 1)}
                        className="h-9 w-9 flex items-center justify-center hover:bg-aayna-mist"
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="w-10 text-center text-sm font-semibold">{item.quantity}</span>
                      <button
                        data-testid={`cart-increase-${item.slug}`}
                        onClick={() => updateQty(item.product_id, item.quantity + 1)}
                        className="h-9 w-9 flex items-center justify-center hover:bg-aayna-mist"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <span className="font-bold text-aayna-rose">{formatBDT(item.unit_price * item.quantity)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-aayna-beige p-5 sm:p-6 sticky top-24">
            <h2 className="font-display text-xl font-bold text-aayna-charcoal mb-4">Order Summary</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-aayna-taupe">Subtotal</span>
                <span data-testid="cart-subtotal" className="font-semibold text-aayna-charcoal">{formatBDT(subtotal)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-aayna-taupe">Delivery</span>
                <span className="text-aayna-taupe">Calculated at checkout</span>
              </div>
            </div>
            <div className="border-t border-aayna-beige my-4" />
            <div className="flex justify-between items-baseline">
              <span className="font-semibold text-aayna-charcoal">Total</span>
              <span className="font-bold text-aayna-rose text-xl">{formatBDT(subtotal)}</span>
            </div>

            {hasIssue && (
              <p className="text-xs text-red-700 flex items-center gap-1.5 mt-3">
                <AlertCircle className="h-3.5 w-3.5" /> Please update unavailable items before checkout.
              </p>
            )}

            <Link
              to="/checkout"
              data-testid="proceed-to-checkout"
              className={`mt-4 w-full h-12 flex items-center justify-center font-semibold transition-colors ${
                hasIssue
                  ? "bg-aayna-beige text-aayna-taupe pointer-events-none"
                  : "bg-aayna-rose text-white hover:bg-aayna-rose-dark"
              }`}
            >
              Proceed to Checkout
            </Link>
            <Link to="/shop" className="mt-3 block text-center text-sm text-aayna-rose hover:underline">
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
