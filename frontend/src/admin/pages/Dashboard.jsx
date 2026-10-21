import { useQuery } from "@tanstack/react-query";
import AdminLoadError from "@/admin/AdminLoadError";
import { Link } from "react-router-dom";
import {
  ShoppingCart, Clock, CheckCircle2, Truck, XCircle, TrendingUp, AlertTriangle, BellOff, Loader2,
  Package, FileEdit, Eye, PackageX, Boxes, PackageCheck, Undo2,
} from "lucide-react";
import { getDashboard } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";

function Card({ icon: Icon, label, value, accent, to, testid }) {
  const inner = (
    <div className="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between">
        <span className={`h-11 w-10 rounded-md flex items-center justify-center ${accent}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="text-2xl font-bold text-aayna-charcoal mt-3">{value}</p>
      <p className="text-sm text-gray-500 mt-0.5">{label}</p>
    </div>
  );
  return to ? <Link to={to} data-testid={testid}>{inner}</Link> : <div data-testid={testid}>{inner}</div>;
}

export default function Dashboard() {
  // Always re-read on open/focus so order counts never lag behind the Orders list.
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["admin-dashboard"], queryFn: getDashboard, refetchOnMount: "always", refetchOnWindowFocus: true });

  if (isError) return <AdminLoadError what="the dashboard" error={error} onRetry={refetch} />;

  if (isLoading || !data) {
    return <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-aayna-burgundy" /></div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-1">Dashboard</h1>
      <p className="text-gray-500 mb-6">Live figures from the store database.</p>

      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Catalogue</h2>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <Card testid="dash-catalogue-total" icon={Package} label="Products" value={data.catalogue?.total ?? 0} accent="bg-aayna-mist text-aayna-burgundy" to="/admin/products" />
        <Card testid="dash-catalogue-draft" icon={FileEdit} label="Draft (not public)" value={data.catalogue?.draft ?? 0} accent="bg-gray-100 text-gray-600" to="/admin/products" />
        <Card testid="dash-catalogue-active" icon={Eye} label="Active (public)" value={data.catalogue?.active ?? 0} accent="bg-green-100 text-green-700" to="/admin/products" />
        <Card testid="dash-catalogue-out_of_stock" icon={PackageX} label="Out of stock" value={data.catalogue?.out_of_stock ?? 0} accent="bg-red-100 text-red-600" to="/admin/inventory" />
        <Card testid="dash-catalogue-units" icon={Boxes} label="Units in stock" value={data.catalogue?.units_in_stock ?? 0} accent="bg-blue-100 text-blue-700" to="/admin/inventory" />
      </div>

      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Orders</h2>
      {data.total_orders === 0 && (
        <p data-testid="dash-no-orders" className="text-sm text-gray-500 mb-3">No orders yet. Order figures will appear here once customers start ordering.</p>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card testid="dash-card-todays_orders" icon={ShoppingCart} label="Today's Orders (Dhaka time)" value={data.todays_orders} accent="bg-blue-100 text-blue-700" to="/admin/orders" />
        <Card testid="dash-card-total_sales_today" icon={TrendingUp} label="Sales Today" value={formatBDT(data.total_sales_today)} accent="bg-aayna-mist text-aayna-burgundy" />
        <Card testid="dash-card-new_orders" icon={Clock} label="New" value={data.new_orders} accent="bg-amber-100 text-amber-700" to="/admin/orders?status=New" />
        <Card testid="dash-card-confirmed_orders" icon={CheckCircle2} label="Confirmed" value={data.confirmed_orders} accent="bg-indigo-100 text-indigo-700" to="/admin/orders?status=Confirmed" />
        <Card testid="dash-card-packed_orders" icon={PackageCheck} label="Packed" value={data.packed_orders ?? 0} accent="bg-sky-100 text-sky-700" to="/admin/orders?status=Packed" />
        <Card testid="dash-card-with_courier_orders" icon={Truck} label="With courier" value={data.with_courier_orders ?? 0} accent="bg-teal-100 text-teal-700" to="/admin/orders?status=Sent%20to%20Courier" />
        <Card testid="dash-card-delivered_orders" icon={CheckCircle2} label="Delivered" value={data.delivered_orders} accent="bg-green-100 text-green-700" to="/admin/orders?status=Delivered" />
        <Card testid="dash-card-cancelled_orders" icon={XCircle} label="Cancelled" value={data.cancelled_orders} accent="bg-red-100 text-red-600" to="/admin/orders?status=Cancelled" />
        <Card testid="dash-card-returned_orders" icon={Undo2} label="Returned" value={data.returned_orders ?? 0} accent="bg-gray-100 text-gray-600" to="/admin/orders?status=Returned" />
        <Card testid="dash-card-low_stock_count" icon={AlertTriangle} label="Low Stock" value={data.low_stock_count} accent="bg-orange-100 text-orange-700" to="/admin/inventory" />
        <Card testid="dash-card-failed_notifications" icon={BellOff} label="Failed Notifications" value={data.failed_notifications} accent="bg-gray-100 text-gray-600" />
      </div>

      <div className="grid sm:grid-cols-3 gap-4 mt-6">
        <div data-testid="dash-card-total_orders" className="bg-white border border-gray-200 rounded-lg p-5">
          <p className="text-sm text-gray-500">Total Orders</p>
          <p className="text-xl font-bold text-aayna-charcoal mt-1">{data.total_orders}</p>
        </div>
        <div data-testid="dash-card-total_products" className="bg-white border border-gray-200 rounded-lg p-5">
          <p className="text-sm text-gray-500">Total Products</p>
          <p className="text-xl font-bold text-aayna-charcoal mt-1">{data.total_products}</p>
        </div>
        <div data-testid="dash-card-total_customers" className="bg-white border border-gray-200 rounded-lg p-5">
          <p className="text-sm text-gray-500">Total Customers</p>
          <p className="text-xl font-bold text-aayna-charcoal mt-1">{data.total_customers}</p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <section data-testid="dash-low-stock" className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-aayna-charcoal mb-3">Low stock</h3>
          {(data.low_stock_items || []).length ? (
            <ul className="text-sm divide-y divide-gray-100">
              {data.low_stock_items.map((p) => (
                <li key={p.id} className="py-2 flex justify-between gap-3">
                  <span className="min-w-0"><span className="block truncate text-aayna-charcoal">{p.product_name}</span><span className="text-xs text-gray-400">{p.sku} · {p.status?.replace("_", " ")}</span></span>
                  <span className="font-semibold text-orange-700 whitespace-nowrap">{p.stock_quantity} left</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-400">No product is at or below its low-stock level.</p>}
        </section>
        <section data-testid="dash-recent-inventory" className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-aayna-charcoal mb-3">Recent stock activity</h3>
          {(data.recent_inventory || []).length ? (
            <ul className="text-sm divide-y divide-gray-100">
              {data.recent_inventory.map((l) => (
                <li key={l.id} className="py-2 flex justify-between gap-3">
                  <span className="min-w-0"><span className="block truncate text-aayna-charcoal">{l.product_name || l.product_id}</span>
                    <span className="text-xs text-gray-400 capitalize">{(l.change_type || "").replace("_", " ")} · {l.created_at ? new Date(l.created_at).toLocaleDateString() : ""}</span></span>
                  <span className={`font-semibold whitespace-nowrap ${l.quantity_change >= 0 ? "text-green-600" : "text-red-600"}`}>{l.quantity_change >= 0 ? "+" : ""}{l.quantity_change}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-400">No stock movements recorded yet.</p>}
        </section>
        <section data-testid="dash-recent-orders" className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-aayna-charcoal mb-3">Recent orders</h3>
          {(data.recent_orders || []).length ? (
            <ul className="text-sm divide-y divide-gray-100">
              {data.recent_orders.map((o) => (
                <li key={o.order_number} className="py-2 flex justify-between gap-3">
                  <span className="min-w-0"><span className="block truncate text-aayna-charcoal">{o.order_number}</span><span className="text-xs text-gray-400">{o.order_status} · {o.payment_status}</span></span>
                  <span className="font-semibold whitespace-nowrap">{formatBDT(o.total_amount)}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-400">No orders yet.</p>}
          <p className="text-xs text-gray-400 mt-3">Delivered sales to date: {formatBDT(data.delivered_sales_total || 0)} · Open (New to With courier): {data.pending_orders ?? 0}</p>
          {data.status_counts && Object.keys(data.status_counts.unknown || {}).length > 0 && (
            <p data-testid="dash-unknown-statuses" className="text-xs text-amber-700 mt-1">
              Unrecognised order statuses: {Object.entries(data.status_counts.unknown).map(([k, v]) => `${k} (${v})`).join(", ")}
            </p>
          )}
        </section>
      </div>

      <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <strong>Note:</strong> Order notifications are a placeholder in this version (no real email/SMS/WhatsApp sent). Failed notification counts are expected until the Make.com webhook is configured.
      </div>
    </div>
  );
}
