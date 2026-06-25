import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { getOrder } from "@/lib/api";
import { formatBDT } from "@/lib/format";
import { useSeo } from "@/lib/seo";

export default function OrderConfirmation() {
  const { orderNumber } = useParams();
  const { data: order, isLoading, isError } = useQuery({
    queryKey: ["order", orderNumber],
    queryFn: () => getOrder(orderNumber),
    retry: 1,
  });
  useSeo({ title: "Order Confirmed", description: "Your AAYNA order has been placed.", noindex: true });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-24 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-aayna-rose mx-auto" />
      </div>
    );
  }

  if (isError || !order) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-24 text-center">
        <h1 className="font-display text-2xl font-bold text-aayna-charcoal">Order not found</h1>
        <Link to="/" className="text-aayna-rose hover:underline mt-3 inline-block">Back to home</Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 md:py-16">
      <div className="text-center animate-fade-up">
        <div className="h-16 w-16 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-5">
          <CheckCircle2 className="h-9 w-9 text-aayna-rose" />
        </div>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal">Thank you, {order.customer_name.split(" ")[0]}!</h1>
        <p className="text-aayna-taupe mt-2">Your order has been placed successfully.</p>
        <p className="text-aayna-taupe text-sm mt-1">Our team will confirm your order shortly.</p>
      </div>

      <div className="bg-white border border-aayna-beige mt-8 p-6">
        <div className="flex items-center justify-between pb-4 border-b border-aayna-beige">
          <div>
            <p className="text-xs text-aayna-taupe">Order ID</p>
            <p data-testid="confirmation-order-number" className="font-display text-2xl font-bold text-aayna-charcoal">{order.order_number}</p>
          </div>
          <span className="bg-aayna-gold/20 text-aayna-charcoal border border-aayna-gold text-xs font-semibold px-3 py-1.5 uppercase tracking-wide">
            {order.order_status}
          </span>
        </div>

        <div className="py-4 border-b border-aayna-beige space-y-3">
          {order.items.map((it, idx) => (
            <div key={idx} className="flex gap-3 items-center">
              {it.image && <div className="h-12 w-12 bg-aayna-cream overflow-hidden flex-shrink-0"><img src={it.image} alt={it.product_name} className="w-full h-full object-cover" /></div>}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-aayna-charcoal line-clamp-1">{it.product_name}</p>
                <p className="text-xs text-aayna-taupe">{formatBDT(it.unit_price)} × {it.quantity}</p>
              </div>
              <span className="text-sm font-medium text-aayna-charcoal">{formatBDT(it.total_price)}</span>
            </div>
          ))}
        </div>

        <div className="py-4 space-y-2 text-sm border-b border-aayna-beige">
          <div className="flex justify-between"><span className="text-aayna-taupe">Subtotal</span><span>{formatBDT(order.subtotal)}</span></div>
          <div className="flex justify-between"><span className="text-aayna-taupe">Delivery ({order.district})</span><span>{formatBDT(order.delivery_charge)}</span></div>
          <div className="flex justify-between"><span className="text-aayna-taupe">Payment Method</span><span>{order.payment_method}</span></div>
        </div>

        <div className="flex justify-between items-baseline pt-4">
          <span className="font-semibold text-aayna-charcoal">Total</span>
          <span data-testid="confirmation-total" className="font-bold text-aayna-rose text-2xl">{formatBDT(order.total_amount)}</span>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mt-6">
        <Link to="/shop" className="flex-1 h-12 bg-aayna-rose text-white font-semibold flex items-center justify-center hover:bg-aayna-rose-dark transition-colors">
          Continue Shopping
        </Link>
        <Link to={`/track-order?order=${encodeURIComponent(order.order_number)}`} className="flex-1 h-12 border border-aayna-rose text-aayna-rose font-semibold flex items-center justify-center hover:bg-aayna-mist transition-colors">
          Track This Order
        </Link>
      </div>
    </div>
  );
}
