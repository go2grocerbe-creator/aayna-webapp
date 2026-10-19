import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Plus, X, Pause, Play, Archive } from "lucide-react";
import AdminLoadError from "@/admin/AdminLoadError";
import { useAdminAuth } from "@/admin/AdminAuthContext";
import {
  getPromotions, getPromotion, createPromotion, updatePromotion, activatePromotion, pausePromotion, archivePromotion,
  previewPromotion, getWelcomeCampaign, updateWelcomeCampaign, restoreRedemption, getAdminCategories, getAdminProducts,
} from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";

// Coupon codes and the welcome campaign. Every amount shown here is computed
// by the server (preview endpoint, real redemptions) - nothing is estimated in
// the browser. Creating/editing is for admins; making a code usable
// (activation) and changing the welcome campaign are super-admin only.
const STATE_STYLE = {
  active: "bg-green-100 text-green-700", draft: "bg-gray-100 text-gray-600", paused: "bg-amber-100 text-amber-800",
  scheduled: "bg-blue-100 text-blue-700", expired: "bg-gray-100 text-gray-500", exhausted: "bg-gray-100 text-gray-500",
  archived: "bg-gray-100 text-gray-400",
};
const field = "w-full h-11 border border-gray-300 rounded-md px-3 text-sm outline-none focus:border-aayna-burgundy";
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const toLocalInput = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const fromLocalInput = (v) => (v ? new Date(v).toISOString() : null);
const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join("; ") : "Request failed";
};

function StateBadge({ state }) {
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded ${STATE_STYLE[state] || STATE_STYLE.draft}`}>{state}</span>;
}

const EMPTY = { code: "", name: "", description: "", type: "percent", value: "", max_discount_bdt: "", max_percent_of_subtotal: "",
  min_subtotal: "", starts_at: "", ends_at: "", usage_limit_total: "", usage_limit_per_customer: "1", first_order_only: false,
  eligible_category_slugs: [], eligible_product_ids: [], customer_emails: "" };

function PromotionForm({ initial, onSaved, onCancel }) {
  const [f, setF] = useState(() => initial ? {
    ...EMPTY, ...initial,
    value: String(initial.value ?? ""), max_discount_bdt: initial.max_discount_bdt ?? "", max_percent_of_subtotal: initial.max_percent_of_subtotal ?? "",
    min_subtotal: initial.min_subtotal || "", usage_limit_total: initial.usage_limit_total ?? "", usage_limit_per_customer: initial.usage_limit_per_customer ?? "",
    starts_at: toLocalInput(initial.starts_at), ends_at: toLocalInput(initial.ends_at), customer_emails: (initial.customer_emails || []).join(", "),
  } : EMPTY);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [sample, setSample] = useState("2000");
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: getAdminCategories });
  const { data: prods = [] } = useQuery({ queryKey: ["admin-products-all"], queryFn: () => getAdminProducts({}) });
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const num = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
  const toggle = (k, v) => setF((x) => ({ ...x, [k]: x[k].includes(v) ? x[k].filter((y) => y !== v) : [...x[k], v] }));

  useEffect(() => {
    if (!f.value || !sample) { setPreview(null); return undefined; }
    const t = setTimeout(() => {
      previewPromotion({ type: f.type, value: Number(f.value), max_discount_bdt: num(f.max_discount_bdt), max_percent_of_subtotal: num(f.max_percent_of_subtotal),
                         min_subtotal: num(f.min_subtotal) || 0, subtotal: Number(sample), delivery_charge: 0 })
        .then(setPreview).catch(() => setPreview(null));
    }, 300);
    return () => clearTimeout(t);
  }, [f.type, f.value, f.max_discount_bdt, f.max_percent_of_subtotal, f.min_subtotal, sample]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    const body = {
      code: f.code, name: f.name, description: f.description, type: f.type, value: Number(f.value),
      max_discount_bdt: num(f.max_discount_bdt), max_percent_of_subtotal: num(f.max_percent_of_subtotal), min_subtotal: num(f.min_subtotal) || 0,
      starts_at: fromLocalInput(f.starts_at), ends_at: fromLocalInput(f.ends_at),
      usage_limit_total: num(f.usage_limit_total), usage_limit_per_customer: num(f.usage_limit_per_customer),
      first_order_only: f.first_order_only, eligible_category_slugs: f.eligible_category_slugs, eligible_product_ids: f.eligible_product_ids,
      customer_emails: f.customer_emails.split(/[\s,;]+/).filter(Boolean),
    };
    try {
      const saved = initial?.id ? await updatePromotion(initial.id, body) : await createPromotion(body);
      toast.success(initial?.id ? "Promotion updated" : "Promotion saved as draft");
      onSaved(saved);
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="bg-white border border-gray-200 rounded-lg p-5 space-y-5" data-testid="promotion-form">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-aayna-charcoal">{initial?.id ? `Edit ${initial.code}` : "New coupon code"}</h2>
        <button type="button" onClick={onCancel} aria-label="Close" className="h-11 w-11 flex items-center justify-center text-gray-400"><X className="h-4 w-4" /></button>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <label className="text-sm">Code *<input data-testid="promo-code" required className={`${field} uppercase mt-1`} value={f.code} onChange={(e) => set("code", e.target.value.toUpperCase())} placeholder="EID10" maxLength={32} /></label>
        <label className="text-sm">Name *<input data-testid="promo-name" required className={`${field} mt-1`} value={f.name} onChange={(e) => set("name", e.target.value)} maxLength={80} /></label>
        <label className="text-sm">Type
          <select data-testid="promo-type" className={`${field} bg-white mt-1`} value={f.type} onChange={(e) => set("type", e.target.value)}>
            <option value="percent">Percentage off products</option><option value="fixed">Fixed BDT off products</option>
          </select>
        </label>
        <label className="text-sm">{f.type === "percent" ? "Percent off *" : "Amount off (BDT) *"}<input data-testid="promo-value" required type="number" min="1" max={f.type === "percent" ? 100 : undefined} step="any" className={`${field} mt-1`} value={f.value} onChange={(e) => set("value", e.target.value)} /></label>
        <label className="text-sm">Maximum discount (BDT)<input data-testid="promo-max" type="number" min="0" className={`${field} mt-1`} value={f.max_discount_bdt} onChange={(e) => set("max_discount_bdt", e.target.value)} placeholder="No cap" /></label>
        <label className="text-sm">Maximum % of eligible subtotal<input type="number" min="1" max="100" className={`${field} mt-1`} value={f.max_percent_of_subtotal} onChange={(e) => set("max_percent_of_subtotal", e.target.value)} placeholder="No cap" /></label>
        <label className="text-sm">Minimum eligible subtotal (BDT)<input data-testid="promo-min" type="number" min="0" className={`${field} mt-1`} value={f.min_subtotal} onChange={(e) => set("min_subtotal", e.target.value)} placeholder="None" /></label>
        <div />
        <label className="text-sm">Starts (Bangladesh time)<input type="datetime-local" className={`${field} mt-1`} value={f.starts_at} onChange={(e) => set("starts_at", e.target.value)} /></label>
        <label className="text-sm">Ends<input type="datetime-local" className={`${field} mt-1`} value={f.ends_at} onChange={(e) => set("ends_at", e.target.value)} /></label>
        <label className="text-sm">Total uses allowed<input data-testid="promo-total" type="number" min="1" className={`${field} mt-1`} value={f.usage_limit_total} onChange={(e) => set("usage_limit_total", e.target.value)} placeholder="Unlimited" /></label>
        <label className="text-sm">Uses per customer<input type="number" min="1" className={`${field} mt-1`} value={f.usage_limit_per_customer} onChange={(e) => set("usage_limit_per_customer", e.target.value)} placeholder="Unlimited" /></label>
      </div>
      <label className="flex items-center gap-2 text-sm min-h-[44px]"><input type="checkbox" checked={f.first_order_only} onChange={(e) => set("first_order_only", e.target.checked)} /> First order only (no previous orders by this account or phone)</label>
      <fieldset>
        <legend className="text-sm font-medium mb-2">Only these categories (optional)</legend>
        <div className="flex flex-wrap gap-2">{cats.map((c) => (
          <label key={c.slug} className={`text-sm border rounded-md px-3 min-h-[40px] flex items-center gap-2 cursor-pointer ${f.eligible_category_slugs.includes(c.slug) ? "border-aayna-burgundy bg-aayna-mist" : "border-gray-300"}`}>
            <input type="checkbox" className="sr-only" checked={f.eligible_category_slugs.includes(c.slug)} onChange={() => toggle("eligible_category_slugs", c.slug)} />{c.name}
          </label>))}
        </div>
      </fieldset>
      <details>
        <summary className="text-sm font-medium cursor-pointer min-h-[44px] flex items-center">Only these products (optional, {f.eligible_product_ids.length} selected)</summary>
        <div className="grid sm:grid-cols-2 gap-1 max-h-60 overflow-y-auto mt-2">{prods.map((p) => (
          <label key={p.id} className="text-sm flex items-center gap-2 min-h-[36px]"><input type="checkbox" checked={f.eligible_product_ids.includes(p.id)} onChange={() => toggle("eligible_product_ids", p.id)} />{p.product_name} <span className="text-gray-400">({p.status})</span></label>))}
        </div>
      </details>
      <label className="text-sm block">Only for these customers (account emails, optional)
        <textarea rows={2} className={`${field} h-auto py-2 mt-1`} value={f.customer_emails} onChange={(e) => set("customer_emails", e.target.value)} placeholder="name@example.com, ..." />
      </label>
      <label className="text-sm block">Internal note<input className={`${field} mt-1`} value={f.description} onChange={(e) => set("description", e.target.value)} maxLength={300} /></label>

      <div className="border border-dashed border-gray-300 rounded-md p-4 bg-gray-50" data-testid="promo-preview">
        <p className="text-sm font-medium text-aayna-charcoal mb-2">Effect preview (calculated by the server)</p>
        <label className="text-sm flex items-center gap-2 flex-wrap">For an eligible product subtotal of ৳
          <input type="number" min="0" value={sample} onChange={(e) => setSample(e.target.value)} className="h-10 w-28 border border-gray-300 rounded-md px-2" /></label>
        {preview && (
          <p className="text-sm mt-2" data-testid="promo-preview-result">
            {preview.meets_minimum
              ? <>Discount <b>{formatBDT(preview.discount)}</b> ({preview.effective_percent}%) → products {formatBDT(preview.merchandise_after)} + delivery</>
              : <>Below the minimum subtotal - no discount.</>}
          </p>
        )}
      </div>
      <div className="flex gap-3">
        <button type="submit" disabled={saving} data-testid="promo-save" className="h-11 px-5 bg-aayna-burgundy text-white rounded-md font-semibold flex items-center gap-2 disabled:opacity-60">{saving && <Loader2 className="h-4 w-4 animate-spin" />}{initial?.id ? "Save changes" : "Save as draft"}</button>
        <button type="button" onClick={onCancel} className="h-11 px-4 text-gray-500">Cancel</button>
      </div>
      <p className="text-xs text-gray-500">New codes are saved as drafts. A super admin must activate a code before customers can use it.</p>
    </form>
  );
}

function PromotionDetail({ id, onClose, onEdit }) {
  const qc = useQueryClient();
  const { can } = useAdminAuth();
  const { data: p, isLoading, isError, error, refetch } = useQuery({ queryKey: ["admin-promo", id], queryFn: () => getPromotion(id) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["admin-promo", id] }); qc.invalidateQueries({ queryKey: ["admin-promos"] }); };
  const act = async (fn, msg) => { try { await fn(); toast.success(msg); refresh(); } catch (e) { toast.error(errMsg(e)); } };
  if (isLoading) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-burgundy" /></div>;
  if (isError) return <AdminLoadError what="this promotion" error={error} onRetry={refetch} />;
  const rules = [
    `${p.type === "percent" ? `${p.value}%` : formatBDT(p.value)} off eligible products (never delivery)`,
    p.max_discount_bdt != null && `Maximum discount ${formatBDT(p.max_discount_bdt)}`,
    p.max_percent_of_subtotal != null && `At most ${p.max_percent_of_subtotal}% of the eligible subtotal`,
    p.min_subtotal > 0 && `Minimum eligible subtotal ${formatBDT(p.min_subtotal)}`,
    p.first_order_only && "First order only",
    `Total uses: ${p.usage_limit_total ?? "unlimited"} · per customer: ${p.usage_limit_per_customer ?? "unlimited"}`,
    p.eligible_category_slugs?.length && `Categories: ${p.eligible_category_slugs.join(", ")}`,
    p.eligible_product_ids?.length && `${p.eligible_product_ids.length} selected product(s)`,
    p.customer_count > 0 && `Only for ${p.customer_count} customer account(s)`,
    `Valid ${p.starts_at ? `from ${fmt(p.starts_at)}` : "immediately"} ${p.ends_at ? `until ${fmt(p.ends_at)}` : "with no end date"}`,
  ].filter(Boolean);
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-5" data-testid="promotion-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-xl font-bold text-aayna-charcoal font-mono">{p.code}</h2><p className="text-sm text-gray-500">{p.name}</p></div>
        <div className="flex items-center gap-2"><StateBadge state={p.state} /><button type="button" onClick={onClose} aria-label="Close" className="h-11 w-11 flex items-center justify-center text-gray-400"><X className="h-4 w-4" /></button></div>
      </div>
      <ul className="text-sm list-disc pl-5 space-y-1">{rules.map((r) => <li key={r}>{r}</li>)}</ul>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="border rounded-md p-3"><p className="text-gray-500 text-xs">Redemptions</p><p className="text-lg font-semibold">{p.redemptions}</p></div>
        <div className="border rounded-md p-3"><p className="text-gray-500 text-xs">Discount given</p><p className="text-lg font-semibold">{formatBDT(p.discount_given)}</p></div>
      </div>
      <div className="flex flex-wrap gap-2">
        {p.kind !== "welcome_issued" && ["draft", "paused"].includes(p.status) && can("promotions.manage") && <button type="button" onClick={() => onEdit(p)} className="h-11 px-4 border border-gray-300 rounded-md text-sm">Edit</button>}
        {p.kind !== "welcome_issued" && ["draft", "paused"].includes(p.status) && can("promotions.activate") && (
          <button type="button" data-testid="promo-activate" onClick={() => {
            const note = window.prompt(`Activate ${p.code}? Customers will be able to use it at checkout.\n\nOptional approval note:`);
            if (note !== null) act(() => activatePromotion(p.id, note), "Promotion activated");
          }} className="h-11 px-4 bg-green-700 text-white rounded-md text-sm flex items-center gap-1.5"><Play className="h-4 w-4" />Activate</button>
        )}
        {p.status === "active" && can("promotions.manage") && <button type="button" onClick={() => act(() => pausePromotion(p.id), "Paused")} className="h-11 px-4 border border-amber-400 text-amber-800 rounded-md text-sm flex items-center gap-1.5"><Pause className="h-4 w-4" />Pause</button>}
        {["draft", "paused"].includes(p.status) && p.kind !== "welcome_issued" && can("promotions.manage") && <button type="button" onClick={() => window.confirm("Archive this promotion?") && act(() => archivePromotion(p.id), "Archived")} className="h-11 px-4 text-gray-500 text-sm flex items-center gap-1.5"><Archive className="h-4 w-4" />Archive</button>}
        {!can("promotions.activate") && ["draft", "paused"].includes(p.status) && <p className="text-xs text-gray-500 self-center">A super admin activates codes.</p>}
      </div>
      <div>
        <h3 className="font-semibold text-sm mb-2">Orders using this code</h3>
        {p.redemption_list.length === 0 ? <p className="text-sm text-gray-400">None yet.</p> : (
          <ul className="divide-y divide-gray-100 text-sm">{p.redemption_list.map((r) => (
            <li key={r.id} className="py-2 flex flex-wrap justify-between gap-2">
              <a href={`/admin/orders/${r.order_number}`} className="text-aayna-burgundy font-medium">{r.order_number}</a>
              <span>{formatBDT(r.discount_amount)}</span><span className="text-gray-500">{r.status}</span>
              {r.status === "redeemed" && can("promotions.manage") && (
                <button type="button" onClick={() => {
                  const note = window.prompt("Give this customer the use back? Only possible for a cancelled or returned order.\n\nReason:");
                  if (note !== null) act(() => restoreRedemption(r.id, note), "Use restored");
                }} className="text-xs text-gray-500 underline">Restore use</button>
              )}
            </li>))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="font-semibold text-sm mb-2">Audit trail</h3>
        <ul className="text-xs text-gray-600 space-y-1">{p.audit.map((a) => <li key={a.id}>{fmt(a.created_at)} · {a.action} · {a.actor}</li>)}</ul>
      </div>
    </div>
  );
}

function WelcomeCampaign() {
  const qc = useQueryClient();
  const { can } = useAdminAuth();
  const { data: c, isLoading, isError, error, refetch } = useQuery({ queryKey: ["admin-welcome"], queryFn: getWelcomeCampaign });
  const [form, setForm] = useState(null);
  useEffect(() => { if (c) setForm({ value: c.value, validity_days: c.validity_days, min_subtotal: c.min_subtotal ?? "", max_discount_bdt: c.max_discount_bdt ?? "", first_order_only: c.first_order_only }); }, [c]);
  const sample = useMemo(() => Number(form?.min_subtotal || c?.proposed?.min_subtotal || 1000) * 2, [form, c]);
  const { data: preview } = useQuery({
    queryKey: ["welcome-preview", form?.value, form?.min_subtotal, form?.max_discount_bdt, sample],
    queryFn: () => previewPromotion({ type: "percent", value: Number(form.value), min_subtotal: Number(form.min_subtotal || 0),
                                      max_discount_bdt: form.max_discount_bdt === "" ? null : Number(form.max_discount_bdt), subtotal: sample }),
    enabled: !!form && !!form.value,
  });
  if (isLoading || !form) return <div className="p-6 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-aayna-burgundy" /></div>;
  if (isError) return <AdminLoadError what="the welcome campaign" error={error} onRetry={refetch} />;
  const save = async (enabled) => {
    const body = { value: Number(form.value), validity_days: Number(form.validity_days), first_order_only: form.first_order_only,
                   min_subtotal: form.min_subtotal === "" ? null : Number(form.min_subtotal),
                   max_discount_bdt: form.max_discount_bdt === "" ? null : Number(form.max_discount_bdt) };
    if (enabled !== undefined) {
      body.enabled = enabled;
      if (enabled && !window.confirm(`Enable the welcome offer?\n\nEvery newly verified customer will receive a real ${form.value}% code (min ${formatBDT(form.min_subtotal || 0)}, max ${form.max_discount_bdt === "" ? "no cap" : formatBDT(form.max_discount_bdt)}, ${form.validity_days} days).`)) return;
      body.confirm = !!enabled;
    }
    try { await updateWelcomeCampaign(body); toast.success("Welcome campaign saved"); qc.invalidateQueries({ queryKey: ["admin-welcome"] }); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const editable = can("promotions.activate");
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4" data-testid="welcome-campaign">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold text-aayna-charcoal">Welcome offer for new verified customers</h2>
          <p className="text-sm text-gray-500">One personal, single-use code per verified account, issued only after email confirmation.</p>
        </div>
        <span data-testid="welcome-status" className={`text-xs font-semibold px-2 py-0.5 rounded ${c.enabled ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>{c.enabled ? "Enabled" : "Disabled"}</span>
      </div>
      {!c.enabled && (
        <p className="text-sm bg-amber-50 border border-amber-200 text-amber-900 rounded-md p-3">
          Not approved yet. Proposed limits awaiting your decision: minimum order {formatBDT(c.proposed.min_subtotal)}, maximum discount {formatBDT(c.proposed.max_discount_bdt)}.
          Nothing is issued while disabled, and the storefront does not mention a discount.
        </p>
      )}
      <fieldset disabled={!editable} className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <label className="text-sm">Percent off<input type="number" min="1" max="100" className={`${field} mt-1`} value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} /></label>
        <label className="text-sm">Valid for (days)<input type="number" min="1" max="365" className={`${field} mt-1`} value={form.validity_days} onChange={(e) => setForm({ ...form, validity_days: e.target.value })} /></label>
        <label className="text-sm">Minimum subtotal (BDT)<input data-testid="welcome-min" type="number" min="0" className={`${field} mt-1`} value={form.min_subtotal} placeholder="Not set" onChange={(e) => setForm({ ...form, min_subtotal: e.target.value })} /></label>
        <label className="text-sm">Maximum discount (BDT)<input data-testid="welcome-max" type="number" min="0" className={`${field} mt-1`} value={form.max_discount_bdt} placeholder="Not set" onChange={(e) => setForm({ ...form, max_discount_bdt: e.target.value })} /></label>
      </fieldset>
      {preview && <p className="text-sm text-gray-600" data-testid="welcome-preview">Example: a {formatBDT(sample)} product order gets {formatBDT(preview.discount)} off ({preview.effective_percent}%).</p>}
      <p className="text-sm text-gray-500">Issued so far: {c.issued} · redeemed: {c.redeemed}{c.approved_by ? ` · approved by ${c.approved_by} on ${fmt(c.approved_at)}` : ""}</p>
      {editable ? (
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => save(undefined)} className="h-11 px-4 border border-gray-300 rounded-md text-sm">Save settings</button>
          {c.enabled
            ? <button type="button" onClick={() => save(false)} className="h-11 px-4 border border-amber-400 text-amber-800 rounded-md text-sm">Disable</button>
            : <button type="button" data-testid="welcome-enable" onClick={() => save(true)} className="h-11 px-4 bg-green-700 text-white rounded-md text-sm">Enable welcome offer</button>}
        </div>
      ) : <p className="text-xs text-gray-500">Only the super admin can change or enable this campaign.</p>}
    </div>
  );
}

export default function Promotions() {
  const { can } = useAdminAuth();
  const [tab, setTab] = useState("codes");
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(null);
  const qc = useQueryClient();
  const { data = [], isLoading, isError, error, refetch } = useQuery({ queryKey: ["admin-promos", tab], queryFn: () => getPromotions(tab === "issued" ? "issued" : "codes"), enabled: tab !== "welcome" });
  return (
    <div data-testid="admin-promotions">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Promotions</h1>
        {tab === "codes" && can("promotions.manage") && !editing && <button type="button" data-testid="promo-new" onClick={() => { setEditing({}); setOpen(null); }} className="h-11 px-4 bg-aayna-burgundy text-white rounded-md text-sm font-semibold flex items-center gap-1.5"><Plus className="h-4 w-4" />New code</button>}
      </div>
      <div className="flex gap-1 border-b border-gray-200 mb-6 overflow-x-auto">
        {[["codes", "Coupon codes"], ["welcome", "Welcome offer"], ["issued", "Issued welcome codes"]].map(([k, l]) => (
          <button key={k} type="button" onClick={() => { setTab(k); setEditing(null); setOpen(null); }}
                  className={`min-h-[44px] px-4 text-sm font-medium border-b-2 whitespace-nowrap ${tab === k ? "border-aayna-burgundy text-aayna-burgundy" : "border-transparent text-gray-500"}`}>{l}</button>
        ))}
      </div>
      {tab === "welcome" ? <WelcomeCampaign /> : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className={`min-w-0 ${editing || open ? "lg:col-span-2" : "lg:col-span-5"}`}>
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-500 text-left"><tr><th className="px-4 py-3 font-medium">Code</th><th className="px-4 py-3 font-medium">Offer</th><th className="px-4 py-3 font-medium">State</th><th className="px-4 py-3 font-medium">Used</th></tr></thead>
                  <tbody className="divide-y divide-gray-100">
                    {isLoading ? <tr><td colSpan={4} className="py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-burgundy mx-auto" /></td></tr>
                      : isError ? <tr><td colSpan={4}><AdminLoadError compact what="promotions" error={error} onRetry={refetch} /></td></tr>
                      : data.length === 0 ? <tr><td colSpan={4} className="py-10 text-center text-gray-400" data-testid="promos-empty">{tab === "issued" ? "No welcome codes issued." : "No coupon codes yet."}</td></tr>
                      : data.map((p) => (
                        <tr key={p.id} onClick={() => { setOpen(p.id); setEditing(null); }} className={`cursor-pointer hover:bg-gray-50 ${open === p.id ? "bg-aayna-mist/40" : ""}`} data-testid={`promo-row-${p.code}`}>
                          <td className="px-4 py-3 font-mono font-medium">{p.code}</td>
                          <td className="px-4 py-3 text-gray-600">{p.type === "percent" ? `${p.value}%` : formatBDT(p.value)}{p.max_discount_bdt != null ? ` (max ${formatBDT(p.max_discount_bdt)})` : ""}</td>
                          <td className="px-4 py-3"><StateBadge state={p.state} /></td>
                          <td className="px-4 py-3">{p.redemptions}{p.usage_limit_total ? ` / ${p.usage_limit_total}` : ""}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          {(editing || open) && (
            <div className="lg:col-span-3 min-w-0">
              {editing ? <PromotionForm initial={editing.id ? editing : null} onCancel={() => setEditing(null)}
                                        onSaved={(p) => { setEditing(null); setOpen(p.id); qc.invalidateQueries({ queryKey: ["admin-promos"] }); }} />
                : <PromotionDetail id={open} onClose={() => setOpen(null)} onEdit={(p) => setEditing(p)} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
