import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ShoppingCart, Clock, CheckCircle2, Truck, XCircle, TrendingUp, AlertTriangle, BellOff, Loader2,
} from "lucide-react";
import { getDashboard } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";

function Card({ icon: Icon, label, value, accent, to, testid }) {
  const inner = (
    <div className="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between">
        <span className={`h-10 w-10 rounded-md flex items-center justify-center ${accent}`}>
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
  const { data, isLoading } = useQuery({ queryKey: ["admin-dashboard"], queryFn: getDashboard });

  if (isLoading || !data) {
    return <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-aayna-rose" /></div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-1">Dashboard</h1>
      <p className="text-gray-500 mb-6">Overview of your store today.</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card testid="dash-card-todays_orders" icon={ShoppingCart} label="Today's Orders" value={data.todays_orders} accent="bg-blue-100 text-blue-700" to="/admin/orders" />
        <Card testid="dash-card-total_sales_today" icon={TrendingUp} label="Sales Today" value={formatBDT(data.total_sales_today)} accent="bg-aayna-mist text-aayna-rose" />
        <Card testid="dash-card-new_orders" icon={Clock} label="New / Pending" value={data.new_orders} accent="bg-amber-100 text-amber-700" to="/admin/orders" />
        <Card testid="dash-card-confirmed_orders" icon={CheckCircle2} label="Confirmed" value={data.confirmed_orders} accent="bg-indigo-100 text-indigo-700" to="/admin/orders" />
        <Card testid="dash-card-delivered_orders" icon={Truck} label="Delivered" value={data.delivered_orders} accent="bg-green-100 text-green-700" to="/admin/orders" />
        <Card testid="dash-card-cancelled_orders" icon={XCircle} label="Cancelled" value={data.cancelled_orders} accent="bg-red-100 text-red-600" to="/admin/orders" />
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

      <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <strong>Note:</strong> Order notifications are a placeholder in this version (no real email/SMS/WhatsApp sent). Failed notification counts are expected until the Make.com webhook is configured.
      </div>
    </div>
  );
}
