import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search, Loader2, Eye, ArrowLeft } from "lucide-react";
import AdminLoadError from "@/admin/AdminLoadError";
import { useAdminAuth } from "@/admin/AdminAuthContext";
import { getCustomerAccounts, getCustomerAccount, suspendCustomerAccount, reactivateCustomerAccount } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";

// Registered sign-in accounts. Guest checkout records stay under "Customers".
// Admins never see passwords, reset/verification tokens or session secrets,
// and cannot sign in as a customer.
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const STATUS = {
  active: "bg-green-100 text-green-700", pending_verification: "bg-amber-100 text-amber-800", suspended: "bg-red-100 text-red-700",
};

function Badge({ status }) {
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded whitespace-nowrap ${STATUS[status] || "bg-gray-100 text-gray-600"}`}>{(status || "").replace("_", " ")}</span>;
}

export default function CustomerAccounts() {
  const [search, setSearch] = useState("");
  const [method, setMethod] = useState("");
  const { data = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin-accounts", search, method],
    queryFn: () => getCustomerAccounts({ ...(search ? { search } : {}), ...(method ? { method } : {}) }),
  });
  return (
    <div data-testid="admin-accounts">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Customer Accounts</h1>
        <p className="text-sm text-gray-500 mt-1">People who created a sign-in. Guest checkout records are listed under Customers.</p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative sm:max-w-sm flex-1">
          <Search className="h-4 w-4 absolute left-3 top-3.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email or phone" data-testid="accounts-search"
                 className="w-full h-11 pl-9 pr-3 border border-gray-300 rounded-md text-sm outline-none focus:border-aayna-burgundy" />
        </div>
        <select value={method} onChange={(e) => setMethod(e.target.value)} data-testid="accounts-method" aria-label="Sign-in method"
                className="h-11 px-3 border border-gray-300 rounded-md text-sm bg-white">
          <option value="">All sign-in methods</option>
          <option value="password">Email and password</option>
          <option value="google">Google</option>
        </select>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th><th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Sign-in</th><th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Orders</th><th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium text-right">View</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-burgundy mx-auto" /></td></tr>
              ) : isError ? (
                <tr><td colSpan={7}><AdminLoadError compact what="customer accounts" error={error} onRetry={refetch} /></td></tr>
              ) : data.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400" data-testid="accounts-empty">No customer accounts yet.</td></tr>
              ) : data.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50" data-testid="account-row">
                  <td className="px-4 py-3 font-medium text-aayna-charcoal">{a.full_name}{a.deletion_requested_at && <span className="ml-2 text-xs text-red-600">deletion requested</span>}</td>
                  <td className="px-4 py-3 text-gray-500">{a.email} {a.email_verified ? <span className="text-green-700 text-xs">✓</span> : <span className="text-amber-700 text-xs">unverified</span>}</td>
                  <td className="px-4 py-3 text-gray-500">{a.login_methods.join(", ")}</td>
                  <td className="px-4 py-3"><Badge status={a.status} /></td>
                  <td className="px-4 py-3">{a.orders}</td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmt(a.created_at)}</td>
                  <td className="px-4 py-3 text-right"><Link to={`/admin/accounts/${a.id}`} aria-label={`View ${a.full_name}`} className="p-2 inline-flex text-gray-500 hover:text-aayna-burgundy"><Eye className="h-4 w-4" /></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function CustomerAccountDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { can } = useAdminAuth();
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["admin-account", id], queryFn: () => getCustomerAccount(id) });
  if (isLoading) return <div className="py-16 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-burgundy" /></div>;
  if (isError) return <AdminLoadError what="this account" error={error} onRetry={refetch} />;
  const a = data.account;
  const act = async (fn, msg) => {
    try { await fn(); toast.success(msg); qc.invalidateQueries({ queryKey: ["admin-account", id] }); qc.invalidateQueries({ queryKey: ["admin-accounts"] }); }
    catch (err) { toast.error(err?.response?.data?.detail || "Action failed"); }
  };
  return (
    <div data-testid="admin-account-detail">
      <Link to="/admin/accounts" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-aayna-burgundy min-h-[44px]"><ArrowLeft className="h-4 w-4" />Accounts</Link>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-aayna-charcoal">{a.full_name}</h1>
          <p className="text-sm text-gray-500">{a.email} · {a.phone || "no phone"}</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge status={a.status} />
          {can("customers.manage") && (a.status === "suspended" ? (
            <button type="button" onClick={() => act(() => reactivateCustomerAccount(id), "Account reactivated")} className="h-11 px-4 border border-gray-300 rounded-md text-sm">Reactivate</button>
          ) : (
            <button type="button" data-testid="account-suspend" onClick={() => {
              const reason = window.prompt("Reason for suspending this account (recorded):");
              if (reason !== null) act(() => suspendCustomerAccount(id, reason), "Account suspended and signed out");
            }} className="h-11 px-4 border border-red-300 text-red-700 rounded-md text-sm">Suspend sign-in</button>
          ))}
        </div>
      </div>
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-5 text-sm space-y-2">
          <h2 className="font-semibold text-aayna-charcoal mb-2">Account</h2>
          <p><span className="text-gray-500">Email verified:</span> {a.email_verified ? `Yes (${fmt(a.verified_at)})` : "No"}</p>
          <p><span className="text-gray-500">Created:</span> {fmt(a.created_at)} via {a.created_via}</p>
          <p><span className="text-gray-500">Last sign-in:</span> {fmt(a.last_login_at)}</p>
          <p><span className="text-gray-500">Sign-in methods:</span> {data.login_methods.map((m) => m.provider).join(", ") || "—"}</p>
          <p><span className="text-gray-500">Active sessions:</span> {data.active_sessions}</p>
          <p><span className="text-gray-500">Saved addresses:</span> {data.addresses}</p>
          {a.deletion_requested_at && <p className="text-red-700">Deletion requested {fmt(a.deletion_requested_at)}</p>}
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-5 lg:col-span-2">
          <h2 className="font-semibold text-aayna-charcoal mb-3">Orders</h2>
          {data.orders.length === 0 ? <p className="text-sm text-gray-400">No orders linked to this account.</p> : (
            <ul className="divide-y divide-gray-100 text-sm">
              {data.orders.map((o) => (
                <li key={o.order_number} className="py-2 flex justify-between gap-3">
                  <Link to={`/admin/orders/${o.order_number}`} className="text-aayna-burgundy font-medium">{o.order_number}</Link>
                  <span className="text-gray-500">{o.order_status}{o.coupon_code ? ` · ${o.coupon_code}` : ""}</span>
                  <span>{formatBDT(o.total_amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-5 lg:col-span-2">
          <h2 className="font-semibold text-aayna-charcoal mb-3">Security events</h2>
          <ul className="space-y-1.5 text-sm">
            {data.security_events.map((e) => (
              <li key={e.id} className="flex justify-between gap-3"><span>{e.type.replace(/_/g, " ")}{e.detail ? <span className="text-gray-400"> · {e.detail}</span> : null}</span><span className="text-gray-500 text-xs whitespace-nowrap">{fmt(e.created_at)}</span></li>
            ))}
          </ul>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="font-semibold text-aayna-charcoal mb-3">Emails</h2>
          {data.emails.length === 0 ? <p className="text-sm text-gray-400">No emails sent.</p> : (
            <ul className="space-y-1.5 text-sm">
              {data.emails.map((m) => (
                <li key={m.id} className="flex justify-between gap-3"><span>{m.template.replace(/_/g, " ")}</span>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded ${m.status === "sent" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>{m.status.replace("_", " ")}</span></li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
