import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import AdminLoadError from "@/admin/AdminLoadError";
import { getCourierFinanceList, importCourierPayouts } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";

// Courier money: order-level Steadfast settlement visibility (not accounting software).
const VIEWS = [["", "All booked"], ["awaiting", "Awaiting settlement"], ["settled", "Settled"], ["mismatch", "Mismatch"], ["exception", "Delivery exception"], ["return_pending", "Return pending"]];
const LABEL = { NOT_AVAILABLE: "Not enough info", ESTIMATED: "Estimated", PROVIDER_CONFIRMED: "Charges confirmed", SETTLED: "Payout recorded", RECONCILED: "Reconciled", DISPUTED: "Disputed" };

export default function CourierFinance() {
  const [view, setView] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: rows = [], isLoading, isError, error, refetch } = useQuery({ queryKey: ["courier-finance", view], queryFn: () => getCourierFinanceList(view) });
  const runImport = async () => {
    setBusy(true);
    try {
      const r = await importCourierPayouts();
      toast.success(`Imported ${r.applied.length} payout line(s)${r.unmatched.length ? `, ${r.unmatched.length} unmatched` : ""}${r.unreadable.length ? `, ${r.unreadable.length} unreadable (reconcile by hand)` : ""}`);
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Import failed");
    } finally { setBusy(false); }
  };
  const money = (v) => (v === null || v === undefined ? <span className="text-gray-400 italic">pending</span> : formatBDT(v));
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h1 className="text-2xl font-bold text-aayna-charcoal">Courier money</h1>
        <button data-testid="fin-import" onClick={runImport} disabled={busy} className="h-11 px-3 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-60 inline-flex items-center gap-2">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}Import Steadfast payouts
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-4">What Steadfast should pay AAYNA for each booked order, and what it actually paid. Estimates are labelled; a delivered parcel is not a payout.</p>
      <div className="flex flex-wrap gap-2 mb-4" role="tablist">
        {VIEWS.map(([v, l]) => (
          <button key={v || "all"} role="tab" aria-selected={view === v} data-testid={`fin-view-${v || "all"}`} onClick={() => setView(v)}
                  className={`min-h-[44px] px-3 text-xs font-semibold rounded-md border ${view === v ? "border-aayna-burgundy text-aayna-burgundy bg-aayna-mist/40" : "border-gray-300 text-gray-600"}`}>{l}</button>
        ))}
      </div>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr><th className="px-4 py-3 font-medium">Order</th><th className="px-4 py-3 font-medium">Courier status</th><th className="px-4 py-3 font-medium text-right">COD</th>
                <th className="px-4 py-3 font-medium text-right">Expected</th><th className="px-4 py-3 font-medium text-right">Actual</th><th className="px-4 py-3 font-medium text-right">Difference</th><th className="px-4 py-3 font-medium">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center"><Loader2 className="h-6 w-6 animate-spin text-aayna-burgundy mx-auto" /></td></tr>
              ) : isError ? (
                <tr><td colSpan={7}><AdminLoadError compact what="courier money" error={error} onRetry={refetch} /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">No orders in this view.</td></tr>
              ) : rows.map((r) => (
                <tr key={r.order_number} data-testid={`fin-row-${r.order_number}`}>
                  <td className="px-4 py-3"><Link className="font-semibold text-aayna-charcoal hover:text-aayna-burgundy" to={`/admin/orders/${r.order_number}`}>{r.order_number}</Link><div className="text-xs text-gray-400">{r.customer_name}</div></td>
                  <td className="px-4 py-3 text-gray-600">{(r.courier_status || "-").replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 text-right">{money(r.cod_requested)}</td>
                  <td className="px-4 py-3 text-right">{money(r.expected?.amount)}{r.expected?.basis === "estimate" && <span className="block text-[11px] text-amber-800">estimate</span>}</td>
                  <td className="px-4 py-3 text-right">{r.actual === null || r.actual === undefined ? <span className="text-gray-400 italic">none</span> : formatBDT(r.actual)}</td>
                  <td className={`px-4 py-3 text-right ${r.difference ? "text-red-700 font-semibold" : ""}`}>{r.difference === null || r.difference === undefined ? "-" : formatBDT(r.difference)}</td>
                  <td className="px-4 py-3 text-xs">{LABEL[r.status] || r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
