import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Save } from "lucide-react";
import { getAdminSettings, updateAdminSettings } from "@/admin/adminApi";
import { Switch } from "@/components/ui/switch";
import BrandLogo from "@/components/BrandLogo";
import AdminLoadError from "@/admin/AdminLoadError";

const TEXT_FIELDS = [
  ["brand_name", "Brand Name"],
  ["tagline", "Tagline"],
  ["announcement_bar_text", "Announcement Bar Text"],
  ["whatsapp_number", "WhatsApp Number"],
  ["support_email", "Support Email"],
  ["facebook_url", "Facebook Link"],
  ["instagram_url", "Instagram Link"],
  ["tiktok_url", "TikTok Link"],
];

// Delivery policy (founder decision 2026-10-19): ৳100 nationwide, free from a ৳1,500
// product subtotal before discounts. Defaults match backend/delivery.py.
const NUMBER_FIELDS = [
  ["delivery_charge_bdt", "Delivery charge, nationwide (৳)", 100],
  ["free_delivery_min_subtotal_bdt", "Free delivery from product subtotal (৳)", 1500],
];

// Optional, PRIVATE planning estimates for Steadfast's charges (never shown to customers).
// Leave empty to show "pending provider confirmation" instead of a guess.
const ESTIMATE_FIELDS = [
  ["steadfast_estimated_delivery_fee_bdt", "Estimated Steadfast delivery fee per parcel (৳)"],
  ["steadfast_estimated_cod_fee_pct", "Estimated Steadfast COD charge (% of COD)"],
];

const PLACEHOLDER_FIELDS = [
  ["announcement_bar_text", "Announcement bar text"],
  ["support_email", "Support email"],
];

const looksPlaceholder = (v) => {
  const s = String(v || "").trim().toLowerCase();
  if (!s) return true;
  if (s.startsWith("test")) return true;
  return ["xxxx", "example.com", "changeme", "placeholder"].some((m) => s.includes(m));
};

export default function Settings() {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["admin-settings"], queryFn: getAdminSettings });
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (data) setForm({ ...Object.fromEntries(NUMBER_FIELDS.map(([k, , d]) => [k, d])), ...data }); }, [data]);

  if (isError) return <AdminLoadError what="settings" error={error} onRetry={refetch} />;
  if (isLoading) return <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-aayna-burgundy" /></div>;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        ...TEXT_FIELDS.reduce((a, [k]) => ({ ...a, [k]: form[k] ?? "" }), {}),
        ...Object.fromEntries(NUMBER_FIELDS.map(([k, , d]) => [k, form[k] === "" || form[k] == null ? d : Number(form[k])])),
        ...Object.fromEntries(ESTIMATE_FIELDS.map(([k]) => [k, form[k] === "" || form[k] == null ? "" : Number(form[k])])),
        logo_url: form.logo_url || "",
        cod_available: Boolean(form.cod_available),
        maintenance_mode: Boolean(form.maintenance_mode),
      };
      await updateAdminSettings(payload);
      toast.success("Settings saved");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-burgundy text-sm";

  const placeholderWarnings = PLACEHOLDER_FIELDS.filter(([k]) => looksPlaceholder(form[k])).map(([, l]) => l);

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-2">Website Settings</h1>
      <p data-testid="settings-scope-note" className="text-sm text-gray-500 mb-6">
        These values are <strong>public</strong>: they appear on the storefront (announcement, social links, delivery charges).
        The approved phone (+880 1348-243169) and email aliases are built into the website. Only Cash on Delivery is offered,
        so bKash/Nagad fields are not shown.
        Private configuration such as the database connection, login keys and passwords is never stored or shown here;
        it lives only in the hosting provider&apos;s environment settings.
      </p>

      {placeholderWarnings.length > 0 && (
        <div data-testid="settings-placeholder-warning" className="mb-6 border border-amber-300 bg-amber-50 text-amber-900 rounded-lg p-4 text-sm">
          <p className="font-semibold mb-1">⚠️ Replace placeholder values before launch</p>
          <p>These still look like placeholders: {placeholderWarnings.join(", ")}. Update them with your real details so customers see correct information.</p>
        </div>
      )}

      <div className="space-y-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Brand & Logo</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {TEXT_FIELDS.slice(0, 3).map(([k, label]) => (
              <div key={k} className={k === "announcement_bar_text" ? "sm:col-span-2" : ""}>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
                <input data-testid={`set-${k}`} className={field} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} />
              </div>
            ))}
            <div className="sm:col-span-2" data-testid="settings-brand-assets">
              <p className="block text-sm font-medium text-gray-700 mb-1.5">Logo and favicon</p>
              <div className="flex flex-wrap items-center gap-4 border border-gray-200 rounded-md p-4 bg-aayna-cream">
                <BrandLogo className="h-14 w-auto" alt="AAYNA logo (approved)" />
                <img src="/favicon-32x32.png" width="32" height="32" alt="AAYNA favicon" />
                <p className="text-xs text-gray-600 flex-1 min-w-[12rem]">
                  Brand assets are managed in the website build: the approved original logo and favicons ship with the site.
                  They cannot be replaced from this page, because the website has no permanent file storage for uploads yet.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Contact & Social</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {TEXT_FIELDS.slice(3).map(([k, label]) => (
              <div key={k}>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
                <input data-testid={`set-${k}`} className={field} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} />
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Delivery & Store</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {NUMBER_FIELDS.map(([k, label, d]) => (
              <div key={k}>
                <label htmlFor={`set-${k}`} className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
                <input id={`set-${k}`} data-testid={`set-${k}`} type="number" min="0" step="1" inputMode="numeric" className={field} value={form[k] ?? d} onChange={(e) => set(k, e.target.value)} />
              </div>
            ))}
            {ESTIMATE_FIELDS.map(([k, label]) => (
              <div key={k}>
                <label htmlFor={`set-${k}`} className="block text-sm font-medium text-gray-700 mb-1.5">{label} <span className="text-xs text-gray-400 font-normal">optional, private</span></label>
                <input id={`set-${k}`} data-testid={`set-${k}`} type="number" min="0" step="0.01" inputMode="decimal" className={field} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} placeholder="Leave empty if not known" />
              </div>
            ))}
            <p className="sm:col-span-2 text-xs text-gray-500" data-testid="set-delivery-help">
              Customers pay the delivery charge when their products total less than the free-delivery amount (before any discount code); at or above it, delivery is free. Same charge for every district.
            </p>
          </div>
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between">
              <div><p className="text-sm font-medium text-gray-700">Cash on Delivery</p><p className="text-xs text-gray-400">Allow COD at checkout</p></div>
              <Switch data-testid="set-cod" checked={Boolean(form.cod_available)} onCheckedChange={(v) => set("cod_available", v)} />
            </div>
            <div className="flex items-center justify-between">
              <div><p className="text-sm font-medium text-gray-700">Maintenance Mode</p><p className="text-xs text-gray-400">When ON, the public storefront shows a maintenance page. The admin dashboard stays accessible.</p></div>
              <Switch data-testid="set-maintenance" checked={Boolean(form.maintenance_mode)} onCheckedChange={(v) => set("maintenance_mode", v)} />
            </div>
          </div>
        </div>

        <button data-testid="settings-save" onClick={save} disabled={saving} className="h-11 px-6 bg-aayna-burgundy text-white rounded-md font-semibold hover:bg-aayna-burgundy-dark disabled:opacity-60 flex items-center gap-2">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save Settings
        </button>
      </div>
    </div>
  );
}
