import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Save } from "lucide-react";
import { getAdminSettings, updateAdminSettings } from "@/admin/adminApi";
import { Switch } from "@/components/ui/switch";
import ImageUpload from "@/admin/ImageUpload";

const TEXT_FIELDS = [
  ["brand_name", "Brand Name"],
  ["tagline", "Tagline"],
  ["announcement_bar_text", "Announcement Bar Text"],
  ["whatsapp_number", "WhatsApp Number"],
  ["support_email", "Support Email"],
  ["bkash_number", "bKash Number"],
  ["nagad_number", "Nagad Number"],
  ["facebook_url", "Facebook Link"],
  ["instagram_url", "Instagram Link"],
  ["tiktok_url", "TikTok Link"],
];

const NUMBER_FIELDS = [
  ["delivery_charge_inside_dhaka", "Delivery Inside Dhaka (৳)"],
  ["delivery_charge_outside_dhaka", "Delivery Outside Dhaka (৳)"],
];

export default function Settings() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-settings"], queryFn: getAdminSettings });
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (data) setForm(data); }, [data]);

  if (isLoading) return <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-aayna-rose" /></div>;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        ...TEXT_FIELDS.reduce((a, [k]) => ({ ...a, [k]: form[k] ?? "" }), {}),
        delivery_charge_inside_dhaka: Number(form.delivery_charge_inside_dhaka) || 0,
        delivery_charge_outside_dhaka: Number(form.delivery_charge_outside_dhaka) || 0,
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

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose text-sm";

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-6">Website Settings</h1>

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
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Logo</label>
              <ImageUpload images={form.logo_url ? [{ image_url: form.logo_url, alt_text: "logo", is_main: true }] : []} onChange={(imgs) => set("logo_url", imgs[0]?.image_url || "")} />
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
            {NUMBER_FIELDS.map(([k, label]) => (
              <div key={k}>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
                <input data-testid={`set-${k}`} type="number" className={field} value={form[k] ?? 0} onChange={(e) => set(k, e.target.value)} />
              </div>
            ))}
          </div>
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between">
              <div><p className="text-sm font-medium text-gray-700">Cash on Delivery</p><p className="text-xs text-gray-400">Allow COD at checkout</p></div>
              <Switch data-testid="set-cod" checked={Boolean(form.cod_available)} onCheckedChange={(v) => set("cod_available", v)} />
            </div>
            <div className="flex items-center justify-between">
              <div><p className="text-sm font-medium text-gray-700">Maintenance Mode</p><p className="text-xs text-gray-400">Flag for taking the store offline (storefront still visible in this version)</p></div>
              <Switch data-testid="set-maintenance" checked={Boolean(form.maintenance_mode)} onCheckedChange={(v) => set("maintenance_mode", v)} />
            </div>
          </div>
        </div>

        <button data-testid="settings-save" onClick={save} disabled={saving} className="h-11 px-6 bg-aayna-rose text-white rounded-md font-semibold hover:bg-aayna-rose-dark disabled:opacity-60 flex items-center gap-2">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save Settings
        </button>
      </div>
    </div>
  );
}
