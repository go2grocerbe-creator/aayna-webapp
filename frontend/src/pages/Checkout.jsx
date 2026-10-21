import { useState, useRef, useMemo, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Check } from "lucide-react";
import { getDistricts } from "@/lib/api";
import { validateCartWithSession as validateCart, checkoutWithSession as checkout, listAddresses } from "@/lib/customerApi";
import { useCustomer } from "@/context/CustomerAuthContext";
import { useSettings } from "@/hooks/useStore";
import { useCart } from "@/context/CartContext";
import { formatBDT, isPlaceholder } from "@/lib/format";
import ProductImage from "@/components/ProductImage";
import { deliveryPolicy, deliveryFor } from "@/lib/delivery";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useSeo } from "@/lib/seo";

// D5 - function-first checkout. Same single-scroll-form architecture as
// before (there is no real hide/show wizard here to preserve - every
// section has always been visible in one <form>, one submit). This pass
// keeps that exact interaction model and layers on: a numbered progress
// strip derived from existing validation state (not a new state machine),
// quiet scroll-to-section "back" links instead of a fake step transition,
// and calmer D2-D4-consistent presentation. Validation rules, field set,
// payment gating, delivery calculation, and the order request itself are
// untouched.
const PHONE_RE = /^(?:\+?880|0)1[3-9]\d{8}$/;

const PAYMENTS = [
  { value: "cod", label: "Cash on Delivery", desc: "Pay in cash when your order arrives." },
  { value: "bkash", label: "bKash (Manual)", desc: "Send money, then add your transaction ID." },
  { value: "nagad", label: "Nagad (Manual)", desc: "Send money, then add your transaction ID." },
];

const STEPS = [
  { key: "contact", num: "01", label: "Contact" },
  { key: "delivery", num: "02", label: "Delivery" },
  { key: "payment", num: "03", label: "Payment" },
  { key: "summary", num: "04", label: "Summary" },
];

const FIELD_TESTID = {
  customer_name: "checkout-name",
  customer_phone: "checkout-phone",
  district: "checkout-district",
  delivery_address: "checkout-address",
};

export default function Checkout() {
  const navigate = useNavigate();
  const { items, subtotal, clearCart, refreshPrices } = useCart();
  // Same server price check as the cart page, so a customer arriving here
  // directly never sees a stale browser-saved price (the order is always
  // charged at the server's current price).
  const { data: priceCheck } = useQuery({
    queryKey: ["cart-validate", items.map((i) => `${i.product_id}:${i.quantity}`).join(",")],
    queryFn: () =>
      validateCart({ items: items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })) }),
    enabled: items.length > 0,
  });
  useEffect(() => {
    if (priceCheck?.items) refreshPrices(priceCheck.items);
  }, [priceCheck, refreshPrices]);
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
  const { account, signedIn } = useCustomer();
  const { data: addresses = [] } = useQuery({ queryKey: ["account-addresses"], queryFn: listAddresses, enabled: signedIn });
  const [couponInput, setCouponInput] = useState("");
  const [coupon, setCoupon] = useState(null); // {code, discount} once the server accepts it
  const [couponMsg, setCouponMsg] = useState(null);
  const [couponLoading, setCouponLoading] = useState(false);

  // Signed-in customers: prefill once from the profile and default address (still editable).
  const prefilled = useRef(false);
  useEffect(() => {
    if (!account || prefilled.current) return;
    prefilled.current = true;
    const addr = account.default_address;
    setForm((f) => ({
      ...f,
      customer_name: f.customer_name || addr?.recipient_name || account.full_name || "",
      customer_phone: f.customer_phone || (addr?.phone || account.phone || "").replace(/^\+880/, "0"),
      customer_email: f.customer_email || account.email || "",
      district: f.district || addr?.district || "",
      delivery_address: f.delivery_address || addr?.address || "",
      delivery_note: f.delivery_note || addr?.instructions || "",
    }));
  }, [account]);

  const pickAddress = (id) => {
    const a = addresses.find((x) => x.id === id);
    if (!a) return;
    setForm((f) => ({ ...f, customer_name: a.recipient_name, customer_phone: a.phone.replace(/^\+880/, "0"),
                      district: a.district, delivery_address: a.address, delivery_note: a.instructions || "" }));
    setErrors({});
  };

  const applyCoupon = async (code = couponInput) => {
    const c = (code || "").trim();
    if (!c) return;
    setCouponLoading(true);
    setCouponMsg(null);
    try {
      const r = await validateCart({
        items: items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
        coupon_code: c, phone: form.customer_phone || undefined,
      });
      if (r.coupon?.valid) {
        setCoupon({ code: r.coupon.code, discount: r.coupon.discount });
        setCouponMsg({ tone: "ok", text: `${r.coupon.code} applied` });
      } else {
        setCoupon(null);
        setCouponMsg({ tone: "error", text: r.coupon?.message || "This code isn't valid." });
      }
    } catch (err) {
      setCoupon(null);
      setCouponMsg({ tone: "error", text: err?.response?.data?.detail || "We couldn't check this code. Please try again." });
    } finally {
      setCouponLoading(false);
    }
  };
  const removeCoupon = () => { setCoupon(null); setCouponMsg(null); setCouponInput(""); };
  // The cart changed: re-check the code against the new items (server decides).
  const itemsKey = items.map((i) => `${i.product_id}:${i.quantity}`).join(",");
  useEffect(() => {
    if (coupon) applyCoupon(coupon.code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsKey]);

  useSeo({ title: "Checkout", description: "Complete your AAYNA order securely.", noindex: true });

  const set = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  // Nationwide rule on the merchandise subtotal BEFORE the discount (server decides at order time).
  const delivery = useMemo(
    () => deliveryFor(subtotal, deliveryPolicy(priceCheck?.delivery_policy ? priceCheck : settings)),
    [subtotal, priceCheck, settings]
  );
  const deliveryCharge = delivery.charge;

  const discount = coupon ? Math.min(coupon.discount, subtotal) : 0;
  const total = subtotal - discount + deliveryCharge;

  // Presentation-only progress read from the same fields/validation the
  // form already has - not a second source of truth, not a gate.
  const cleanedPhone = form.customer_phone.replace(/[\s-]/g, "");
  const contactDone = !!form.customer_name.trim() && PHONE_RE.test(cleanedPhone);
  const deliveryDone = !!form.district && !!form.delivery_address.trim();
  const paymentDone = !!form.payment_method;
  const stepStatus = (key) => {
    if (key === "contact") return contactDone ? "complete" : "current";
    if (key === "delivery") return !contactDone ? "upcoming" : deliveryDone ? "complete" : "current";
    if (key === "payment") return !(contactDone && deliveryDone) ? "upcoming" : paymentDone ? "complete" : "current";
    return contactDone && deliveryDone && paymentDone ? "current" : "upcoming";
  };
  const goToSection = (key) => {
    document.getElementById(`checkout-section-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const validate = () => {
    const e = {};
    if (!form.customer_name.trim()) e.customer_name = "Full name is required";
    if (!form.customer_phone.trim()) e.customer_phone = "Phone number is required";
    else if (!PHONE_RE.test(cleanedPhone))
      e.customer_phone = "Enter a valid Bangladesh number (e.g. 01712345678)";
    if (!form.district) e.district = "Please select your district";
    if (!form.delivery_address.trim()) e.delivery_address = "Delivery address is required";
    if (!form.payment_method) e.payment_method = "Select a payment method";
    setErrors(e);
    if (Object.keys(e).length > 0) {
      const firstKey = Object.keys(FIELD_TESTID).find((k) => e[k]);
      const target = firstKey
        ? document.querySelector(`[data-testid="${FIELD_TESTID[firstKey]}"]`)
        : document.getElementById("checkout-section-payment");
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
      target?.focus?.();
    }
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    if (submitting) return;
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
        coupon_code: coupon?.code || undefined,
      });
      clearCart();
      const token = encodeURIComponent(res.order_confirmation_token || "");
      navigate(`/order-confirmation/${res.order_number}?token=${token}`);
    } catch (err) {
      const msg = err?.response?.data?.detail || "Something went wrong. Please try again.";
      toast.error(msg);
      setSubmitting(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-32 text-center">
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">AAYNA · Checkout</p>
        <h1 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark">Checkout</h1>
        <p className="text-aayna-taupe text-sm mt-3">Nothing to check out.</p>
        <Link
          to="/shop"
          className="inline-flex items-center gap-1.5 mt-7 text-aayna-burgundy font-medium min-h-[44px] hover:underline underline-offset-2"
        >
          Return to The Edit <span aria-hidden="true">→</span>
        </Link>
      </div>
    );
  }

  const inputCls = (key) =>
    `w-full h-11 border bg-white px-3 text-aayna-charcoal text-[15px] outline-none focus:border-aayna-burgundy focus:ring-1 focus:ring-aayna-burgundy ${
      errors[key] ? "border-red-500" : "border-aayna-beige"
    }`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-16">
      <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">The Selection · Checkout</p>
      <h1 className="font-display font-semibold text-3xl md:text-5xl text-aayna-burgundy-dark mb-8 md:mb-10">Checkout</h1>

      {/* Progress strip - reflects real form state, not a hidden-step gate */}
      {/* Phones: an even 2x2 grid (a wrapping row left "04 Summary" orphaned on its own line). */}
      <nav aria-label="Checkout progress" className="grid grid-cols-2 gap-x-4 sm:flex sm:flex-wrap sm:gap-x-6 gap-y-0 border-y border-aayna-beige py-2 mb-10 md:mb-14">
        {STEPS.map((s) => {
          const status = stepStatus(s.key);
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => goToSection(s.key)}
              className={`inline-flex items-center gap-1.5 text-xs font-bold tracking-[0.14em] uppercase min-h-[44px] transition-colors ${
                status === "current"
                  ? "text-aayna-burgundy"
                  : status === "complete"
                  ? "text-aayna-charcoal"
                  : "text-aayna-taupe/70"
              }`}
            >
              {status === "complete" ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <span aria-hidden="true">{s.num}</span>}
              {s.label}
            </button>
          );
        })}
      </nav>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-10 md:gap-12">
        {/* Form fields */}
        <div className="md:col-span-7 space-y-10">
          <div id="checkout-section-contact">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-1">01 — Contact</p>
            <h2 className="font-display text-xl font-semibold text-aayna-burgundy-dark mb-4 pb-3 border-b border-aayna-beige">Contact</h2>
            {signedIn ? (
              <p className="text-xs text-aayna-taupe mb-4" data-testid="checkout-signed-in">Signed in as <span className="text-aayna-charcoal break-all">{account.email}</span> - this order will appear in your account.</p>
            ) : (
              <p className="text-xs text-aayna-taupe mb-4">Have an account? <Link to="/login?next=/checkout" className="text-aayna-burgundy underline underline-offset-2">Sign in</Link> to track this order in My AAYNA. Or continue as a guest.</p>
            )}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label htmlFor="checkout-name" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Full Name *</label>
                <input
                  id="checkout-name"
                  data-testid="checkout-name"
                  autoComplete="name"
                  className={inputCls("customer_name")}
                  value={form.customer_name}
                  onChange={(e) => set("customer_name", e.target.value)}
                  placeholder="Your full name"
                  aria-invalid={!!errors.customer_name}
                  aria-describedby={errors.customer_name ? "checkout-name-error" : undefined}
                />
                {errors.customer_name && <p id="checkout-name-error" className="text-xs text-red-700 mt-1">{errors.customer_name}</p>}
              </div>
              <div>
                <label htmlFor="checkout-phone" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Phone Number *</label>
                <input
                  id="checkout-phone"
                  data-testid="checkout-phone"
                  type="tel"
                  autoComplete="tel"
                  className={inputCls("customer_phone")}
                  value={form.customer_phone}
                  onChange={(e) => set("customer_phone", e.target.value)}
                  placeholder="01712345678"
                  aria-invalid={!!errors.customer_phone}
                  aria-describedby={errors.customer_phone ? "checkout-phone-error" : undefined}
                />
                {errors.customer_phone && <p id="checkout-phone-error" className="text-xs text-red-700 mt-1">{errors.customer_phone}</p>}
              </div>
              <div>
                <label htmlFor="checkout-email" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Email (optional)</label>
                <input
                  id="checkout-email"
                  data-testid="checkout-email"
                  type="email"
                  autoComplete="email"
                  className={inputCls("customer_email")}
                  value={form.customer_email}
                  onChange={(e) => set("customer_email", e.target.value)}
                  placeholder="you@email.com"
                />
              </div>
            </div>
          </div>

          <div id="checkout-section-delivery">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-1">02 — Delivery</p>
            <h2 className="font-display text-xl font-semibold text-aayna-burgundy-dark mb-4 pb-3 border-b border-aayna-beige">Delivery Information</h2>
            {addresses.length > 0 && (
              <div className="mb-4">
                <label htmlFor="checkout-saved-address" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Saved addresses</label>
                <select id="checkout-saved-address" data-testid="checkout-saved-address" defaultValue="" onChange={(e) => pickAddress(e.target.value)}
                        className="w-full h-11 border border-aayna-beige bg-white px-3 text-aayna-charcoal text-[15px] outline-none focus:border-aayna-burgundy">
                  <option value="" disabled>Choose a saved address</option>
                  {addresses.map((a) => <option key={a.id} value={a.id}>{(a.label ? `${a.label} - ` : "") + `${a.recipient_name}, ${a.district}`}</option>)}
                </select>
              </div>
            )}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label htmlFor="checkout-district" className="block text-sm font-medium text-aayna-charcoal mb-1.5">District *</label>
                <Select value={form.district} onValueChange={(v) => set("district", v)}>
                  <SelectTrigger
                    id="checkout-district"
                    data-testid="checkout-district"
                    aria-invalid={!!errors.district}
                    aria-describedby={errors.district ? "checkout-district-error" : undefined}
                    className={`h-11 bg-white ${errors.district ? "border-red-500" : "border-aayna-beige"}`}
                  >
                    <SelectValue placeholder="Select district" />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {districts.map((d) => (
                      <SelectItem key={d} value={d}>{d}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.district && <p id="checkout-district-error" className="text-xs text-red-700 mt-1">{errors.district}</p>}
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="checkout-address" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Full Address *</label>
                <textarea
                  id="checkout-address"
                  data-testid="checkout-address"
                  autoComplete="street-address"
                  rows={3}
                  className={`${inputCls("delivery_address")} h-auto py-2.5 resize-none`}
                  value={form.delivery_address}
                  onChange={(e) => set("delivery_address", e.target.value)}
                  placeholder="House, road, area, landmark..."
                  aria-invalid={!!errors.delivery_address}
                  aria-describedby={errors.delivery_address ? "checkout-address-error" : undefined}
                />
                {errors.delivery_address && <p id="checkout-address-error" className="text-xs text-red-700 mt-1">{errors.delivery_address}</p>}
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="checkout-note" className="block text-sm font-medium text-aayna-charcoal mb-1.5">Delivery Note (optional)</label>
                <input
                  id="checkout-note"
                  data-testid="checkout-note"
                  className={inputCls("delivery_note")}
                  value={form.delivery_note}
                  onChange={(e) => set("delivery_note", e.target.value)}
                  placeholder="Any instructions?"
                />
              </div>
            </div>
          </div>

          {/* Payment */}
          <div id="checkout-section-payment">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-1">03 — Payment</p>
            <h2 className="font-display text-xl font-semibold text-aayna-burgundy-dark mb-4 pb-3 border-b border-aayna-beige">Payment Method</h2>
            <RadioGroup value={form.payment_method} onValueChange={(v) => set("payment_method", v)} className="space-y-3">
              {PAYMENTS.filter((p) => p.value === "cod" || !isPlaceholder(p.value === "bkash" ? settings?.bkash_number : settings?.nagad_number)).map((p) => {
                // 21 Oct 2026: only Cash on Delivery is approved. bKash/Nagad stay hidden
                // unless a real number is configured (and a separate founder decision enables them).
                const manualNumber = p.value === "bkash" ? settings?.bkash_number : settings?.nagad_number;
                // L3.1: cod_available now actually gates COD, not just bKash/Nagad's
                // existing placeholder-number gate. Fails OPEN (available) while
                // settings are still loading or the flag is missing entirely, so a
                // slow/failed settings fetch can never make checkout impossible -
                // only an explicit settings.cod_available === false disables it.
                const codDisabled = settings ? settings.cod_available === false : false;
                const notConfigured = p.value === "cod" ? codDisabled : isPlaceholder(manualNumber);
                return (
                  <label
                    key={p.value}
                    data-testid={`payment-${p.value}`}
                    className={`flex items-start gap-3 border p-4 transition-colors ${
                      notConfigured ? "border-aayna-beige opacity-60 cursor-not-allowed" : "cursor-pointer"
                    } ${
                      form.payment_method === p.value && !notConfigured ? "border-aayna-burgundy bg-aayna-mist/40" : "border-aayna-beige"
                    }`}
                  >
                    <RadioGroupItem value={p.value} disabled={notConfigured} className="mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-aayna-charcoal text-sm">{p.label}</p>
                      <p className="text-xs text-aayna-taupe mt-0.5">
                        {notConfigured
                          ? p.value === "cod"
                            ? "Not available right now."
                            : "Not available yet — choose Cash on Delivery for now."
                          : p.desc}
                      </p>
                      {form.payment_method === p.value && p.value !== "cod" && !notConfigured && (
                        <div className="mt-3 space-y-3" onClick={(e) => e.preventDefault()}>
                          <div className="bg-aayna-cream border border-aayna-beige p-3 text-sm">
                            Send money to{" "}
                            <span className="font-semibold text-aayna-burgundy">{manualNumber}</span>{" "}
                            ({p.value === "bkash" ? "bKash" : "Nagad"} Personal). Transaction ID is optional — our team verifies manually.
                          </div>
                          <input
                            data-testid="checkout-transaction-id"
                            className="w-full h-11 border border-aayna-beige bg-white px-3 text-sm outline-none focus:border-aayna-burgundy"
                            placeholder="Transaction ID (optional)"
                            value={form.transaction_id}
                            onChange={(e) => set("transaction_id", e.target.value)}
                          />
                          <input
                            className="w-full h-11 border border-aayna-beige bg-white px-3 text-sm outline-none focus:border-aayna-burgundy"
                            placeholder="Your bKash/Nagad number (optional)"
                            value={form.sender_number}
                            onChange={(e) => set("sender_number", e.target.value)}
                          />
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </RadioGroup>
          </div>
        </div>

        {/* Summary - anchored by hairlines, not a boxed card, matching The Selection */}
        <div className="md:col-span-5" id="checkout-section-summary">
          <div className="md:sticky md:top-28">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-1">04 — Summary</p>
            <h2 className="font-display text-xl font-semibold text-aayna-burgundy-dark mb-4 pb-3 border-b border-aayna-beige">Order Summary</h2>
            <div className="space-y-3 max-h-64 overflow-y-auto no-scrollbar mb-4" aria-label="Items in your order">
              {items.map((i) => (
                <div key={i.product_id} className="flex gap-3">
                  <div className="relative flex-shrink-0">
                    <ProductImage src={i.image} alt={i.name} className="h-14 w-14" iconClassName="h-4 w-4" />
                    <span className="absolute -top-1 -right-1 bg-aayna-burgundy text-white text-[10px] h-4 min-w-4 px-1 rounded-full flex items-center justify-center">{i.quantity}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-aayna-charcoal line-clamp-1">{i.name}</p>
                    <p className="text-xs text-aayna-taupe">{formatBDT(i.unit_price)} × {i.quantity}</p>
                  </div>
                  <span className="text-sm font-medium text-aayna-charcoal">{formatBDT(i.unit_price * i.quantity)}</span>
                </div>
              ))}
            </div>
            <div className="border-t border-aayna-beige pt-4 pb-4" data-testid="checkout-coupon">
              {coupon ? (
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-emerald-800 font-medium">Code {coupon.code} applied</span>
                  <button type="button" onClick={removeCoupon} className="min-h-[44px] text-aayna-taupe hover:text-aayna-burgundy underline-offset-2 hover:underline">Remove</button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <label htmlFor="checkout-coupon-input" className="sr-only">Discount code</label>
                  <input id="checkout-coupon-input" data-testid="checkout-coupon-input" value={couponInput} autoComplete="off" autoCapitalize="characters"
                         onChange={(e) => { setCouponInput(e.target.value); setCouponMsg(null); }}
                         onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); applyCoupon(); } }}
                         placeholder="Discount code" maxLength={40}
                         className="flex-1 min-w-0 h-11 border border-aayna-beige bg-white px-3 text-sm uppercase outline-none focus:border-aayna-burgundy focus:ring-1 focus:ring-aayna-burgundy" />
                  <button type="button" onClick={() => applyCoupon()} disabled={couponLoading || !couponInput.trim()} data-testid="checkout-coupon-apply"
                          className="h-11 px-4 border border-aayna-burgundy text-aayna-burgundy text-sm font-semibold disabled:opacity-50 flex items-center gap-1.5">
                    {couponLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}Apply
                  </button>
                </div>
              )}
              {couponMsg?.tone === "error" && <p role="alert" data-testid="checkout-coupon-error" className="text-xs text-red-700 mt-1.5">{couponMsg.text}</p>}
            </div>
            <div className="border-t border-aayna-beige pt-4 space-y-2.5 text-sm">
              <div className="flex justify-between"><span className="text-aayna-taupe">Subtotal</span><span className="font-semibold">{formatBDT(subtotal)}</span></div>
              {discount > 0 && <div className="flex justify-between text-emerald-800" data-testid="checkout-discount"><span>Discount ({coupon.code})</span><span className="font-semibold">−{formatBDT(discount)}</span></div>}
              <div className="flex justify-between">
                <span className="text-aayna-taupe">Delivery</span>
                <span data-testid="checkout-delivery" className={`font-semibold ${delivery.free ? "text-emerald-800" : ""}`}>{delivery.free ? "Free" : formatBDT(deliveryCharge)}</span>
              </div>
              {!delivery.free && delivery.remaining > 0 && (
                <p data-testid="checkout-free-delivery-hint" className="text-xs text-aayna-taupe">
                  Add {formatBDT(delivery.remaining)} more for free delivery.
                </p>
              )}
            </div>
            <div className="border-t border-aayna-beige mt-4 pt-4 flex justify-between items-baseline">
              <span className="font-display text-lg text-aayna-charcoal">Total</span>
              <span data-testid="checkout-total" className="font-display text-2xl font-semibold text-aayna-burgundy">{formatBDT(total)}</span>
            </div>
            <button
              data-testid="place-order-button"
              type="submit"
              disabled={submitting}
              aria-busy={submitting}
              className="mt-5 w-full h-12 md:h-14 bg-aayna-coral text-white font-semibold hover:bg-aayna-coral-dark active:bg-aayna-coral-pressed transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {submitting ? "Placing Order..." : "Place Order"}
            </button>
            <p className="text-xs text-aayna-taupe text-center mt-3">{signedIn ? "We'll confirm your order shortly." : "No account needed. We'll confirm your order shortly."}</p>
          </div>
        </div>
      </form>
    </div>
  );
}
