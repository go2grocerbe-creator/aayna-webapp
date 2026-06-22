import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Pencil, Loader2 } from "lucide-react";
import { getAdminCategories, createCategory, updateCategory } from "@/admin/adminApi";
import { statusStyle } from "@/admin/statusColors";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import ImageUpload from "@/admin/ImageUpload";

const EMPTY = { name: "", slug: "", description: "", sku_prefix: "", image_url: "", sort_order: 0, status: "active" };

export default function Categories() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const { data: categories = [], isLoading } = useQuery({ queryKey: ["admin-categories"], queryFn: getAdminCategories });

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ ...EMPTY, ...c }); setOpen(true); };
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.name) { toast.error("Category name is required"); return; }
    setSaving(true);
    try {
      const payload = { name: form.name, description: form.description, sku_prefix: form.sku_prefix, image_url: form.image_url, sort_order: Number(form.sort_order) || 0, status: form.status };
      if (editing) await updateCategory(editing.id, payload);
      else await createCategory(payload);
      toast.success(editing ? "Category updated" : "Category created");
      qc.invalidateQueries({ queryKey: ["admin-categories"] });
      setOpen(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose text-sm";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Categories</h1>
        <button data-testid="add-category-btn" onClick={openNew} className="h-10 px-4 bg-aayna-rose text-white rounded-md text-sm font-semibold flex items-center gap-1.5 hover:bg-aayna-rose-dark"><Plus className="h-4 w-4" /> Add Category</button>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Category</th>
              <th className="px-4 py-3 font-medium">Slug</th>
              <th className="px-4 py-3 font-medium">Products</th>
              <th className="px-4 py-3 font-medium">Order</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-rose mx-auto" /></td></tr>
            ) : categories.map((c) => (
              <tr key={c.id} data-testid={`category-row-${c.slug}`} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded bg-gray-100 overflow-hidden flex-shrink-0">{c.image_url && <img src={c.image_url} alt="" className="w-full h-full object-cover" />}</div>
                    <span className="font-medium text-aayna-charcoal">{c.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-500">{c.slug}</td>
                <td className="px-4 py-3">{c.product_count}</td>
                <td className="px-4 py-3">{c.sort_order}</td>
                <td className="px-4 py-3"><span className={`text-xs font-semibold px-2 py-1 rounded ${statusStyle(c.status)}`}>{c.status}</span></td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => openEdit(c)} data-testid={`edit-category-${c.slug}`} className="p-2 text-gray-500 hover:text-aayna-rose"><Pencil className="h-4 w-4" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editing ? "Edit Category" : "Add Category"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Name *</label><input data-testid="cat-name" className={field} value={form.name} onChange={(e) => set("name", e.target.value)} /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Description</label><textarea rows={2} className={`${field} h-auto py-2 resize-none`} value={form.description} onChange={(e) => set("description", e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="block text-sm font-medium text-gray-700 mb-1.5">SKU Prefix</label><input className={field} value={form.sku_prefix} onChange={(e) => set("sku_prefix", e.target.value)} placeholder="EAR" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Sort Order</label><input type="number" className={field} value={form.sort_order} onChange={(e) => set("sort_order", e.target.value)} /></div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Image</label>
              <ImageUpload images={form.image_url ? [{ image_url: form.image_url, alt_text: form.name, is_main: true }] : []} onChange={(imgs) => set("image_url", imgs[0]?.image_url || "")} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-700">Active</span>
              <Switch checked={form.status === "active"} onCheckedChange={(v) => set("status", v ? "active" : "inactive")} />
            </div>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="h-10 px-4 border border-gray-300 rounded-md text-sm">Cancel</button>
            <button data-testid="cat-save" onClick={save} disabled={saving} className="h-10 px-5 bg-aayna-rose text-white rounded-md text-sm font-semibold flex items-center gap-2 disabled:opacity-60">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Save</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
