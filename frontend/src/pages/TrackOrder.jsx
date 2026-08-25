import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Search, SearchX } from "lucide-react";
import { trackOrder } from "@/lib/api";
import { formatBDT, customerStatusLabel } from "@/lib/format";
import { useSeo } from "@/lib/seo";

// D6 - presentation only. Verification is unchanged: both order number AND
// phone are required, the backend never distinguishes which one was wrong,
// and this page never renders anything beyond what POST /api/track returns.
// No noindex here - Track Order is deliberately in the public sitemap
// (backend/server.py SITEMAP_STATIC_PATHS) since the page itself never
// shows order data until a matching lookup succeeds; that's existing
// architecture, not something to "fix" by adding noindex.
const STATUS_STEPS = ["New", "Confirmed", "Packed", "Sent to Courier", "Delivered"];

export default function TrackOrder() {
  useSeo({ title: "Track Your Order", description: "Track your AAYNA order using your Order ID and phone number." });
  const [params] = useSearchParams();
  const [orderNumber, setOrderNumber] = useState(params.get("order") || "");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const nextErrors = {};
    if (!orderNumber.trim()) nextErrors.orderNumber = "Order ID is required";
    if (!phone.trim()) nextErrors.phone = "Phone number is required";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      const firstKey = nextErrors.orderNumber ? "track-order-number" : "track-phone";
      document.querySelector(`[data-testid="${firstKey}"]`)?.focus();
      toast.error("Enter your Order ID and the phone number used for the order");
      return;
    }
    setLoading(true);
    setResults(null);
    try {
      const data = await trackOrder({ order_number: orderNumber.trim(), phone: phone.trim() });
      setResults(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No matching order found. Please check your details.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 md:py-16">
      <div className="text-center mb-10">
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">AAYNA</p>
        <h1 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark">Track Your Order</h1>
        <p className="text-aayna-taupe mt-2 text-sm">
          Use your Order ID and the phone number used at checkout.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="track-order-number" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Order ID *</label>
          <input
            id="track-order-number"
            data-testid="track-order-number"
            autoComplete="off"
            value={orderNumber}
            onChange={(e) => { setOrderNumber(e.target.value); setErrors((er) => ({ ...er, orderNumber: undefined })); }}
            placeholder="e.g. ORD-1001"
            aria-invalid={!!errors.orderNumber}
            aria-describedby={errors.orderNumber ? "track-order-number-error" : undefined}
            className={`w-full h-12 border bg-white px-4 outline-none focus:border-aayna-burgundy focus:ring-1 focus:ring-aayna-burgundy text-aayna-charcoal ${
              errors.orderNumber ? "border-red-500" : "border-aayna-beige"
            }`}
          />
          {errors.orderNumber && <p id="track-order-number-error" className="text-xs text-red-700 mt-1">{errors.orderNumber}</p>}
        </div>
        <div>
          <label htmlFor="track-phone" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Phone Number *</label>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              id="track-phone"
              data-testid="track-phone"
              type="tel"
              autoComplete="tel"
              value={phone}
              onChange={(e) => { setPhone(e.target.value); setErrors((er) => ({ ...er, phone: undefined })); }}
              placeholder="e.g. 01712345678"
              aria-invalid={!!errors.phone}
              aria-describedby={errors.phone ? "track-phone-error" : undefined}
              className={`flex-1 h-12 border bg-white px-4 outline-none focus:border-aayna-burgundy focus:ring-1 focus:ring-aayna-burgundy text-aayna-charcoal ${
                errors.phone ? "border-red-500" : "border-aayna-beige"
              }`}
            />
            <button
              data-testid="track-submit"
              type="submit"
              disabled={loading}
              aria-busy={loading}
              className="h-12 px-6 bg-aayna-coral text-white font-semibold flex items-center justify-center gap-2 hover:bg-aayna-coral-dark transition-colors disabled:opacity-60 min-h-[44px]"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Search className="h-4 w-4" aria-hidden="true" />}
              Track
            </button>
          </div>
          {errors.phone && <p id="track-phone-error" className="text-xs text-red-700 mt-1">{errors.phone}</p>}
        </div>
      </form>
      <p className="text-xs text-aayna-taupe mt-3">For your privacy, we verify both your Order ID and phone number.</p>

      {results && results.length === 0 && (
        <div data-testid="track-no-results" role="status" className="flex flex-col items-center text-center py-14 border-t border-aayna-beige mt-10">
          <SearchX className="h-6 w-6 text-aayna-taupe mb-3" aria-hidden="true" />
          <p className="text-aayna-taupe">No order found. Please check your details.</p>
        </div>
      )}

      <div className="space-y-10 mt-10">
        {(results || []).map((o) => {
          const stepIdx = STATUS_STEPS.indexOf(o.order_status);
          const isStopped = o.order_status === "Cancelled" || o.order_status === "Returned";
          return (
            <div key={o.order_number} data-testid={`track-result-${o.order_number}`} className="border-t border-aayna-beige pt-6" role="status">
              <div className="flex items-center justify-between mb-5">
                <span className="font-display text-xl font-semibold text-aayna-charcoal">{o.order_number}</span>
                <span
                  className={`text-xs font-semibold px-3 py-1.5 uppercase tracking-wide ${
                    isStopped ? "text-red-700 border border-red-200" : "text-aayna-burgundy border border-aayna-burgundy/30"
                  }`}
                >
                  {customerStatusLabel(o.order_status)}
                </span>
              </div>

              {stepIdx >= 0 && !isStopped && (
                <div className="flex items-center mb-6" aria-hidden="true">
                  {STATUS_STEPS.map((s, i) => (
                    <div key={s} className="flex-1 flex items-center last:flex-none">
                      <div className={`h-2 w-2 rounded-full flex-shrink-0 ${i <= stepIdx ? "bg-aayna-burgundy" : "bg-aayna-beige"}`} title={customerStatusLabel(s)} />
                      {i < STATUS_STEPS.length - 1 && <div className={`h-px flex-1 ${i < stepIdx ? "bg-aayna-burgundy" : "bg-aayna-beige"}`} />}
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-1.5 text-sm border-t border-aayna-beige pt-4">
                {o.items.map((it, i) => (
                  <div key={i} className="flex justify-between">
                    <span className="text-aayna-charcoal">{it.product_name}</span>
                    <span className="text-aayna-taupe">×{it.quantity}</span>
                  </div>
                ))}
              </div>

              <div className="border-t border-aayna-beige mt-4 pt-4 text-sm space-y-1.5">
                <div className="flex justify-between"><span className="text-aayna-taupe">Payment</span><span className="text-aayna-charcoal">{o.payment_method}</span></div>
                <div className="flex justify-between"><span className="text-aayna-taupe">Total</span><span className="font-semibold text-aayna-burgundy">{formatBDT(o.total_amount)}</span></div>
                {o.courier_name && (
                  <div className="flex justify-between"><span className="text-aayna-taupe">Courier</span><span className="text-aayna-charcoal">{o.courier_name} {o.courier_tracking_code ? `· ${o.courier_tracking_code}` : ""}</span></div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
