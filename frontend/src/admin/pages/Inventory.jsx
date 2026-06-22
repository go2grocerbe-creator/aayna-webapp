import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Plus, History, AlertTriangle } from "lucide-react";
import { getInventory, adjustStock, getInventoryLogs } from "@/admin/adminApi";
import { statusStyle } from "@/admin/statusColors";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

export default function Inventory() {
  const qc = useQueryClient();
  const [lowOnly, setLowOnly] = useState(false);
  const [adjustFor, setAdjustFor] = useState(null);
  const [logsFor, setLogsFor] = useState(null);
  const [adj, setAdj] = useState({ change_type: "stock_in", quantity_change: "", reason: "" });
  const [saving, setSaving] = useState(false);

  const { data: products = [], isLoading } = useQuery({ queryKey: ["admin-inventory", lowOnly], queryFn: () => getInventory(lowOnly) });
  const { data: logs = [] } = useQuery({ queryKey: ["inv-logs", logsFor?.id], queryFn: () => getInventoryLogs(logsFor.id), enabled: Boolean(logsFor) });

  const isLow = (p) => p.stock_quantity <= p.low_stock_alert;

  const openAdjust = (p) => { setAdjustFor(p); setAdj({ change_type: "stock_in", quantity_change: "", reason: "" }); };

  const saveAdjust = async () => {
    const qty = Number(adj.quantity_change);
    if (!qty) { toast.error("Enter a quantity (use negative to reduce)"); return; }
    setSaving(true);
    try {
      await adjustStock(adjustFor.id, { change_type: adj.change_type, quantity_change: qty, reason: adj.reason });
      toast.success("Stock updated");
      qc.invalidateQueries({ queryKey: ["admin-inventory"] });
      setAdjustFor(null);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    } finally { setSaving(false); }
  };

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose text-sm";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Inventory</h1>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input data-testid="low-stock-toggle" type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} className="accent-aayna-rose h-4 w-4" />
          Low stock only
        </label>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Stock</th>
                <th className="px-4 py-3 font-medium">Low Alert</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr><td colSpan={6} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-rose mx-auto" /></td></tr>
              ) : products.map((p) => (
                <tr key={p.id} data-testid={`inv-row-${p.sku}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-aayna-charcoal font-medium">{p.product_name}</td>
                  <td className="px-4 py-3 text-gray-500">{p.sku}</td>
                  <td className="px-4 py-3">
                    <span className={`font-semibold ${isLow(p) ? "text-red-600" : "text-aayna-charcoal"}`}>{p.stock_quantity}</span>
                    {isLow(p) && <AlertTriangle className="h-3.5 w-3.5 text-red-500 inline ml-1" />}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{p.low_stock_alert}</td>
                  <td className="px-4 py-3"><span className={`text-xs font-semibold px-2 py-1 rounded ${statusStyle(p.status)}`}>{p.status.replace("_", " ")}</span></td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => openAdjust(p)} data-testid={`adjust-stock-${p.sku}`} className="px-2.5 py-1.5 text-xs border border-gray-300 rounded-md flex items-center gap-1 hover:bg-gray-50"><Plus className="h-3.5 w-3.5" /> Adjust</button>
                      <button onClick={() => setLogsFor(p)} className="p-2 text-gray-500 hover:text-aayna-rose" title="View log"><History className="h-4 w-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Adjust dialog */}
      <Dialog open={Boolean(adjustFor)} onOpenChange={(o) => !o && setAdjustFor(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Adjust Stock — {adjustFor?.product_name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-gray-500">Current stock: <strong>{adjustFor?.stock_quantity}</strong></p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Type</label>
              <select className={`${field} bg-white`} value={adj.change_type} onChange={(e) => setAdj((a) => ({ ...a, change_type: e.target.value }))}>
                <option value="stock_in">Stock In</option>
                <option value="adjustment">Adjustment</option>
                <option value="damage">Damage</option>
                <option value="return">Return</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Quantity Change</label>
              <input data-testid="adjust-qty" type="number" className={field} value={adj.quantity_change} onChange={(e) => setAdj((a) => ({ ...a, quantity_change: e.target.value }))} placeholder="e.g. 10 or -2" />
              <p className="text-xs text-gray-400 mt-1">Use a negative number to reduce stock.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Reason</label>
              <input className={field} value={adj.reason} onChange={(e) => setAdj((a) => ({ ...a, reason: e.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <button onClick={() => setAdjustFor(null)} className="h-10 px-4 border border-gray-300 rounded-md text-sm">Cancel</button>
            <button data-testid="adjust-save" onClick={saveAdjust} disabled={saving} className="h-10 px-5 bg-aayna-rose text-white rounded-md text-sm font-semibold flex items-center gap-2 disabled:opacity-60">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Apply</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Logs dialog */}
      <Dialog open={Boolean(logsFor)} onOpenChange={(o) => !o && setLogsFor(null)}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Inventory Log — {logsFor?.product_name}</DialogTitle></DialogHeader>
          {logs.length ? (
            <ul className="divide-y divide-gray-100 text-sm">
              {logs.map((l) => (
                <li key={l.id} className="py-2.5 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-aayna-charcoal capitalize">{l.change_type.replace("_", " ")}</span>
                    <span className="text-gray-400 ml-2">{l.reason}</span>
                    <div className="text-xs text-gray-400">{new Date(l.created_at).toLocaleString()}</div>
                  </div>
                  <div className="text-right">
                    <span className={`font-semibold ${l.quantity_change >= 0 ? "text-green-600" : "text-red-600"}`}>{l.quantity_change >= 0 ? "+" : ""}{l.quantity_change}</span>
                    <div className="text-xs text-gray-400">{l.previous_stock} → {l.new_stock}</div>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-400">No log entries yet.</p>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
