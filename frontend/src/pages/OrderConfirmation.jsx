import { useState, useEffect } from "react";
import { useParams, useNavigate, useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Copy, Check } from "lucide-react";
import { getOrder } from "@/lib/api";
import { formatBDT, customerStatusLabel } from "@/lib/format";
import { useSeo } from "@/lib/seo";
import ProductImage from "@/components/ProductImage";

// D6 - presentation only. The secure token-lookup contract is untouched:
// getOrder(orderNumber, token) still requires a real token, the query stays
// disabled without one, and any missing/invalid/unknown token renders the
// exact same generic state - never a hint about which part was wrong.
// The confirmation endpoint deliberately excludes phone/address/email from
// its response (see backend/server.py get_order_confirmation - "public-safe:
// no phone/address"), so this page only ever renders customer_name and
// district - it cannot show more contact detail than the API returns.
export default function OrderConfirmation() {
  const { orderNumber } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Captured once, at mount, from the URL the customer actually arrived
  // with - stripping the token from the visible URL below must not change
  // this value or re-trigger/disable the query.
  const [token] = useState(() => searchParams.get("token"));

  // L5.1: the raw token otherwise sits in the browser's own address bar and
  // history for as long as this tab/session keeps it. It's already used for
  // the one request it's needed for by the time this runs, so replace the
  // URL with the query string removed - no extra history entry, no refetch.
  useEffect(() => {
    if (searchParams.get("token")) {
      navigate(`/order-confirmation/${orderNumber}`, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data: order, isLoading, isError } = useQuery({
    queryKey: ["order", orderNumber, token],
    queryFn: () => getOrder(orderNumber, token),
    enabled: !!token,
    retry: 1,
  });
  const [copied, setCopied] = useState(false);
  useSeo({ title: "Order Confirmed", description: "Your AAYNA order has been placed.", noindex: true });

  const copyOrderNumber = async () => {
    if (!order) return;
    try {
      await navigator.clipboard.writeText(order.order_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API can be unavailable (permissions, non-secure context) -
      // the order number is already visible as selectable text either way.
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-24 text-center" role="status" aria-live="polite">
        <Loader2 className="h-7 w-7 animate-spin text-aayna-burgundy mx-auto" aria-hidden="true" />
        <span className="sr-only">Loading your order confirmation…</span>
      </div>
    );
  }

  if (isError || !order) {
    return (
      <div className="max-w-xl mx-auto px-4 sm:px-6 py-24 md:py-32 text-center">
        <h1 className="font-display font-semibold text-2xl md:text-3xl text-aayna-burgundy-dark">
          We couldn't open this order confirmation.
        </h1>
        <p className="text-aayna-taupe text-sm mt-3">
          The link may be incomplete or out of date.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center mt-8">
          <Link
            to="/track-order"
            className="inline-flex items-center justify-center h-12 px-6 bg-aayna-coral text-white font-semibold hover:bg-aayna-coral-dark transition-colors min-h-[44px]"
          >
            Track an order
          </Link>
          <Link
            to="/"
            className="inline-flex items-center justify-center h-12 px-6 text-aayna-burgundy font-medium hover:underline underline-offset-2 min-h-[44px]"
          >
            Return home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 md:py-16">
      <div className="text-center">
        <div className="h-14 w-14 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-5" aria-hidden="true">
          <CheckCircle2 className="h-7 w-7 text-aayna-burgundy" />
        </div>
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">AAYNA</p>
        <h1 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark">Order Confirmed</h1>
        <p className="text-aayna-taupe mt-2">
          Thank you, {order.customer_name.split(" ")[0]}. We've received your order and the details are below.
        </p>
      </div>

      <div className="mt-10">
        <div className="flex items-start justify-between gap-4 pb-5 border-b border-aayna-beige">
          <div>
            <p className="text-xs text-aayna-taupe uppercase tracking-wide">Order Number</p>
            <div className="flex items-center gap-2 mt-0.5">
              <p data-testid="confirmation-order-number" className="font-display text-2xl font-semibold text-aayna-charcoal">
                {order.order_number}
              </p>
              <button
                type="button"
                onClick={copyOrderNumber}
                aria-label={copied ? "Order number copied" : "Copy order number"}
                className="h-8 w-8 flex items-center justify-center text-aayna-taupe hover:text-aayna-burgundy transition-colors"
              >
                {copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
              </button>
            </div>
          </div>
          <span className="text-xs font-semibold text-aayna-burgundy uppercase tracking-wide border border-aayna-burgundy/30 px-3 py-1.5 flex-shrink-0">
            {customerStatusLabel(order.order_status)}
          </span>
        </div>

        <div className="py-5 border-b border-aayna-beige space-y-4" aria-label="Items in this order">
          {order.items.map((it, idx) => (
            <div key={idx} className="flex gap-3 items-center">
              <ProductImage src={it.image} alt={it.product_name} className="h-14 w-14 flex-shrink-0" iconClassName="h-4 w-4" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-aayna-charcoal line-clamp-1">{it.product_name}</p>
                <p className="text-xs text-aayna-taupe">{formatBDT(it.unit_price)} × {it.quantity}</p>
              </div>
              <span className="text-sm font-medium text-aayna-charcoal">{formatBDT(it.total_price)}</span>
            </div>
          ))}
        </div>

        <div className="py-5 space-y-2.5 text-sm border-b border-aayna-beige">
          <div className="flex justify-between"><span className="text-aayna-taupe">Subtotal</span><span className="text-aayna-charcoal">{formatBDT(order.subtotal)}</span></div>
          <div className="flex justify-between"><span className="text-aayna-taupe">Delivery ({order.district})</span><span className="text-aayna-charcoal">{formatBDT(order.delivery_charge)}</span></div>
          <div className="flex justify-between"><span className="text-aayna-taupe">Payment Method</span><span className="text-aayna-charcoal">{order.payment_method}</span></div>
        </div>

        <div className="flex justify-between items-baseline pt-5">
          <span className="font-display text-lg text-aayna-charcoal">Total</span>
          <span data-testid="confirmation-total" className="font-display text-2xl font-semibold text-aayna-burgundy">{formatBDT(order.total_amount)}</span>
        </div>
      </div>

      <p className="text-sm text-aayna-taupe mt-8 text-center">
        We'll confirm your order shortly. You can check its status anytime on the Track Order page.
      </p>

      <div className="flex flex-col sm:flex-row gap-3 mt-6">
        <Link
          to="/shop"
          className="flex-1 h-12 bg-aayna-coral text-white font-semibold flex items-center justify-center hover:bg-aayna-coral-dark transition-colors min-h-[44px]"
        >
          Continue the Edit
        </Link>
        <Link
          to={`/track-order?order=${encodeURIComponent(order.order_number)}`}
          className="flex-1 h-12 border border-aayna-burgundy text-aayna-burgundy font-semibold flex items-center justify-center hover:bg-aayna-mist transition-colors min-h-[44px]"
        >
          Track This Order
        </Link>
      </div>
    </div>
  );
}
