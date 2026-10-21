import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { getAdminProduct, createProduct, updateProduct, getAdminCategories } from "@/admin/adminApi";
import { Switch } from "@/components/ui/switch";
import GalleryManager from "@/admin/GalleryManager";
import { useAdminAuth } from "@/admin/AdminAuthContext";
import { withBrand } from "@/lib/seo";
import ProductDescription from "@/components/ProductDescription";
import { getProductContentHistory } from "@/admin/adminApi";

// Description & details limits (same as backend/product_content.py).
const LIM = { short_description: 300, full_description: 3000, material: 120, size: 120, care_note: 500, seo_title: 70, seo_description: 170 };
const HL_MAX = 6, HL_LEN = 120;
const completeness = (f) => {
  const s = !!(f.short_description || "").trim(), d = !!(f.full_description || "").trim();
  return s && d ? "complete" : s || d ? "partial" : "missing";
};
const COMPLETE_LABEL = { complete: ["Description complete", "bg-green-100 text-green-800"], partial: ["Description partly written", "bg-amber-100 text-amber-900"], missing: ["No description yet", "bg-gray-100 text-gray-700"] };

const PUBLIC_STATUSES = ["active", "out_of_stock"];

const EMPTY = {
  product_name: "", sku: "", category_slug: "", short_description: "", full_description: "",
  cost_price: "", selling_price: "", discount_price: "", stock_quantity: "", low_stock_alert: 3,
  material: "", color: "", size: "", status: "draft",
  is_featured: false, is_best_seller: false, is_new_arrival: false, images: [],
  highlights_text: "", care_note: "", seo_title: "", seo_description: "",
};

export default function ProductForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const { can } = useAdminAuth();
  const canEdit = can("products.edit");
  const canCost = can("products.cost");

  const { data: categories = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: getAdminCategories });
  const { data: product } = useQuery({ queryKey: ["admin-product", id], queryFn: () => getAdminProduct(id), enabled: isEdit });

  useEffect(() => {
    if (product) {
      setForm({
        ...EMPTY, ...product,
        discount_price: product.discount_price ?? "",
        cost_price: product.cost_price ?? "",
        images: product.images || [],
        highlights_text: (product.highlights || []).join("\n"),
        care_note: product.care_note || "", seo_title: product.seo_title || "", seo_description: product.seo_description || "",
        short_description: product.short_description || "", full_description: product.full_description || "",
        material: product.material || "", size: product.size || "",
      });
    }
  }, [product]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const [preview, setPreview] = useState(false);
  const { data: history = [] } = useQuery({ queryKey: ["admin-product-content-history", id], queryFn: () => getProductContentHistory(id), enabled: isEdit });
  const highlights = (form.highlights_text || "").split("\n").map((h) => h.trim()).filter(Boolean);
  const tooLong = Object.entries(LIM).filter(([k, n]) => (form[k] || "").length > n).map(([k]) => k);
  const hlProblem = highlights.length > HL_MAX ? `At most ${HL_MAX} detail lines` : highlights.some((h) => h.length > HL_LEN) ? `Each detail line: at most ${HL_LEN} characters` : null;
  const count = (k) => (
    <span className={`text-[11px] ${(form[k] || "").length > LIM[k] ? "text-red-700 font-semibold" : "text-gray-400"}`}>{(form[k] || "").length}/{LIM[k]}</span>
  );

  const submit = async (e) => {
    e.preventDefault();
    if (!form.product_name || !form.sku || !form.category_slug || form.selling_price === "" || form.stock_quantity === "") {
      toast.error("Name, SKU, category, selling price and stock are required");
      return;
    }
    if (Number(form.selling_price) <= 0) {
      toast.error("Selling price must be greater than 0");
      return;
    }
    if (tooLong.length || hlProblem) {
      toast.error(hlProblem || "Some description fields are too long");
      return;
    }
    const wasPublic = isEdit && PUBLIC_STATUSES.includes(product?.status);
    if (PUBLIC_STATUSES.includes(form.status) && !wasPublic &&
        !window.confirm("This status makes the product visible and purchasable on the public shop. Continue?")) {
      return;
    }
    const payload = {
      ...form,
      selling_price: Number(form.selling_price),
      discount_price: form.discount_price === "" ? null : Number(form.discount_price),
      stock_quantity: Number(form.stock_quantity),
      low_stock_alert: Number(form.low_stock_alert) || 3,
      highlights,
    };
    delete payload.highlights_text;
    delete payload.content_status;
    // Gallery writes are revision-checked through GalleryManager. Never let a stale
    // product form overwrite a newer photo upload/order change.
    delete payload.images;
    // Purchase cost: only sent by roles allowed to see it, and only with a value.
    if (canCost && form.cost_price !== "") payload.cost_price = Number(form.cost_price);
    else delete payload.cost_price;
    if (isEdit) {
      // SKU is the product's identity and stock changes go through Inventory (logged).
      delete payload.sku;
      delete payload.stock_quantity;
    }
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

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-burgundy focus:ring-1 focus:ring-aayna-burgundy text-sm";

  return (
    <div className="max-w-3xl">
      <Link to="/admin/products" className="inline-flex items-center gap-1.5 min-h-[44px] text-sm text-gray-500 hover:text-aayna-burgundy mb-2"><ArrowLeft className="h-4 w-4" /> Back to products</Link>
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-6">{isEdit ? (canEdit ? "Edit Product" : "Product") : "Add Product"}</h1>

      <form onSubmit={submit} className="space-y-6">
        <fieldset disabled={!canEdit} className="space-y-6 min-w-0">
        <div className="bg-white border border-gray-200 rounded-lg p-6 grid sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label htmlFor="pf-field-1" className="block text-sm font-medium text-gray-700 mb-1.5">Product Name *</label>
            <input id="pf-field-1" data-testid="pf-name" className={field} value={form.product_name} onChange={(e) => set("product_name", e.target.value)} />
          </div>
          <div>
            <label htmlFor="pf-field-2" className="block text-sm font-medium text-gray-700 mb-1.5">SKU *</label>
            <input id="pf-field-2" data-testid="pf-sku" className={`${field} ${isEdit ? "bg-gray-50 text-gray-500" : ""}`} value={form.sku} readOnly={isEdit} onChange={(e) => set("sku", e.target.value)} />
            {isEdit && <p className="text-xs text-gray-400 mt-1">SKU is the product's permanent identity and cannot be changed.</p>}
          </div>
          <div>
            <label htmlFor="pf-field-3" className="block text-sm font-medium text-gray-700 mb-1.5">Category *</label>
            <select id="pf-field-3" data-testid="pf-category" className={`${field} bg-white`} value={form.category_slug} onChange={(e) => set("category_slug", e.target.value)}>
              <option value="">Select category</option>
              {categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </select>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4 min-w-0" data-testid="pf-content">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-aayna-charcoal">Description &amp; details</h2>
            <span data-testid="pf-content-status" className={`text-xs font-semibold px-2.5 py-1 rounded ${COMPLETE_LABEL[completeness(form)][1]}`}>{COMPLETE_LABEL[completeness(form)][0]}</span>
          </div>
          <p className="text-xs text-gray-500">Plain text. Write only what is verified for this piece; leave a field empty when it is not known (empty fields are not shown to customers). Saving keeps the product's status: a draft stays a draft.</p>
          <div>
            <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-short" className="text-sm font-medium text-gray-700">Short description</label>{count("short_description")}</div>
            <textarea id="pf-short" data-testid="pf-short" rows={2} className={`${field} h-auto py-2 resize-y`} value={form.short_description} onChange={(e) => set("short_description", e.target.value)} placeholder="One or two sentences shown under the price" />
          </div>
          <div>
            <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-full" className="text-sm font-medium text-gray-700">Description</label>{count("full_description")}</div>
            <textarea id="pf-full" data-testid="pf-full" rows={7} className={`${field} h-auto py-2 resize-y`} value={form.full_description} onChange={(e) => set("full_description", e.target.value)} placeholder="Leave an empty line between paragraphs" />
          </div>
          <div>
            <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-highlights" className="text-sm font-medium text-gray-700">Product details <span className="text-gray-400 font-normal">(one per line, up to {HL_MAX})</span></label>
              <span className={`text-[11px] ${hlProblem ? "text-red-700 font-semibold" : "text-gray-400"}`}>{highlights.length}/{HL_MAX}</span></div>
            <textarea id="pf-highlights" data-testid="pf-highlights" rows={3} className={`${field} h-auto py-2 resize-y`} value={form.highlights_text} onChange={(e) => set("highlights_text", e.target.value)} placeholder={"e.g. Sold as a pair\nClasp closure"} />
            {hlProblem && <p className="text-xs text-red-700 mt-1">{hlProblem}</p>}
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-field-12" className="text-sm font-medium text-gray-700">Material <span className="text-gray-400 font-normal">(only if verified)</span></label>{count("material")}</div>
              <input id="pf-field-12" data-testid="pf-material" className={field} value={form.material} onChange={(e) => set("material", e.target.value)} />
            </div>
            <div>
              <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-field-14" className="text-sm font-medium text-gray-700">Size / dimensions</label>{count("size")}</div>
              <input id="pf-field-14" data-testid="pf-size" className={field} value={form.size} onChange={(e) => set("size", e.target.value)} />
            </div>
          </div>
          <div>
            <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-care" className="text-sm font-medium text-gray-700">Care <span className="text-gray-400 font-normal">(only if the material is known)</span></label>{count("care_note")}</div>
            <textarea id="pf-care" data-testid="pf-care" rows={2} className={`${field} h-auto py-2 resize-y`} value={form.care_note} onChange={(e) => set("care_note", e.target.value)} />
          </div>
          <div className="border-t border-gray-100 pt-4 grid sm:grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-seo-title" className="text-sm font-medium text-gray-700">SEO title</label>{count("seo_title")}</div>
              <input id="pf-seo-title" data-testid="pf-seo-title" className={field} value={form.seo_title} onChange={(e) => set("seo_title", e.target.value)} placeholder={form.product_name || "Defaults to the product name"} />
            </div>
            <div>
              <div className="flex justify-between items-baseline mb-1.5"><label htmlFor="pf-seo-desc" className="text-sm font-medium text-gray-700">SEO description</label>{count("seo_description")}</div>
              <input id="pf-seo-desc" data-testid="pf-seo-description" className={field} value={form.seo_description} onChange={(e) => set("seo_description", e.target.value)} placeholder="Defaults to a line built from the short description" />
            </div>
            <div className="sm:col-span-2 rounded-md bg-gray-50 px-3 py-2 min-w-0" data-testid="pf-seo-preview">
              <p className="text-[11px] text-gray-400 mb-0.5">Search result preview</p>
              <p className="text-sm text-[#1a0dab] truncate">{withBrand(form.seo_title || form.product_name || "Product name")}</p>
              <p className="text-xs text-gray-600 line-clamp-2 break-words">{form.seo_description || form.short_description || "Built from the product name, category, short description and price."}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" data-testid="pf-preview-toggle" onClick={() => setPreview((v) => !v)} className="min-h-[44px] px-4 border border-gray-300 rounded-md text-sm font-medium hover:bg-gray-50">
              {preview ? "Hide customer preview" : "Preview as customers see it"}
            </button>
          </div>
          {preview && (
            <div data-testid="pf-preview" className="rounded-md border border-dashed border-gray-300 bg-aayna-cream p-4 min-w-0">
              <p className="text-[11px] uppercase tracking-wider text-gray-400 mb-2">Customer preview (not saved yet)</p>
              <p className="font-display font-semibold text-xl text-aayna-charcoal">{form.product_name || "Product name"}</p>
              {form.short_description && <p className="text-aayna-taupe text-sm leading-relaxed mt-2 mb-4 whitespace-pre-line">{form.short_description}</p>}
              <ProductDescription product={{ ...form, highlights }} />
            </div>
          )}
          {isEdit && history.length > 0 && (
            <details data-testid="pf-content-history">
              <summary className="text-sm text-gray-600 cursor-pointer min-h-[44px] flex items-center">Description change history ({history.length})</summary>
              <ul className="text-xs text-gray-500 space-y-1">
                {history.slice(0, 20).map((h) => (
                  <li key={h.id}>{new Date(h.created_at).toLocaleString("en-GB")} · {h.actor} · {Object.keys(h.changes).join(", ")}</li>
                ))}
              </ul>
            </details>
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Pricing & Stock</h2>
          <div className="grid sm:grid-cols-3 gap-4">
            <div>
              <label htmlFor="pf-field-6" className="block text-sm font-medium text-gray-700 mb-1.5">Selling Price (৳) *</label>
              <input id="pf-field-6" data-testid="pf-selling-price" type="number" className={field} value={form.selling_price} onChange={(e) => set("selling_price", e.target.value)} />
            </div>
            <div>
              <label htmlFor="pf-field-7" className="block text-sm font-medium text-gray-700 mb-1.5">Discount Price (৳)</label>
              <input id="pf-field-7" data-testid="pf-discount-price" type="number" className={field} value={form.discount_price} onChange={(e) => set("discount_price", e.target.value)} />
            </div>
            {canCost && (
              <div>
                <label htmlFor="pf-field-8" className="block text-sm font-medium text-gray-700 mb-1.5">Purchase Cost (৳) <span className="text-xs text-gray-400 font-normal">private</span></label>
                <input id="pf-field-8" data-testid="pf-cost" type="number" className={field} value={form.cost_price} onChange={(e) => set("cost_price", e.target.value)} />
              </div>
            )}
            <div>
              <label htmlFor="pf-field-9" className="block text-sm font-medium text-gray-700 mb-1.5">Stock Quantity *</label>
              <input id="pf-field-9" data-testid="pf-stock" type="number" min="0" readOnly={isEdit}
                className={`${field} ${isEdit ? "bg-gray-50 text-gray-500" : ""}`} value={form.stock_quantity} onChange={(e) => set("stock_quantity", e.target.value)} />
              {isEdit && <p className="text-xs text-gray-400 mt-1">Change stock in <Link to="/admin/inventory" className="underline">Inventory</Link> (every change is logged with a reason).</p>}
            </div>
            <div>
              <label htmlFor="pf-field-10" className="block text-sm font-medium text-gray-700 mb-1.5">Low Stock Alert</label>
              <input id="pf-field-10" type="number" className={field} value={form.low_stock_alert} onChange={(e) => set("low_stock_alert", e.target.value)} />
            </div>
            <div>
              <label htmlFor="pf-field-11" className="block text-sm font-medium text-gray-700 mb-1.5">Status</label>
              <select id="pf-field-11" className={`${field} bg-white`} value={form.status} onChange={(e) => set("status", e.target.value)}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="draft">Draft</option>
                <option value="out_of_stock">Out of stock</option>
              </select>
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-4 mt-4">
            <div><label htmlFor="pf-field-13" className="block text-sm font-medium text-gray-700 mb-1.5">Color</label><input id="pf-field-13" className={field} value={form.color} onChange={(e) => set("color", e.target.value)} /></div>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-aayna-charcoal mb-4">Images</h2>
          {/* Reviewed static photos: order + cover chosen here (backend/gallery.py, revision-checked). */}
          {isEdit ? <GalleryManager productId={id} canEdit={canEdit} /> :
            <p className="text-sm text-gray-600">Save the product as a draft first, then upload and arrange its photos.</p>}
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h2 className="font-semibold text-aayna-charcoal">Visibility</h2>
          {[["is_featured", "Featured"], ["is_best_seller", "Best Seller"], ["is_new_arrival", "New Arrival"]].map(([key, label]) => (
            <div key={key} className="flex items-center justify-between">
              <label htmlFor={`pf-switch-${key}`} className="text-sm text-gray-700 cursor-pointer flex-1 min-h-[44px] flex items-center">{label}</label>
              <Switch id={`pf-switch-${key}`} data-testid={`pf-${key}`} checked={form[key]} onCheckedChange={(v) => set(key, v)} />
            </div>
          ))}
        </div>

        </fieldset>
        <div className="flex items-center gap-3">
          {canEdit && <button data-testid="pf-save" type="submit" disabled={saving} className="h-11 px-6 bg-aayna-burgundy text-white rounded-md font-semibold hover:bg-aayna-burgundy-dark disabled:opacity-60 flex items-center gap-2">
            {saving && <Loader2 className="h-4 w-4 animate-spin" />} {isEdit ? "Save Changes" : "Create Product"}
          </button>}
          <Link to="/admin/products" className="h-11 px-6 border border-gray-300 rounded-md font-medium flex items-center hover:bg-gray-50">{canEdit ? "Cancel" : "Back"}</Link>
        </div>
      </form>
    </div>
  );
}
