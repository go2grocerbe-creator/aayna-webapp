import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, Download, Loader2, Eye } from "lucide-react";
import { getCustomers, downloadCsv } from "@/admin/adminApi";

export default function Customers() {
  const [search, setSearch] = useState("");
  const { data: customers = [], isLoading } = useQuery({
    queryKey: ["admin-customers", search],
    queryFn: () => getCustomers(search ? { search } : {}),
  });

  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—");

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Customers</h1>
        <button onClick={() => downloadCsv("customers", "aayna_customers.csv")} className="h-10 px-3 border border-gray-300 rounded-md text-sm flex items-center gap-1.5 hover:bg-gray-50"><Download className="h-4 w-4" /> Export</button>
      </div>

      <div className="relative mb-4 max-w-sm">
        <Search className="h-4 w-4 absolute left-3 top-3 text-gray-400" />
        <input data-testid="customer-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, phone or email" className="w-full h-10 pl-9 pr-3 border border-gray-300 rounded-md text-sm outline-none focus:border-aayna-rose" />
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Phone</th>
                <th className="px-4 py-3 font-medium">District</th>
                <th className="px-4 py-3 font-medium">Orders</th>
                <th className="px-4 py-3 font-medium">Delivered</th>
                <th className="px-4 py-3 font-medium">Last Order</th>
                <th className="px-4 py-3 font-medium text-right">View</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-rose mx-auto" /></td></tr>
              ) : customers.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">No customers yet.</td></tr>
              ) : customers.map((c) => (
                <tr key={c.id} data-testid={`customer-row-${c.phone}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-aayna-charcoal">{c.full_name}</td>
                  <td className="px-4 py-3 text-gray-500">{c.phone}</td>
                  <td className="px-4 py-3 text-gray-500">{c.district}</td>
                  <td className="px-4 py-3">{c.total_orders}</td>
                  <td className="px-4 py-3 text-green-700">{c.successful_orders}</td>
                  <td className="px-4 py-3 text-gray-500">{fmtDate(c.last_order_date)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/admin/customers/${c.id}`} data-testid={`view-customer-${c.phone}`} className="p-2 inline-flex text-gray-500 hover:text-aayna-rose"><Eye className="h-4 w-4" /></Link>
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
