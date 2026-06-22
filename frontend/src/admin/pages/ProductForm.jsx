import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { getAdminProduct, createProduct, updateProduct, getAdminCategories } from "@/admin/adminApi";
import { Switch } from "@/components/ui/switch";
import ImageUpload from "@/admin/ImageUpload";

const EMPTY = {
  product_name: "", sku: "", category_slug: "", short_description: "", full_description: "",
  cost_price: "", selling_price: "", discount_price: "", stock_quantity: "", low_stock_alert: 3,
  material: "", color: "", size: "", status: "active",
  is_featured: false, is_best_seller: false, is_new_arrival: false, images: [],
};

export default function ProductForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const { data: categories = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: getAdminCategories });
  const { data: product } = useQuery({ queryKey: ["admin-product", id], queryFn: () => getAdminProduct(id), enabled: isEdit });

  useEffect(() => {
    if (product) {
      setForm({
        ...EMPTY, ...product,
        discount_price: product.discount_price ?? "",
        cost_price: product.cost_price ?? "",
        images: product.images || [],
      });
    }
  }, [product]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.product_name || !form.sku || !form.category_slug || form.selling_price === "" || form.stock_quantity === "") {
      toast.error("Name, SKU, category, selling price and stock are required");
      return;
    }
    const payload = {
      ...form,
      selling_price: Number(form.selling_price),
      cost_price: form.cost_price === "" ? 0 : Number(form.cost_price),
      discount_price: form.discount_price === "" ? null : Number(form.discount_price),
      stock_quantity: Number(form.stock_quantity),
      low_stock_alert: Number(form.low_stock_alert) || 3,
    };
    setSaving(true);
    try {
      if (isEdit) {
        await updateProduct(id, payload);
        toast.success("Product updated");
      } else {
        await createProduct(payload);
        toast.success("Product created");
      }
      navigate("/admin/products");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose focus:ring-1 focus:ring-aayna-rose text-sm";

  return (
    <div className="max-w-3xl">
      <Link to="/admin/products" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-aayna-rose mb-4"><ArrowLeft className="h-4 w-4" /> Back to products</Link>
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-6">{isEdit ? "Edit Product" : "Add Product"}</h1>

      <form onSubmit={submit} className="space-y-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6 grid sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Product Name *</label>
            <input data-testid="pf-name" className={field} value={form.product_name} onChange={(e) => set("product_name", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">SKU *</label>
            <input data-testid="pf-sku" className={field} value={form.sku} onChange={(e) => set("sku", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Category *</label>
            <select data-testid="pf-category" className={`${field} bg-white`} value={form.category_slug} onChange={(e) => set("category_slug", e.target.value)}>
              <option value="">Select category</option>
              {categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Short Description</label>
            <input className={field} value={form.short_description} onChange={(e) => set("short_description", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Description</label>
            <textarea rows={3} className={`${field} h-auto py-2 resize-none`} value={form.full_description} onChange={(e) => set("full_description", e.target.value)} />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Pricing & Stock</h2>
          <div className="grid sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Selling Price (৳) *</label>
              <input data-testid="pf-selling-price" type="number" className={field} value={form.selling_price} onChange={(e) => set("selling_price", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Discount Price (৳)</label>
              <input data-testid="pf-discount-price" type="number" className={field} value={form.discount_price} onChange={(e) => set("discount_price", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Cost Price (৳)</label>
              <input type="number" className={field} value={form.cost_price} onChange={(e) => set("cost_price", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Stock Quantity *</label>
              <input data-testid="pf-stock" type="number" className={field} value={form.stock_quantity} onChange={(e) => set("stock_quantity", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Low Stock Alert</label>
              <input type="number" className={field} value={form.low_stock_alert} onChange={(e) => set("low_stock_alert", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Status</label>
              <select className={`${field} bg-white`} value={form.status} onChange={(e) => set("status", e.target.value)}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="draft">Draft</option>
                <option value="out_of_stock">Out of stock</option>
              </select>
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-4 mt-4">
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Material</label><input className={field} value={form.material} onChange={(e) => set("material", e.target.value)} /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Color</label><input className={field} value={form.color} onChange={(e) => set("color", e.target.value)} /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Size</label><input className={field} value={form.size} onChange={(e) => set("size", e.target.value)} /></div>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Images</h2>
          <ImageUpload images={form.images} onChange={(imgs) => set("images", imgs)} />
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h2 className="font-semibold text-aayna-charcoal">Visibility</h2>
          {[["is_featured", "Featured"], ["is_best_seller", "Best Seller"], ["is_new_arrival", "New Arrival"]].map(([key, label]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-gray-700">{label}</span>
              <Switch data-testid={`pf-${key}`} checked={form[key]} onCheckedChange={(v) => set(key, v)} />
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button data-testid="pf-save" type="submit" disabled={saving} className="h-11 px-6 bg-aayna-rose text-white rounded-md font-semibold hover:bg-aayna-rose-dark disabled:opacity-60 flex items-center gap-2">
            {saving && <Loader2 className="h-4 w-4 animate-spin" />} {isEdit ? "Save Changes" : "Create Product"}
          </button>
          <Link to="/admin/products" className="h-11 px-6 border border-gray-300 rounded-md font-medium flex items-center hover:bg-gray-50">Cancel</Link>
        </div>
      </form>
    </div>
  );
}
