import { useState, useRef, useMemo } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, ShoppingBag } from "lucide-react";
import { getDistricts, checkout } from "@/lib/api";
import { useSettings } from "@/hooks/useStore";
import { useCart } from "@/context/CartContext";
import { formatBDT } from "@/lib/format";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useSeo } from "@/lib/seo";

const PHONE_RE = /^(?:\+?880|0)1[3-9]\d{8}$/;

const PAYMENTS = [
  { value: "cod", label: "Cash on Delivery", desc: "Pay in cash when your order arrives." },
  { value: "bkash", label: "bKash (Manual)", desc: "Send money, then add your transaction ID." },
  { value: "nagad", label: "Nagad (Manual)", desc: "Send money, then add your transaction ID." },
];

export default function Checkout() {
  const navigate = useNavigate();
  const { items, subtotal, clearCart } = useCart();
  const { data: settings } = useSettings();
  const { data: districts = [] } = useQuery({ queryKey: ["districts"], queryFn: getDistricts });
  const requestId = useRef(
    (typeof crypto !== "undefined" && crypto.randomUUID && crypto.randomUUID()) ||
      `req-${Date.now()}-${Math.random()}`
  );

  const [form, setForm] = useState({
    customer_name: "",
    customer_phone: "",
    district: "",
    delivery_address: "",
    delivery_note: "",
    customer_email: "",
    payment_method: "cod",
    transaction_id: "",
    sender_number: "",
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useSeo({ title: "Checkout", description: "Complete your AAYNA order securely.", noindex: true });

  const set = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const deliveryCharge = useMemo(() => {
    if (!form.district || !settings) return 0;
    return form.district === "Dhaka"
      ? Number(settings.delivery_charge_inside_dhaka)
      : Number(settings.delivery_charge_outside_dhaka);
  }, [form.district, settings]);

  const total = subtotal + deliveryCharge;

  const validate = () => {
    const e = {};
    if (!form.customer_name.trim()) e.customer_name = "Full name is required";
    if (!form.customer_phone.trim()) e.customer_phone = "Phone number is required";
    else if (!PHONE_RE.test(form.customer_phone.replace(/[\s-]/g, "")))
      e.customer_phone = "Enter a valid Bangladesh number (e.g. 01712345678)";
    if (!form.district) e.district = "Please select your district";
    if (!form.delivery_address.trim()) e.delivery_address = "Delivery address is required";
    if (!form.payment_method) e.payment_method = "Select a payment method";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    if (!validate()) {
      toast.error("Please fix the highlighted fields");
      return;
    }
    setSubmitting(true);
    try {
      const res = await checkout({
        ...form,
        items: items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
        client_request_id: requestId.current,
      });
      clearCart();
      navigate(`/order-confirmation/${res.order_number}`);
    } catch (err) {
      const msg = err?.response?.data?.detail || "Something went wrong. Please try again.";
      toast.error(msg);
      setSubmitting(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <div className="h-20 w-20 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-6">
          <ShoppingBag className="h-9 w-9 text-aayna-rose" />
        </div>
        <h1 className="font-display text-3xl font-bold text-aayna-charcoal">Your cart is empty</h1>
        <Link to="/shop" className="inline-flex h-12 px-8 items-center bg-aayna-rose text-white font-semibold mt-6 hover:bg-aayna-rose-dark transition-colors">
          Start Shopping
        </Link>
      </div>
    );
  }

  const inputCls = (key) =>
    `w-full h-11 border bg-white px-3 text-aayna-charcoal text-[15px] outline-none focus:border-aayna-rose focus:ring-1 focus:ring-aayna-rose ${
      errors[key] ? "border-red-500" : "border-aayna-beige"
    }`;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
      <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal mb-8">Checkout</h1>

      <form onSubmit={handleSubmit} className="grid lg:grid-cols-3 gap-8">
        {/* Form fields */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white border border-aayna-beige p-5 sm:p-6">
            <h2 className="font-display text-xl font-bold text-aayna-charcoal mb-4">Delivery Details</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-aayna-charcoal mb-1.5">Full Name *</label>
                <input data-testid="checkout-name" className={inputCls("customer_name")} value={form.customer_name} onChange={(e) => set("customer_name", e.target.value)} placeholder="Your full name" />
                {errors.customer_name && <p className="text-xs text-red-700 mt-1">{errors.customer_name}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-aayna-charcoal mb-1.5">Phone Number *</label>
                <input data-testid="checkout-phone" className={inputCls("customer_phone")} value={form.customer_phone} onChange={(e) => set("customer_phone", e.target.value)} placeholder="01712345678" />
                {errors.customer_phone && <p className="text-xs text-red-700 mt-1">{errors.customer_phone}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-aayna-charcoal mb-1.5">District *</label>
                <Select value={form.district} onValueChange={(v) => set("district", v)}>
                  <SelectTrigger data-testid="checkout-district" className={`h-11 bg-white ${errors.district ? "border-red-500" : "border-aayna-beige"}`}>
                    <SelectValue placeholder="Select district" />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {districts.map((d) => (
                      <SelectItem key={d} value={d}>{d}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.district && <p className="text-xs text-red-700 mt-1">{errors.district}</p>}
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-aayna-charcoal mb-1.5">Full Address *</label>
                <textarea data-testid="checkout-address" rows={3} className={`${inputCls("delivery_address")} h-auto py-2.5 resize-none`} value={form.delivery_address} onChange={(e) => set("delivery_address", e.target.value)} placeholder="House, road, area, landmark..." />
                {errors.delivery_address && <p className="text-xs text-red-700 mt-1">{errors.delivery_address}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-aayna-charcoal mb-1.5">Email (optional)</label>
                <input data-testid="checkout-email" type="email" className={inputCls("customer_email")} value={form.customer_email} onChange={(e) => set("customer_email", e.target.value)} placeholder="you@email.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-aayna-charcoal mb-1.5">Delivery Note (optional)</label>
                <input data-testid="checkout-note" className={inputCls("delivery_note")} value={form.delivery_note} onChange={(e) => set("delivery_note", e.target.value)} placeholder="Any instructions?" />
              </div>
            </div>
          </div>

          {/* Payment */}
          <div className="bg-white border border-aayna-beige p-5 sm:p-6">
            <h2 className="font-display text-xl font-bold text-aayna-charcoal mb-4">Payment Method</h2>
            <RadioGroup value={form.payment_method} onValueChange={(v) => set("payment_method", v)} className="space-y-3">
              {PAYMENTS.map((p) => (
                <label
                  key={p.value}
                  data-testid={`payment-${p.value}`}
                  className={`flex items-start gap-3 border p-4 cursor-pointer transition-colors ${
                    form.payment_method === p.value ? "border-aayna-rose bg-aayna-mist/40" : "border-aayna-beige"
                  }`}
                >
                  <RadioGroupItem value={p.value} className="mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium text-aayna-charcoal text-sm">{p.label}</p>
                    <p className="text-xs text-aayna-taupe mt-0.5">{p.desc}</p>
                    {form.payment_method === p.value && p.value !== "cod" && (
                      <div className="mt-3 space-y-3" onClick={(e) => e.preventDefault()}>
                        <div className="bg-aayna-cream border border-aayna-beige p-3 text-sm">
                          Send money to{" "}
                          <span className="font-semibold text-aayna-rose">
                            {p.value === "bkash" ? settings?.bkash_number : settings?.nagad_number}
                          </span>{" "}
                          ({p.value === "bkash" ? "bKash" : "Nagad"} Personal). Transaction ID is optional — our team verifies manually.
                        </div>
                        <input
                          data-testid="checkout-transaction-id"
                          className="w-full h-11 border border-aayna-beige bg-white px-3 text-sm outline-none focus:border-aayna-rose"
                          placeholder="Transaction ID (optional)"
                          value={form.transaction_id}
                          onChange={(e) => set("transaction_id", e.target.value)}
                        />
                        <input
                          className="w-full h-11 border border-aayna-beige bg-white px-3 text-sm outline-none focus:border-aayna-rose"
                          placeholder="Your bKash/Nagad number (optional)"
                          value={form.sender_number}
                          onChange={(e) => set("sender_number", e.target.value)}
                        />
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </RadioGroup>
          </div>
        </div>

        {/* Summary */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-aayna-beige p-5 sm:p-6 sticky top-24">
            <h2 className="font-display text-xl font-bold text-aayna-charcoal mb-4">Your Order</h2>
            <div className="space-y-3 max-h-64 overflow-y-auto no-scrollbar mb-4">
              {items.map((i) => (
                <div key={i.product_id} className="flex gap-3">
                  <div className="h-14 w-14 flex-shrink-0 bg-aayna-cream overflow-hidden relative">
                    <img src={i.image} alt={i.name} className="w-full h-full object-cover" />
                    <span className="absolute -top-1 -right-1 bg-aayna-rose text-white text-[10px] h-4 min-w-4 px-1 rounded-full flex items-center justify-center">{i.quantity}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-aayna-charcoal line-clamp-1">{i.name}</p>
                    <p className="text-xs text-aayna-taupe">{formatBDT(i.unit_price)} × {i.quantity}</p>
                  </div>
                  <span className="text-sm font-medium text-aayna-charcoal">{formatBDT(i.unit_price * i.quantity)}</span>
                </div>
              ))}
            </div>
            <div className="border-t border-aayna-beige pt-4 space-y-2.5 text-sm">
              <div className="flex justify-between"><span className="text-aayna-taupe">Subtotal</span><span className="font-semibold">{formatBDT(subtotal)}</span></div>
              <div className="flex justify-between">
                <span className="text-aayna-taupe">Delivery {form.district ? `(${form.district})` : ""}</span>
                <span data-testid="checkout-delivery" className="font-semibold">{form.district ? formatBDT(deliveryCharge) : "—"}</span>
              </div>
            </div>
            <div className="border-t border-aayna-beige mt-4 pt-4 flex justify-between items-baseline">
              <span className="font-semibold text-aayna-charcoal">Total</span>
              <span data-testid="checkout-total" className="font-bold text-aayna-rose text-xl">{formatBDT(total)}</span>
            </div>
            <button
              data-testid="place-order-button"
              type="submit"
              disabled={submitting}
              className="mt-5 w-full h-12 bg-aayna-rose text-white font-semibold hover:bg-aayna-rose-dark transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting ? "Placing Order..." : "Confirm Order"}
            </button>
            <p className="text-xs text-aayna-taupe text-center mt-3">No account needed. We'll confirm your order shortly.</p>
          </div>
        </div>
      </form>
    </div>
  );
}
