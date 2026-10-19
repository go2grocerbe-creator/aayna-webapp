import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Package, MapPin, User, ShieldCheck, Gift, LayoutGrid, LogOut, Plus, Pencil, Trash2, ChevronRight, ShoppingBag } from "lucide-react";
import { useCustomer } from "@/context/CustomerAuthContext";
import {
  listOrders, getAccountOrder, listAddresses, addAddress, updateAddress, deleteAddress, updateProfile, getSecurity,
  changePassword, requestEmailChange, revokeOtherSessions, revokeSession, logoutAll, unlinkGoogle, requestDeletion,
  getRewards, claimOrder, claimOrderByEmail, googleStartUrl, apiError,
} from "@/lib/customerApi";
import { getDistricts } from "@/lib/api";
import { formatBDT, customerStatusLabel } from "@/lib/format";
import { useSeo } from "@/lib/seo";
import { Field, PasswordField, SubmitButton, Notice, Spinner, inputClass } from "@/components/account/ui";
import OrderTimeline, { formatDhakaDateTime } from "@/components/account/OrderTimeline";
import ProductImage from "@/components/ProductImage";

const NAV = [
  { to: "/account", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/account/orders", label: "Orders", icon: Package },
  { to: "/account/addresses", label: "Addresses", icon: MapPin },
  { to: "/account/profile", label: "Profile", icon: User },
  { to: "/account/security", label: "Security", icon: ShieldCheck },
  { to: "/account/rewards", label: "Rewards", icon: Gift },
];
const ACTIVE = new Set(["New", "Confirmed", "Packed", "Sent to Courier"]);
const date = (iso) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Dhaka" }) : "");

function StatusPill({ status }) {
  const stopped = status === "Cancelled" || status === "Returned";
  return (
    <span className={`text-[11px] font-semibold px-2.5 py-1 uppercase tracking-wide whitespace-nowrap ${stopped ? "text-red-700 border border-red-200" : status === "Delivered" ? "text-emerald-800 border border-emerald-200" : "text-aayna-burgundy border border-aayna-burgundy/30"}`}>
      {customerStatusLabel(status)}
    </span>
  );
}

function SectionTitle({ children, action }) {
  return (
    <div className="flex items-center justify-between gap-4 mb-5 pb-3 border-b border-aayna-beige">
      <h2 className="font-display text-xl md:text-2xl font-semibold text-aayna-burgundy-dark">{children}</h2>
      {action}
    </div>
  );
}

function Empty({ icon: Icon, title, text, action, testid }) {
  return (
    <div data-testid={testid} className="text-center py-12 px-4 border border-dashed border-aayna-beige">
      <Icon className="h-6 w-6 text-aayna-taupe mx-auto mb-3" aria-hidden="true" />
      <p className="font-display text-lg text-aayna-charcoal">{title}</p>
      {text && <p className="text-sm text-aayna-taupe mt-1.5 max-w-sm mx-auto">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

function LoadFailed({ onRetry }) {
  return <Notice tone="error" testid="account-load-error">We couldn't load this right now. <button type="button" onClick={onRetry} className="underline font-semibold">Try again</button></Notice>;
}

// ---------------------------------------------------------------------------
export function AccountLayout() {
  const { loading, signedIn, account, logout } = useCustomer();
  const location = useLocation();
  const navigate = useNavigate();
  useSeo({ title: "My AAYNA", description: "Your AAYNA account.", noindex: true });
  if (loading) return <Spinner label="Loading your account" />;
  if (!signedIn) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  const doLogout = async () => {
    await logout();
    toast.success("You're signed out.");
    navigate("/", { replace: true });
  };
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-14" data-testid="account-area">
      <div className="mb-6 md:mb-10">
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">My AAYNA</p>
        <h1 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark break-words">Hello, {(account.full_name || "there").split(" ")[0]}</h1>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 md:gap-10">
        <nav aria-label="Account" className="md:col-span-3 min-w-0">
          <ul className="flex md:flex-col gap-1 overflow-x-auto no-scrollbar -mx-4 px-4 md:mx-0 md:px-0 border-b md:border-b-0 border-aayna-beige">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to} className="flex-shrink-0">
                <NavLink to={to} end={end} data-testid={`account-nav-${label.toLowerCase()}`}
                         className={({ isActive }) => `flex items-center gap-2.5 min-h-[44px] px-3 text-sm font-medium whitespace-nowrap border-b-2 md:border-b-0 md:border-l-2 transition-colors ${
                           isActive ? "border-aayna-burgundy text-aayna-burgundy md:bg-aayna-mist/50" : "border-transparent text-aayna-charcoal hover:text-aayna-burgundy"}`}>
                  <Icon className="h-4 w-4" aria-hidden="true" />{label}
                </NavLink>
              </li>
            ))}
            <li className="flex-shrink-0 md:mt-4 md:pt-4 md:border-t md:border-aayna-beige">
              <button type="button" onClick={doLogout} data-testid="account-logout"
                      className="flex items-center gap-2.5 min-h-[44px] px-3 text-sm font-medium text-aayna-taupe hover:text-aayna-burgundy whitespace-nowrap">
                <LogOut className="h-4 w-4" aria-hidden="true" />Sign out
              </button>
            </li>
          </ul>
        </nav>
        <div className="md:col-span-9 min-w-0">
          {!account.email_verified && <div className="mb-6"><Notice tone="info">Please confirm your email address to finish setting up your account.</Notice></div>}
          <Outlet />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function OrderRow({ o }) {
  return (
    <Link to={`/account/orders/${o.order_number}`} data-testid={`account-order-${o.order_number}`}
          className="flex items-center gap-4 py-4 border-b border-aayna-beige hover:bg-aayna-mist/30 transition-colors -mx-2 px-2 min-w-0">
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-display text-lg font-semibold text-aayna-charcoal">{o.order_number}</span>
          <StatusPill status={o.order_status} />
        </div>
        <p className="text-xs text-aayna-taupe mt-1 truncate">
          {date(o.created_at)} · {(() => { const n = o.items.reduce((t, it) => t + it.quantity, 0); return `${n} ${n === 1 ? "item" : "items"}`; })()} · {o.items.map((it) => it.product_name).join(", ")}
        </p>
      </div>
      <span className="font-semibold text-aayna-burgundy whitespace-nowrap">{formatBDT(o.total_amount)}</span>
      <ChevronRight className="h-4 w-4 text-aayna-taupe flex-shrink-0" aria-hidden="true" />
    </Link>
  );
}

export function AccountHome() {
  const { account } = useCustomer();
  const orders = useQuery({ queryKey: ["account-orders"], queryFn: listOrders });
  const rewards = useQuery({ queryKey: ["account-rewards"], queryFn: getRewards });
  const latest = (orders.data || [])[0];
  const active = (orders.data || []).filter((o) => ACTIVE.has(o.order_status));
  const coupons = (rewards.data?.coupons || []).filter((c) => c.state === "active");
  return (
    <div className="space-y-10" data-testid="account-home">
      <section>
        <SectionTitle action={<Link to="/account/orders" className="text-sm text-aayna-burgundy hover:underline underline-offset-2">All orders</Link>}>Your orders</SectionTitle>
        {orders.isLoading ? <Spinner /> : orders.isError ? <LoadFailed onRetry={orders.refetch} /> : !latest ? (
          <Empty testid="account-no-orders" icon={ShoppingBag} title="No orders yet" text="When you order while signed in, it appears here with its delivery progress."
                 action={<Link to="/shop" className="inline-flex min-h-[44px] items-center px-6 bg-aayna-coral text-white font-semibold">Shop the Edit</Link>} />
        ) : (
          <div>
            {active.length > 0 && <p className="text-sm text-aayna-taupe mb-2">{active.length} {active.length === 1 ? "order" : "orders"} in progress</p>}
            {(orders.data || []).slice(0, 3).map((o) => <OrderRow key={o.order_number} o={o} />)}
          </div>
        )}
      </section>
      {coupons.length > 0 && (
        <section>
          <SectionTitle>Your rewards</SectionTitle>
          <Link to="/account/rewards" className="block border border-aayna-burgundy/30 p-4 hover:bg-aayna-mist/40">
            <p className="font-semibold text-aayna-burgundy">You have {coupons.length} reward(s) ready to use</p>
            <p className="text-sm text-aayna-taupe mt-1">See the code and its conditions</p>
          </Link>
        </section>
      )}
      <section className="grid sm:grid-cols-2 gap-6">
        <div className="border border-aayna-beige p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-2">Account</p>
          <p className="font-medium text-aayna-charcoal break-words">{account.full_name}</p>
          <p className="text-sm text-aayna-taupe break-all">{account.email}</p>
          {account.phone && <p className="text-sm text-aayna-taupe">{account.phone.replace("+880", "0")}</p>}
          <Link to="/account/profile" className="inline-flex mt-3 min-h-[44px] items-center text-sm text-aayna-burgundy hover:underline underline-offset-2">Edit profile</Link>
        </div>
        <div className="border border-aayna-beige p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-2">Default address</p>
          {account.default_address ? (
            <>
              <p className="font-medium text-aayna-charcoal">{account.default_address.recipient_name}</p>
              <p className="text-sm text-aayna-taupe break-words">{account.default_address.address}, {account.default_address.district}</p>
            </>
          ) : <p className="text-sm text-aayna-taupe">No saved address yet.</p>}
          <Link to="/account/addresses" className="inline-flex mt-3 min-h-[44px] items-center text-sm text-aayna-burgundy hover:underline underline-offset-2">Manage addresses</Link>
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
function ClaimPanel() {
  const qc = useQueryClient();
  const [num, setNum] = useState("");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!num.trim()) return;
    setLoading(true);
    try {
      const r = await claimOrderByEmail(num.trim());
      setStatus({ tone: "success", text: r.message });
      qc.invalidateQueries({ queryKey: ["account-orders"] });
    } catch (err) {
      setStatus({ tone: "error", text: apiError(err).message });
    } finally {
      setLoading(false);
    }
  };
  return (
    <details className="mt-8 border border-aayna-beige p-4 group">
      <summary className="cursor-pointer text-sm font-medium text-aayna-charcoal min-h-[44px] flex items-center">Missing an order you placed as a guest?</summary>
      <p className="text-sm text-aayna-taupe mt-2 leading-relaxed">
        If you used this account's email address at checkout, we'll email you a link to add the order here. You can also add it from the
        order confirmation page right after ordering. For your privacy, a matching phone number alone isn't enough.
      </p>
      <form onSubmit={submit} className="mt-4 flex flex-col sm:flex-row gap-3" noValidate>
        <input aria-label="Order ID" placeholder="e.g. ORD-1001" value={num} onChange={(e) => setNum(e.target.value)} data-testid="claim-order-number" className={`${inputClass(false)} sm:flex-1`} />
        <button type="submit" disabled={loading} className="min-h-[48px] px-6 border border-aayna-burgundy text-aayna-burgundy font-semibold disabled:opacity-60">Email me a link</button>
      </form>
      {status && <div className="mt-3"><Notice tone={status.tone}>{status.text}</Notice></div>}
    </details>
  );
}

export function AccountOrders() {
  const orders = useQuery({ queryKey: ["account-orders"], queryFn: listOrders });
  const list = orders.data || [];
  const active = list.filter((o) => ACTIVE.has(o.order_status));
  const past = list.filter((o) => !ACTIVE.has(o.order_status));
  return (
    <div data-testid="account-orders">
      <SectionTitle>Orders</SectionTitle>
      {orders.isLoading ? <Spinner /> : orders.isError ? <LoadFailed onRetry={orders.refetch} /> : list.length === 0 ? (
        <Empty testid="account-orders-empty" icon={Package} title="No orders yet" text="Orders you place while signed in will appear here."
               action={<Link to="/shop" className="inline-flex min-h-[44px] items-center px-6 bg-aayna-coral text-white font-semibold">Shop the Edit</Link>} />
      ) : (
        <div className="space-y-8">
          {active.length > 0 && <div><h3 className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-1">In progress</h3>{active.map((o) => <OrderRow key={o.order_number} o={o} />)}</div>}
          {past.length > 0 && <div><h3 className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-1">Completed and cancelled</h3>{past.map((o) => <OrderRow key={o.order_number} o={o} />)}</div>}
        </div>
      )}
      <ClaimPanel />
    </div>
  );
}

export function AccountOrderDetail() {
  const { orderNumber } = useParams();
  const q = useQuery({ queryKey: ["account-order", orderNumber], queryFn: () => getAccountOrder(orderNumber), retry: false });
  if (q.isLoading) return <Spinner />;
  if (q.isError) {
    return <Empty testid="account-order-missing" icon={Package} title="Order not found" text="This order isn't in your account."
                  action={<Link to="/account/orders" className="text-aayna-burgundy font-medium hover:underline">Back to orders</Link>} />;
  }
  const o = q.data;
  return (
    <div data-testid="account-order-detail">
      <Link to="/account/orders" className="inline-flex min-h-[44px] items-center text-sm text-aayna-burgundy hover:underline underline-offset-2 mb-2">← All orders</Link>
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-aayna-beige">
        <div>
          <h2 className="font-display text-2xl font-semibold text-aayna-charcoal">{o.order_number}</h2>
          <p className="text-xs text-aayna-taupe mt-0.5">Placed {formatDhakaDateTime(o.created_at)}</p>
        </div>
        <StatusPill status={o.order_status} />
      </div>
      <div className="grid lg:grid-cols-2 gap-8 mt-6">
        <section aria-label="Delivery progress">
          <h3 className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-4">Progress</h3>
          <OrderTimeline timeline={o.timeline} />
          {o.courier_name && (
            <div className="mt-6 border border-aayna-beige p-4 text-sm" data-testid="account-order-courier">
              <p className="text-aayna-taupe text-xs uppercase tracking-wide mb-1">Courier</p>
              <p className="text-aayna-charcoal">{o.courier_name}</p>
              {o.courier_tracking_code && <p className="text-aayna-taupe break-all">Tracking reference: <span className="text-aayna-charcoal">{o.courier_tracking_code}</span></p>}
            </div>
          )}
        </section>
        <section aria-label="Order summary">
          <h3 className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-4">Items</h3>
          <div className="space-y-3">
            {o.items.map((it, i) => (
              <div key={i} className="flex gap-3 items-center">
                <ProductImage src={it.image} alt={it.product_name} className="h-14 w-14 flex-shrink-0" iconClassName="h-4 w-4" />
                <div className="flex-1 min-w-0"><p className="text-sm text-aayna-charcoal line-clamp-2">{it.product_name}</p><p className="text-xs text-aayna-taupe">{formatBDT(it.unit_price)} × {it.quantity}</p></div>
                <span className="text-sm font-medium">{formatBDT(it.total_price)}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-aayna-beige mt-4 pt-4 space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-aayna-taupe">Subtotal</span><span>{formatBDT(o.subtotal)}</span></div>
            {o.discount_amount > 0 && <div className="flex justify-between text-emerald-800" data-testid="account-order-discount"><span>Discount{o.coupon_code ? ` (${o.coupon_code})` : ""}</span><span>−{formatBDT(o.discount_amount)}</span></div>}
            <div className="flex justify-between"><span className="text-aayna-taupe">Delivery ({o.district})</span><span>{formatBDT(o.delivery_charge)}</span></div>
            <div className="flex justify-between font-semibold text-aayna-burgundy pt-2 border-t border-aayna-beige"><span>Total</span><span>{formatBDT(o.total_amount)}</span></div>
            <div className="flex justify-between"><span className="text-aayna-taupe">Payment</span><span className="text-right">{o.payment_method} · {String(o.payment_status || "").replace("_", " ")}</span></div>
          </div>
          <div className="mt-6 text-sm">
            <p className="text-xs uppercase tracking-[0.16em] text-aayna-taupe mb-1">Delivering to</p>
            <p className="text-aayna-charcoal">{o.customer_name}</p>
            <p className="text-aayna-taupe break-words">{o.delivery_address}, {o.district}</p>
          </div>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
const EMPTY_ADDR = { label: "", recipient_name: "", phone: "", district: "", address: "", instructions: "", is_default: false };

function AddressForm({ initial, onDone, onCancel }) {
  const { data: districts = [] } = useQuery({ queryKey: ["districts"], queryFn: getDistricts });
  const [form, setForm] = useState({ ...EMPTY_ADDR, ...initial, phone: (initial?.phone || "").replace("+880", "0") });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const set = (k, v) => { setForm((f) => ({ ...f, [k]: v })); setErrors((e) => ({ ...e, [k]: undefined })); };
  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const body = { label: form.label, recipient_name: form.recipient_name, phone: form.phone, district: form.district,
                     address: form.address, instructions: form.instructions, is_default: form.is_default };
      if (initial?.id) await updateAddress(initial.id, body); else await addAddress(body);
      onDone();
    } catch (err) {
      const e2 = apiError(err);
      setErrors(e2.fields || {});
      if (!Object.keys(e2.fields || {}).length) toast.error(e2.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <form onSubmit={submit} noValidate className="border border-aayna-beige p-4 sm:p-5 space-y-4" data-testid="address-form">
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="Label (optional)" placeholder="Home, Office…" value={form.label} maxLength={30} onChange={(e) => set("label", e.target.value)} />
        <Field label="Recipient name" required autoComplete="name" data-testid="address-name" value={form.recipient_name} error={errors.recipient_name} onChange={(e) => set("recipient_name", e.target.value)} />
        <Field label="Mobile number" required type="tel" autoComplete="tel" placeholder="01712345678" data-testid="address-phone" value={form.phone} error={errors.phone} onChange={(e) => set("phone", e.target.value)} />
        <Field label="District" required error={errors.district}>
          <select data-testid="address-district" value={form.district} onChange={(e) => set("district", e.target.value)} aria-invalid={!!errors.district} className={inputClass(errors.district)}>
            <option value="">Select district</option>
            {districts.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Full address" required error={errors.address}>
        <textarea data-testid="address-text" rows={3} autoComplete="street-address" maxLength={300} placeholder="House, road, area, landmark"
                  value={form.address} onChange={(e) => set("address", e.target.value)} aria-invalid={!!errors.address} className={`${inputClass(errors.address)} h-auto py-3 resize-none`} />
      </Field>
      <Field label="Delivery instructions (optional)" maxLength={200} value={form.instructions} onChange={(e) => set("instructions", e.target.value)} />
      <label className="flex items-center gap-3 text-sm min-h-[44px] cursor-pointer">
        <input type="checkbox" checked={form.is_default} onChange={(e) => set("is_default", e.target.checked)} className="h-4 w-4 accent-[#7a2238]" /> Use as my default address
      </label>
      <div className="flex flex-col sm:flex-row gap-3">
        <SubmitButton loading={loading} className="sm:w-auto sm:px-8" data-testid="address-save">Save address</SubmitButton>
        <button type="button" onClick={onCancel} className="min-h-[48px] px-6 text-aayna-taupe hover:text-aayna-burgundy">Cancel</button>
      </div>
    </form>
  );
}

export function AccountAddresses() {
  const qc = useQueryClient();
  const { refresh } = useCustomer();
  const q = useQuery({ queryKey: ["account-addresses"], queryFn: listAddresses });
  const [editing, setEditing] = useState(null);
  const done = () => { setEditing(null); qc.invalidateQueries({ queryKey: ["account-addresses"] }); refresh(); toast.success("Address saved"); };
  const remove = async (a) => {
    if (!window.confirm(`Delete the address for ${a.recipient_name}?`)) return;
    try { await deleteAddress(a.id); qc.invalidateQueries({ queryKey: ["account-addresses"] }); refresh(); } catch (err) { toast.error(apiError(err).message); }
  };
  const list = q.data || [];
  return (
    <div data-testid="account-addresses">
      <SectionTitle action={!editing && list.length < 10 && <button type="button" onClick={() => setEditing("new")} data-testid="address-add" className="inline-flex items-center gap-1.5 min-h-[44px] text-sm font-medium text-aayna-burgundy"><Plus className="h-4 w-4" aria-hidden="true" />Add address</button>}>
        Saved addresses
      </SectionTitle>
      {editing === "new" && <div className="mb-6"><AddressForm onDone={done} onCancel={() => setEditing(null)} /></div>}
      {q.isLoading ? <Spinner /> : q.isError ? <LoadFailed onRetry={q.refetch} /> : list.length === 0 && editing !== "new" ? (
        <Empty testid="addresses-empty" icon={MapPin} title="No saved addresses" text="Save an address to fill in checkout faster."
               action={<button type="button" onClick={() => setEditing("new")} className="min-h-[44px] px-6 bg-aayna-coral text-white font-semibold">Add an address</button>} />
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {list.map((a) => editing === a.id ? (
            <div key={a.id} className="sm:col-span-2"><AddressForm initial={a} onDone={done} onCancel={() => setEditing(null)} /></div>
          ) : (
            <div key={a.id} className="border border-aayna-beige p-4 flex flex-col" data-testid="address-card">
              <div className="flex items-center gap-2 mb-1">
                <p className="font-medium text-aayna-charcoal">{a.label || a.recipient_name}</p>
                {a.is_default && <span className="text-[10px] uppercase tracking-wide border border-aayna-burgundy/30 text-aayna-burgundy px-1.5 py-0.5">Default</span>}
              </div>
              <p className="text-sm text-aayna-taupe">{a.recipient_name} · {a.phone.replace("+880", "0")}</p>
              <p className="text-sm text-aayna-taupe break-words">{a.address}, {a.district}</p>
              {a.instructions && <p className="text-xs text-aayna-taupe mt-1 break-words">{a.instructions}</p>}
              <div className="flex gap-4 mt-auto pt-3">
                <button type="button" onClick={() => setEditing(a.id)} className="inline-flex items-center gap-1 min-h-[44px] text-sm text-aayna-burgundy"><Pencil className="h-3.5 w-3.5" aria-hidden="true" />Edit</button>
                <button type="button" onClick={() => remove(a)} className="inline-flex items-center gap-1 min-h-[44px] text-sm text-aayna-taupe hover:text-red-700"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" />Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
export function AccountProfile() {
  const { account, setAccount } = useCustomer();
  const [form, setForm] = useState({ full_name: account.full_name || "", phone: (account.phone || "").replace("+880", "0") });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [emailForm, setEmailForm] = useState({ new_email: "", current_password: "" });
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailErrors, setEmailErrors] = useState({});
  const save = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      setAccount(await updateProfile(form));
      setErrors({});
      toast.success("Profile updated");
    } catch (err) {
      const e2 = apiError(err);
      setErrors(e2.fields || {});
      if (!Object.keys(e2.fields || {}).length) toast.error(e2.message);
    } finally {
      setLoading(false);
    }
  };
  const changeEmail = async (e) => {
    e.preventDefault();
    try {
      const r = await requestEmailChange(emailForm);
      setEmailStatus({ tone: "success", text: r.message });
      setEmailErrors({});
      setEmailForm({ new_email: "", current_password: "" });
    } catch (err) {
      const e2 = apiError(err);
      setEmailErrors(e2.fields || {});
      setEmailStatus({ tone: "error", text: e2.message });
    }
  };
  return (
    <div className="space-y-10" data-testid="account-profile">
      <section>
        <SectionTitle>Profile</SectionTitle>
        <form onSubmit={save} noValidate className="space-y-4 max-w-lg">
          <Field label="Full name" autoComplete="name" maxLength={80} data-testid="profile-name" value={form.full_name} error={errors.full_name}
                 onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          <Field label="Mobile number" type="tel" autoComplete="tel" placeholder="01712345678" data-testid="profile-phone" value={form.phone} error={errors.phone}
                 onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <SubmitButton loading={loading} className="sm:w-auto sm:px-8" data-testid="profile-save">Save changes</SubmitButton>
        </form>
      </section>
      <section>
        <SectionTitle>Email address</SectionTitle>
        <p className="text-sm text-aayna-charcoal break-all">{account.email} {account.email_verified && <span className="text-emerald-800 text-xs ml-1">✓ Verified</span>}</p>
        {account.has_password ? (
          <form onSubmit={changeEmail} noValidate className="space-y-4 max-w-lg mt-5">
            {emailStatus && <Notice tone={emailStatus.tone}>{emailStatus.text}</Notice>}
            <Field label="New email address" type="email" autoComplete="email" value={emailForm.new_email} error={emailErrors.new_email}
                   onChange={(e) => setEmailForm({ ...emailForm, new_email: e.target.value })} />
            <PasswordField label="Current password" autoComplete="current-password" value={emailForm.current_password} error={emailErrors.current_password}
                           onChange={(e) => setEmailForm({ ...emailForm, current_password: e.target.value })} />
            <SubmitButton variant="secondary" className="sm:w-auto sm:px-8">Send confirmation link</SubmitButton>
            <p className="text-xs text-aayna-taupe">Your email changes only after you open the link we send to the new address.</p>
          </form>
        ) : <p className="text-sm text-aayna-taupe mt-2">This email comes from your Google account.</p>}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
export function AccountSecurity() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { account, refresh, setAccount } = useCustomer();
  const [params] = useSearchParams();
  const q = useQuery({ queryKey: ["account-security"], queryFn: getSecurity });
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [pwErrors, setPwErrors] = useState({});
  const [pwStatus, setPwStatus] = useState(null);
  const [pwLoading, setPwLoading] = useState(false);
  const googleParam = params.get("google");
  useEffect(() => { if (googleParam) { refresh(); qc.invalidateQueries({ queryKey: ["account-security"] }); } }, [googleParam, refresh, qc]);
  const sec = q.data;
  const reload = () => qc.invalidateQueries({ queryKey: ["account-security"] });

  const submitPw = async (e) => {
    e.preventDefault();
    setPwLoading(true);
    try {
      const r = await changePassword(pw);
      setPwStatus({ tone: "success", text: `Password ${sec?.has_password ? "changed" : "set"}. ${r.other_sessions_signed_out ? `Signed out of ${r.other_sessions_signed_out} other device(s).` : ""}` });
      setPw({ current_password: "", new_password: "", confirm_password: "" });
      setPwErrors({});
      refresh();
      reload();
    } catch (err) {
      const e2 = apiError(err);
      setPwErrors(e2.fields || {});
      setPwStatus({ tone: "error", text: e2.message });
    } finally {
      setPwLoading(false);
    }
  };
  const act = async (fn, ok) => { try { await fn(); toast.success(ok); reload(); } catch (err) { toast.error(apiError(err).message); } };

  if (q.isLoading) return <Spinner />;
  if (q.isError) return <LoadFailed onRetry={q.refetch} />;
  return (
    <div className="space-y-10" data-testid="account-security">
      {googleParam === "linked" && <Notice tone="success">Your Google account is now linked. You can sign in with either method.</Notice>}
      {googleParam === "in_use" && <Notice tone="error">That Google account is already used by a different AAYNA account.</Notice>}
      <section>
        <SectionTitle>{sec.has_password ? "Change password" : "Set a password"}</SectionTitle>
        {!sec.has_password && !sec.recent_login ? (
          <div className="max-w-lg space-y-3">
            <p className="text-sm text-aayna-taupe">You sign in with Google. To add a password as well, sign in with Google again first (for your security), then set it within 15 minutes.</p>
            <a href={googleStartUrl("/account/security")} className="inline-flex min-h-[48px] items-center px-6 border border-aayna-burgundy text-aayna-burgundy font-semibold">Re-confirm with Google</a>
          </div>
        ) : (
          <form onSubmit={submitPw} noValidate className="space-y-4 max-w-lg">
            {pwStatus && <Notice tone={pwStatus.tone} testid="password-status">{pwStatus.text}</Notice>}
            <input type="text" name="username" autoComplete="username" value={account.email} readOnly className="sr-only" tabIndex={-1} aria-hidden="true" />
            {sec.has_password && <PasswordField label="Current password" autoComplete="current-password" data-testid="pw-current" value={pw.current_password} error={pwErrors.current_password}
                                                onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />}
            <PasswordField label="New password" autoComplete="new-password" data-testid="pw-new" hint="At least 12 characters." value={pw.new_password} error={pwErrors.new_password}
                           onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            <PasswordField label="Confirm new password" autoComplete="new-password" data-testid="pw-confirm" value={pw.confirm_password} error={pwErrors.confirm_password}
                           onChange={(e) => setPw({ ...pw, confirm_password: e.target.value })} />
            <SubmitButton loading={pwLoading} className="sm:w-auto sm:px-8" data-testid="pw-submit">{sec.has_password ? "Change password" : "Set password"}</SubmitButton>
          </form>
        )}
      </section>

      <section>
        <SectionTitle>Sign-in methods</SectionTitle>
        <ul className="divide-y divide-aayna-beige border-y border-aayna-beige text-sm">
          <li className="flex items-center justify-between py-3 gap-3"><span>Email and password</span><span className="text-aayna-taupe">{sec.has_password ? "On" : "Not set"}</span></li>
          <li className="flex items-center justify-between py-3 gap-3 flex-wrap">
            <span>Google</span>
            {sec.google_linked ? (
              sec.has_password ? <button type="button" onClick={() => window.confirm("Remove Google sign-in from this account?") && act(unlinkGoogle, "Google removed")} className="min-h-[44px] text-aayna-taupe hover:text-red-700">Remove</button>
                : <span className="text-aayna-taupe">Connected</span>
            ) : sec.google_available ? <a href={googleStartUrl("/account/security", "link")} className="min-h-[44px] inline-flex items-center text-aayna-burgundy font-medium">Connect Google</a>
              : <span className="text-aayna-taupe">Not available yet</span>}
          </li>
        </ul>
      </section>

      <section>
        <SectionTitle action={sec.sessions.length > 1 && <button type="button" data-testid="revoke-others" onClick={() => act(revokeOtherSessions, "Signed out of other devices")} className="min-h-[44px] text-sm text-aayna-burgundy">Sign out other devices</button>}>
          Where you're signed in
        </SectionTitle>
        <ul className="divide-y divide-aayna-beige border-y border-aayna-beige" data-testid="session-list">
          {sec.sessions.map((s) => (
            <li key={s.id} className="py-3 flex items-center justify-between gap-3 text-sm">
              <div className="min-w-0">
                <p className="text-aayna-charcoal truncate">{s.user_agent || "Unknown device"}</p>
                <p className="text-xs text-aayna-taupe">Signed in {formatDhakaDateTime(s.created_at)} · {s.method === "google" ? "Google" : "Password"}{s.current ? " · This device" : ""}</p>
              </div>
              {!s.current && <button type="button" onClick={() => act(() => revokeSession(s.id), "Device signed out")} className="min-h-[44px] text-aayna-taupe hover:text-red-700 flex-shrink-0">Sign out</button>}
            </li>
          ))}
        </ul>
        <button type="button" data-testid="logout-all" onClick={async () => { await logoutAll(); setAccount(null); navigate("/login"); }}
                className="mt-4 min-h-[44px] text-sm text-aayna-burgundy hover:underline underline-offset-2">Sign out everywhere</button>
      </section>

      <section>
        <SectionTitle>Recent activity</SectionTitle>
        <ul className="text-sm space-y-2">
          {sec.events.slice(0, 8).map((ev, i) => (
            <li key={i} className="flex justify-between gap-3"><span className="text-aayna-charcoal">{ev.type.replace(/_/g, " ")}</span><span className="text-xs text-aayna-taupe whitespace-nowrap">{formatDhakaDateTime(ev.created_at)}</span></li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle>Delete account</SectionTitle>
        {account.deletion_requested_at ? (
          <Notice>We received your deletion request on {formatDhakaDateTime(account.deletion_requested_at)}. Our team will complete it and email you.</Notice>
        ) : (
          <>
            <p className="text-sm text-aayna-taupe max-w-lg">Ask us to delete your account. We'll remove your profile and saved addresses and email you once it's done. Order records we're required to keep are retained.</p>
            <button type="button" data-testid="delete-request" onClick={async () => {
              if (window.prompt('Type DELETE to request deletion of your account') !== "DELETE") return;
              try { const r = await requestDeletion(); toast.success(r.message); refresh(); } catch (err) { toast.error(apiError(err).message); }
            }} className="mt-4 min-h-[44px] px-5 border border-red-300 text-red-800 text-sm font-medium hover:bg-red-50">Request account deletion</button>
          </>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
export function AccountRewards() {
  const q = useQuery({ queryKey: ["account-rewards"], queryFn: getRewards });
  const copy = async (code) => { try { await navigator.clipboard.writeText(code); toast.success("Code copied"); } catch { /* visible as text */ } };
  return (
    <div data-testid="account-rewards">
      <SectionTitle>Rewards</SectionTitle>
      {q.isLoading ? <Spinner /> : q.isError ? <LoadFailed onRetry={q.refetch} /> : q.data.coupons.length === 0 ? (
        <Empty testid="rewards-empty" icon={Gift} title="No rewards yet"
               text={q.data.welcome_enabled ? "Your welcome offer appears here after you confirm your email." : "When AAYNA has an offer for you, it will appear here."} />
      ) : (
        <div className="space-y-4">
          {q.data.coupons.map((c) => (
            <div key={c.code} data-testid="reward-card" className={`border p-5 ${c.state === "active" ? "border-aayna-burgundy/40" : "border-aayna-beige opacity-70"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-display text-xl font-semibold text-aayna-burgundy">{c.type === "percent" ? `${c.value}% off` : `${formatBDT(c.value)} off`}</p>
                  <p className="text-sm text-aayna-taupe">{c.name}</p>
                </div>
                <span className="text-[11px] uppercase tracking-wide border px-2 py-1 text-aayna-taupe">{c.state === "active" ? "Ready to use" : c.state}</span>
              </div>
              <button type="button" onClick={() => copy(c.code)} className="mt-4 font-mono text-base tracking-wider border border-dashed border-aayna-burgundy px-4 min-h-[44px] text-aayna-charcoal">{c.code}</button>
              <ul className="text-xs text-aayna-taupe mt-3 space-y-1">
                {c.min_subtotal > 0 && <li>Minimum order: {formatBDT(c.min_subtotal)} of products</li>}
                {c.max_discount_bdt != null && <li>Maximum discount: {formatBDT(c.max_discount_bdt)}</li>}
                {c.first_order_only && <li>First order only · one use · for your account only</li>}
                {c.ends_at && <li>Expires {formatDhakaDateTime(c.ends_at)}</li>}
                <li>Applies to products, not delivery. Can't be combined with other codes.</li>
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export { claimOrder };
