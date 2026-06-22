import { useState, useRef } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Search, Pencil, Trash2, Download, Upload, Loader2 } from "lucide-react";
import { getAdminProducts, deleteProduct, downloadCsv, importProducts, getAdminCategories } from "@/admin/adminApi";
import { formatBDT, effectivePrice } from "@/lib/format";
import { statusStyle } from "@/admin/statusColors";

export default function Products() {
  const qc = useQueryClient();
  const fileRef = useRef();
  const [filters, setFilters] = useState({ category: "", status: "", search: "" });
  const [importing, setImporting] = useState(false);

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["admin-products", filters],
    queryFn: () => getAdminProducts({
      ...(filters.category ? { category: filters.category } : {}),
      ...(filters.status ? { status: filters.status } : {}),
      ...(filters.search ? { search: filters.search } : {}),
    }),
  });
  const { data: categories = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: getAdminCategories });

  const del = useMutation({
    mutationFn: deleteProduct,
    onSuccess: (r) => {
      toast.success(r.deleted ? "Product deleted" : "Product deactivated (has order history)");
      qc.invalidateQueries({ queryKey: ["admin-products"] });
    },
    onError: () => toast.error("Action failed"),
  });

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const r = await importProducts(file);
      toast.success(`Imported: ${r.created} created, ${r.updated} updated${r.errors.length ? `, ${r.errors.length} errors` : ""}`);
      qc.invalidateQueries({ queryKey: ["admin-products"] });
    } catch {
      toast.error("Import failed");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Products</h1>
        <div className="flex items-center gap-2">
          <button onClick={() => downloadCsv("products", "aayna_products.csv")} className="h-10 px-3 border border-gray-300 rounded-md text-sm flex items-center gap-1.5 hover:bg-gray-50">
            <Download className="h-4 w-4" /> Export
          </button>
          <button data-testid="import-products-btn" onClick={() => fileRef.current?.click()} disabled={importing} className="h-10 px-3 border border-gray-300 rounded-md text-sm flex items-center gap-1.5 hover:bg-gray-50">
            {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Import CSV
          </button>
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleImport} />
          <Link to="/admin/products/new" data-testid="add-product-btn" className="h-10 px-4 bg-aayna-rose text-white rounded-md text-sm font-semibold flex items-center gap-1.5 hover:bg-aayna-rose-dark">
            <Plus className="h-4 w-4" /> Add Product
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="h-4 w-4 absolute left-3 top-3 text-gray-400" />
          <input data-testid="product-search" value={filters.search} onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))} placeholder="Search name or SKU" className="w-full h-10 pl-9 pr-3 border border-gray-300 rounded-md text-sm outline-none focus:border-aayna-rose" />
        </div>
        <select value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))} className="h-10 px-3 border border-gray-300 rounded-md text-sm bg-white">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </select>
        <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} className="h-10 px-3 border border-gray-300 rounded-md text-sm bg-white">
          <option value="">All status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="draft">Draft</option>
          <option value="out_of_stock">Out of stock</option>
        </select>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Stock</th>
                <th className="px-4 py-3 font-medium">Price</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-rose mx-auto" /></td></tr>
              ) : products.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">No products found.</td></tr>
              ) : products.map((p) => (
                <tr key={p.id} data-testid={`product-row-${p.sku}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-11 w-11 rounded bg-gray-100 overflow-hidden flex-shrink-0">
                        {p.images?.[0]?.image_url && <img src={p.images[0].image_url} alt="" className="w-full h-full object-cover" />}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-aayna-charcoal line-clamp-1">{p.product_name}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{p.sku}</td>
                  <td className="px-4 py-3 text-gray-500">{p.category_name}</td>
                  <td className="px-4 py-3">{p.stock_quantity}</td>
                  <td className="px-4 py-3 font-medium text-aayna-rose">{formatBDT(effectivePrice(p))}</td>
                  <td className="px-4 py-3"><span className={`text-xs font-semibold px-2 py-1 rounded ${statusStyle(p.status)}`}>{p.status.replace("_", " ")}</span></td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <Link to={`/admin/products/${p.id}`} data-testid={`edit-product-${p.sku}`} className="p-2 text-gray-500 hover:text-aayna-rose" title="Edit"><Pencil className="h-4 w-4" /></Link>
                      <button onClick={() => { if (window.confirm(`Delete/deactivate ${p.product_name}?`)) del.mutate(p.id); }} className="p-2 text-gray-500 hover:text-red-600" title="Delete"><Trash2 className="h-4 w-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
