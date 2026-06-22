import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Phone, MapPin, Mail, StickyNote } from "lucide-react";
import { getAdminOrder, updateOrder } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";
import { statusStyle, ORDER_STATUSES } from "@/admin/statusColors";

export default function OrderDetail() {
  const { orderNumber } = useParams();
  const qc = useQueryClient();
  const { data: order, isLoading } = useQuery({ queryKey: ["admin-order", orderNumber], queryFn: () => getAdminOrder(orderNumber) });

  const [form, setForm] = useState({ order_status: "", courier_name: "", courier_tracking_code: "", admin_note: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (order) setForm({
      order_status: order.order_status,
      courier_name: order.courier_name || "",
      courier_tracking_code: order.courier_tracking_code || "",
      admin_note: order.admin_note || "",
    });
  }, [order]);

  if (isLoading || !order) {
    return <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-aayna-rose" /></div>;
  }

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await updateOrder(orderNumber, form);
      toast.success("Order updated");
      qc.invalidateQueries({ queryKey: ["admin-order", orderNumber] });
      qc.invalidateQueries({ queryKey: ["admin-orders"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Update failed");
    } finally {
      setSaving(false);
    }
  };

  const field = "w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose text-sm";

  return (
    <div className="max-w-4xl">
      <Link to="/admin/orders" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-aayna-rose mb-4"><ArrowLeft className="h-4 w-4" /> Back to orders</Link>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-aayna-charcoal">{order.order_number}</h1>
          <p className="text-sm text-gray-400">{new Date(order.created_at).toLocaleString()}</p>
        </div>
        <span className={`text-xs font-semibold px-3 py-1.5 rounded ${statusStyle(order.order_status)}`}>{order.order_status}</span>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Customer */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <h2 className="font-semibold text-aayna-charcoal mb-3">Customer</h2>
            <p className="font-medium text-aayna-charcoal">{order.customer_name}</p>
            <div className="mt-2 space-y-1.5 text-sm text-gray-600">
              <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-gray-400" /> {order.customer_phone}</p>
              {order.customer_email && <p className="flex items-center gap-2"><Mail className="h-4 w-4 text-gray-400" /> {order.customer_email}</p>}
              <p className="flex items-start gap-2"><MapPin className="h-4 w-4 text-gray-400 mt-0.5" /> {order.delivery_address}, {order.district}</p>
              {order.delivery_note && <p className="flex items-start gap-2"><StickyNote className="h-4 w-4 text-gray-400 mt-0.5" /> {order.delivery_note}</p>}
            </div>
          </div>

          {/* Items */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <h2 className="font-semibold text-aayna-charcoal mb-3">Items</h2>
            <table className="w-full text-sm">
              <thead className="text-gray-400 text-left text-xs"><tr><th className="py-2">Product</th><th className="py-2">SKU</th><th className="py-2 text-center">Qty</th><th className="py-2 text-right">Unit</th><th className="py-2 text-right">Total</th></tr></thead>
              <tbody className="divide-y divide-gray-100">
                {order.items.map((it, i) => (
                  <tr key={i}>
                    <td className="py-2.5 text-aayna-charcoal">{it.product_name_snapshot}</td>
                    <td className="py-2.5 text-gray-400">{it.sku_snapshot}</td>
                    <td className="py-2.5 text-center">{it.quantity}</td>
                    <td className="py-2.5 text-right">{formatBDT(it.unit_price)}</td>
                    <td className="py-2.5 text-right font-medium">{formatBDT(it.total_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="border-t border-gray-100 mt-3 pt-3 space-y-1.5 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Subtotal</span><span>{formatBDT(order.subtotal)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Delivery</span><span>{formatBDT(order.delivery_charge)}</span></div>
              {order.discount_amount > 0 && <div className="flex justify-between"><span className="text-gray-500">Discount</span><span>-{formatBDT(order.discount_amount)}</span></div>}
              <div className="flex justify-between font-bold text-base pt-1"><span>Total</span><span className="text-aayna-rose">{formatBDT(order.total_amount)}</span></div>
              <div className="flex justify-between pt-1"><span className="text-gray-500">Payment</span><span>{order.payment_method} · {order.payment_status}</span></div>
            </div>
          </div>

          {/* Notifications */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <h2 className="font-semibold text-aayna-charcoal mb-3">Notification History</h2>
            {order.notifications?.length ? (
              <ul className="space-y-2 text-sm">
                {order.notifications.map((n, i) => (
                  <li key={i} className="flex items-center justify-between">
                    <span className="text-gray-600">{n.notification_type}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${n.status === "sent" ? "bg-green-100 text-green-700" : n.status === "failed" ? "bg-red-100 text-red-600" : "bg-gray-100 text-gray-600"}`}>{n.status}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-gray-400">No notifications logged.</p>}
            <p className="text-xs text-gray-400 mt-3">Notifications are a placeholder in this version (no real send).</p>
          </div>
        </div>

        {/* Manage */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-gray-200 rounded-lg p-5 sticky top-6 space-y-4">
            <h2 className="font-semibold text-aayna-charcoal">Manage Order</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Status</label>
              <select data-testid="order-status-select" className={`${field} bg-white`} value={form.order_status} onChange={(e) => set("order_status", e.target.value)}>
                {ORDER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Courier Name</label>
              <input data-testid="order-courier-name" className={field} value={form.courier_name} onChange={(e) => set("courier_name", e.target.value)} placeholder="e.g. Pathao, Steadfast" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Tracking Code</label>
              <input data-testid="order-tracking-code" className={field} value={form.courier_tracking_code} onChange={(e) => set("courier_tracking_code", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Internal Admin Note</label>
              <textarea rows={3} data-testid="order-admin-note" className={`${field} h-auto py-2 resize-none`} value={form.admin_note} onChange={(e) => set("admin_note", e.target.value)} />
            </div>
            <button data-testid="order-save" onClick={save} disabled={saving} className="w-full h-11 bg-aayna-rose text-white rounded-md font-semibold hover:bg-aayna-rose-dark disabled:opacity-60 flex items-center justify-center gap-2">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Save Changes</button>
          </div>
        </div>
      </div>
    </div>
  );
}
