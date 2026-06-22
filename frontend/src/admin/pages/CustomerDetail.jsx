import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Phone, Mail, MapPin } from "lucide-react";
import { getCustomer } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";
import { statusStyle } from "@/admin/statusColors";

export default function CustomerDetail() {
  const { id } = useParams();
  const { data: customer, isLoading } = useQuery({ queryKey: ["admin-customer", id], queryFn: () => getCustomer(id) });

  if (isLoading || !customer) {
    return <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-aayna-rose" /></div>;
  }

  return (
    <div className="max-w-4xl">
      <Link to="/admin/customers" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-aayna-rose mb-4"><ArrowLeft className="h-4 w-4" /> Back to customers</Link>
      <h1 className="text-2xl font-bold text-aayna-charcoal mb-1">{customer.full_name}</h1>

      <div className="grid md:grid-cols-3 gap-6 mt-5">
        <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-2 text-sm">
          <p className="flex items-center gap-2 text-gray-600"><Phone className="h-4 w-4 text-gray-400" /> {customer.phone}</p>
          {customer.email && <p className="flex items-center gap-2 text-gray-600"><Mail className="h-4 w-4 text-gray-400" /> {customer.email}</p>}
          <p className="flex items-start gap-2 text-gray-600"><MapPin className="h-4 w-4 text-gray-400 mt-0.5" /> {customer.default_address}, {customer.district}</p>
          <div className="border-t border-gray-100 pt-3 mt-3 grid grid-cols-3 gap-2 text-center">
            <div><p className="text-lg font-bold text-aayna-charcoal">{customer.total_orders}</p><p className="text-xs text-gray-400">Total</p></div>
            <div><p className="text-lg font-bold text-green-700">{customer.successful_orders}</p><p className="text-xs text-gray-400">Delivered</p></div>
            <div><p className="text-lg font-bold text-red-600">{customer.cancelled_orders}</p><p className="text-xs text-gray-400">Cancelled</p></div>
          </div>
        </div>

        <div className="md:col-span-2 bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="font-semibold text-aayna-charcoal mb-3">Order History</h2>
          {customer.orders?.length ? (
            <div className="divide-y divide-gray-100">
              {customer.orders.map((o) => (
                <Link key={o.order_number} to={`/admin/orders/${o.order_number}`} className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-2 px-2 rounded">
                  <div>
                    <span className="font-medium text-aayna-charcoal">{o.order_number}</span>
                    <span className="text-xs text-gray-400 ml-2">{new Date(o.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-aayna-rose font-medium">{formatBDT(o.total_amount)}</span>
                    <span className={`text-xs font-semibold px-2 py-1 rounded ${statusStyle(o.order_status)}`}>{o.order_status}</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : <p className="text-sm text-gray-400">No orders yet.</p>}
        </div>
      </div>
    </div>
  );
}
