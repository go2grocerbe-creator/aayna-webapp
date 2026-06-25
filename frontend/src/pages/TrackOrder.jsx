import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Package, Search } from "lucide-react";
import { trackOrder } from "@/lib/api";
import { formatBDT } from "@/lib/format";
import { useSeo } from "@/lib/seo";

const STATUS_STEPS = ["New", "Confirmed", "Packed", "Sent to Courier", "Delivered"];

export default function TrackOrder() {
  useSeo({ title: "Track Your Order", description: "Track your AAYNA order using your Order ID and phone number." });
  const [params] = useSearchParams();
  const [orderNumber, setOrderNumber] = useState(params.get("order") || "");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!orderNumber.trim() || !phone.trim()) {
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
      <div className="text-center mb-8">
        <div className="h-14 w-14 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-4">
          <Package className="h-7 w-7 text-aayna-rose" />
        </div>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal">Track Your Order</h1>
        <p className="text-aayna-taupe mt-2">Enter your Order ID (e.g. ORD-1001) and the phone number you used at checkout.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          data-testid="track-order-number"
          value={orderNumber}
          onChange={(e) => setOrderNumber(e.target.value)}
          placeholder="Order ID (e.g. ORD-1001)"
          className="w-full h-12 border border-aayna-beige bg-white px-4 outline-none focus:border-aayna-rose text-aayna-charcoal"
        />
        <div className="flex gap-2">
          <input
            data-testid="track-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="Phone number (e.g. 01712345678)"
            className="flex-1 h-12 border border-aayna-beige bg-white px-4 outline-none focus:border-aayna-rose text-aayna-charcoal"
          />
          <button data-testid="track-submit" type="submit" disabled={loading} className="h-12 px-6 bg-aayna-rose text-white font-semibold flex items-center gap-2 hover:bg-aayna-rose-dark transition-colors disabled:opacity-60">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Track
          </button>
        </div>
      </form>
      <p className="text-xs text-aayna-taupe mt-2">For your privacy, we verify both your Order ID and phone number.</p>

      {results && results.length === 0 && (
        <p data-testid="track-no-results" className="text-center text-aayna-taupe mt-8">No order found. Please check your details.</p>
      )}

      <div className="space-y-5 mt-8">
        {(results || []).map((o) => {
          const stepIdx = STATUS_STEPS.indexOf(o.order_status);
          return (
            <div key={o.order_number} data-testid={`track-result-${o.order_number}`} className="bg-white border border-aayna-beige p-5 sm:p-6">
              <div className="flex items-center justify-between mb-4">
                <span className="font-display text-xl font-bold text-aayna-charcoal">{o.order_number}</span>
                <span className="bg-aayna-mist text-aayna-rose text-xs font-semibold px-3 py-1.5 uppercase tracking-wide">{o.order_status}</span>
              </div>

              {stepIdx >= 0 && o.order_status !== "Cancelled" && o.order_status !== "Returned" && (
                <div className="flex items-center mb-5">
                  {STATUS_STEPS.map((s, i) => (
                    <div key={s} className="flex-1 flex items-center last:flex-none">
                      <div className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${i <= stepIdx ? "bg-aayna-rose" : "bg-aayna-beige"}`} title={s} />
                      {i < STATUS_STEPS.length - 1 && <div className={`h-0.5 flex-1 ${i < stepIdx ? "bg-aayna-rose" : "bg-aayna-beige"}`} />}
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

              <div className="border-t border-aayna-beige mt-4 pt-3 text-sm space-y-1.5">
                <div className="flex justify-between"><span className="text-aayna-taupe">Payment</span><span className="text-aayna-charcoal">{o.payment_method}</span></div>
                <div className="flex justify-between"><span className="text-aayna-taupe">Total</span><span className="font-bold text-aayna-rose">{formatBDT(o.total_amount)}</span></div>
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
