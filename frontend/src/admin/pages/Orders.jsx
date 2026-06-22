import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, Download, Loader2, Eye } from "lucide-react";
import { getAdminOrders, downloadCsv } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";
import { statusStyle, ORDER_STATUSES } from "@/admin/statusColors";

export default function Orders() {
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ["admin-orders", status, search],
    queryFn: () => getAdminOrders({ status, ...(search ? { search } : {}) }),
  });

  const fmtDate = (iso) => new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Orders</h1>
        <button onClick={() => downloadCsv("orders", "aayna_orders.csv")} className="h-10 px-3 border border-gray-300 rounded-md text-sm flex items-center gap-1.5 hover:bg-gray-50"><Download className="h-4 w-4" /> Export</button>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="h-4 w-4 absolute left-3 top-3 text-gray-400" />
          <input data-testid="order-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Order ID, name or phone" className="w-full h-10 pl-9 pr-3 border border-gray-300 rounded-md text-sm outline-none focus:border-aayna-rose" />
        </div>
        <select data-testid="order-status-filter" value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 px-3 border border-gray-300 rounded-md text-sm bg-white">
          <option value="all">All statuses</option>
          {ORDER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Order ID</th>
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">District</th>
                <th className="px-4 py-3 font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Payment</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium text-right">View</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr><td colSpan={8} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-rose mx-auto" /></td></tr>
              ) : orders.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-10 text-center text-gray-400">No orders found.</td></tr>
              ) : orders.map((o) => (
                <tr key={o.order_number} data-testid={`order-row-${o.order_number}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold text-aayna-charcoal">{o.order_number}</td>
                  <td className="px-4 py-3"><div className="text-aayna-charcoal">{o.customer_name}</div><div className="text-xs text-gray-400">{o.customer_phone}</div></td>
                  <td className="px-4 py-3 text-gray-500">{o.district}</td>
                  <td className="px-4 py-3 font-medium text-aayna-rose">{formatBDT(o.total_amount)}</td>
                  <td className="px-4 py-3 text-gray-500">{o.payment_method}</td>
                  <td className="px-4 py-3"><span className={`text-xs font-semibold px-2 py-1 rounded ${statusStyle(o.order_status)}`}>{o.order_status}</span></td>
                  <td className="px-4 py-3 text-gray-500">{fmtDate(o.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/admin/orders/${o.order_number}`} data-testid={`view-order-${o.order_number}`} className="p-2 inline-flex text-gray-500 hover:text-aayna-rose"><Eye className="h-4 w-4" /></Link>
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
