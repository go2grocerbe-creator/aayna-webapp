import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Truck, AlertTriangle, RefreshCw, CheckCircle2 } from "lucide-react";
import { getCourierView, courierAction } from "@/admin/adminApi";
import { useAdminAuth } from "@/admin/AdminAuthContext";
import { formatBDT } from "@/lib/format";

// Steadfast delivery panel on Admin -> Orders -> order. Every action is explicit;
// the server decides eligibility, the COD amount and duplicate protection.
const KIND_STYLE = {
  booked: "bg-sky-50 text-sky-800 border-sky-200",
  confirming: "bg-indigo-50 text-indigo-800 border-indigo-200",
  delivered: "bg-green-50 text-green-800 border-green-200",
  attention: "bg-amber-50 text-amber-900 border-amber-200",
  return: "bg-amber-50 text-amber-900 border-amber-200",
  return_received: "bg-amber-50 text-amber-900 border-amber-200",
};
const SIM_STATUSES = ["in_review", "pending", "hold", "delivered_approval_pending", "delivered", "partial_delivered",
  "cancelled", "exceptional", "unknown"];
const SIM_FAULTS = [["timeout_after_accept", "Timeout after Steadfast accepts"], ["timeout_before_accept", "Timeout before acceptance"],
  ["validation", "Validation error"], ["server_error", "Steadfast server error"], ["down", "Steadfast unreachable"], ["auth", "Wrong API keys"]];

const when = (iso) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "-");

function Row({ label, children, testid }) {
  return (
    <div className="flex justify-between gap-3 py-1.5 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-right text-aayna-charcoal break-all" data-testid={testid}>{children}</span>
    </div>
  );
}

export default function SteadfastPanel({ orderNumber }) {
  const qc = useQueryClient();
  const { can } = useAdminAuth();
  const canBook = can("courier.book");
  const canSync = can("orders.edit");
  const { data, isLoading, isError } = useQuery({ queryKey: ["admin-courier", orderNumber], queryFn: () => getCourierView(orderNumber) });
  const [busy, setBusy] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [link, setLink] = useState({ consignment_id: "", tracking_code: "" });
  const [sim, setSim] = useState({ status: "pending", fault: "timeout_after_accept" });

  const run = async (action, body, okMsg) => {
    setBusy(action);
    try {
      const r = await courierAction(orderNumber, action, body);
      if (r?.note) toast.message(r.note);
      else if (okMsg) toast.success(okMsg);
      setConfirming(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Steadfast action failed");
    } finally {
      setBusy(null);
      qc.invalidateQueries({ queryKey: ["admin-courier", orderNumber] });
      qc.invalidateQueries({ queryKey: ["admin-order", orderNumber] });
      qc.invalidateQueries({ queryKey: ["admin-orders"] });
    }
  };

  if (isLoading) return <div className="bg-white border border-gray-200 rounded-lg p-5"><Loader2 className="h-5 w-5 animate-spin text-aayna-burgundy" /></div>;
  if (isError || !data) return <div className="bg-white border border-gray-200 rounded-lg p-5 text-sm text-gray-500">Steadfast details could not be loaded.</div>;

  const { config, courier: c, booking_preview: bp, simulated_portal: portal } = data;
  const state = c?.state || "none";
  const mock = config.mode === "mock";
  const off = config.mode === "off";
  const liveBlocked = config.mode === "live" && !config.real_bookings;
  const Btn = ({ action, children, body, okMsg, primary, disabled, testid }) => (
    <button type="button" data-testid={testid} disabled={!!busy || disabled} onClick={() => run(action, body, okMsg)}
            className={`min-h-[44px] px-4 rounded-md text-sm font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-50 ${
              primary ? "bg-aayna-burgundy text-white hover:bg-aayna-burgundy-dark" : "border border-gray-300 text-aayna-charcoal hover:bg-gray-50"}`}>
      {busy === action && <Loader2 className="h-4 w-4 animate-spin" />}{children}
    </button>
  );

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5" data-testid="steadfast-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold text-aayna-charcoal flex items-center gap-2"><Truck className="h-4 w-4 text-gray-400" /> Steadfast delivery</h2>
        <span data-testid="steadfast-mode" className={`text-[11px] font-semibold px-2 py-1 rounded ${mock ? "bg-violet-100 text-violet-800" : off ? "bg-gray-100 text-gray-600" : "bg-green-100 text-green-800"}`}>
          {mock ? "Test simulator - no real parcels" : off ? "Not connected" : liveBlocked ? "Live - status only" : "Live"}
        </span>
      </div>

      {off && <p className="text-sm text-gray-500" data-testid="steadfast-off">{config.reason || "Steadfast is not configured."} Courier details can still be entered by hand below.</p>}

      {!off && (state === "none" || state === "failed") && (
        <div className="space-y-3">
          {state === "failed" && c?.last_error && (
            <p data-testid="steadfast-error" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{c.last_error}</p>
          )}
          <div className="border border-gray-100 rounded-md px-3 py-2" data-testid="steadfast-preview">
            <Row label="Invoice">{bp.invoice}</Row>
            <Row label="Recipient">{bp.recipient_name || "-"}</Row>
            <Row label="Phone">{bp.recipient_phone || "-"}</Row>
            <Row label="Address">{bp.recipient_address || "-"}</Row>
            {bp.note && <Row label="Note">{bp.note}</Row>}
            <Row label="Cash to collect (COD)" testid="steadfast-cod">{bp.cod?.ok ? formatBDT(bp.cod.amount) : "-"}</Row>
            {bp.cod?.ok && (
              <p className="text-xs text-gray-500 pb-1">
                Products {formatBDT(bp.cod.breakdown.subtotal)}{bp.cod.breakdown.discount ? ` − discount ${formatBDT(bp.cod.breakdown.discount)}` : ""} + delivery {formatBDT(bp.cod.breakdown.delivery)}
                {bp.cod.breakdown.prepaid ? ` − prepaid ${formatBDT(bp.cod.breakdown.prepaid)}` : ""}. Steadfast's own charge is billed to AAYNA separately.
              </p>
            )}
          </div>
          {bp.problems?.length > 0 && (
            <ul data-testid="steadfast-problems" className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 space-y-1 list-disc pl-5">
              {bp.problems.map((p) => <li key={p}>{p}</li>)}
            </ul>
          )}
          {liveBlocked && <p className="text-xs text-gray-500">{config.reason}</p>}
          {canBook && !liveBlocked && (confirming ? (
            <div className="border border-aayna-burgundy/30 bg-aayna-mist/30 rounded-md p-3 space-y-2" data-testid="steadfast-confirm">
              <p className="text-sm text-aayna-charcoal">
                Book this parcel with Steadfast, collecting <strong>{formatBDT(bp.cod?.amount)}</strong> on delivery?
                {mock ? " (Simulator: nothing is sent to Steadfast.)" : " This creates a real consignment."}
              </p>
              <div className="flex flex-wrap gap-2">
                <Btn action="book" body={{ confirm: true }} okMsg="Booked with Steadfast" primary testid="steadfast-confirm-book">Confirm booking</Btn>
                <button type="button" onClick={() => setConfirming(false)} className="min-h-[44px] px-4 text-sm text-gray-600">Cancel</button>
              </div>
            </div>
          ) : (
            <button type="button" data-testid="steadfast-book" disabled={!bp.ok || !!busy} onClick={() => setConfirming(true)}
                    className="w-full min-h-[44px] bg-aayna-burgundy text-white rounded-md text-sm font-semibold disabled:opacity-50 hover:bg-aayna-burgundy-dark">
              {state === "failed" ? "Retry booking with Steadfast" : "Book with Steadfast"}
            </button>
          ))}
        </div>
      )}

      {!off && state === "booking" && (
        <div className="space-y-2">
          <p className="text-sm text-gray-600" data-testid="steadfast-booking">Booking in progress since {when(c.claimed_at)}. If this does not change within two minutes, check Steadfast by invoice.</p>
          {canBook && <Btn action="reconcile" okMsg="Checked with Steadfast" testid="steadfast-reconcile">Check Steadfast by invoice</Btn>}
        </div>
      )}

      {!off && state === "needs_reconciliation" && (
        <div className="space-y-3">
          <p data-testid="steadfast-reconcile-note" className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 flex gap-2">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" /><span>{c.last_error || "The booking result is unknown. Check before doing anything else."}</span>
          </p>
          {canBook && <Btn action="reconcile" okMsg="Checked with Steadfast" testid="steadfast-reconcile">Check Steadfast by invoice ({c.invoice})</Btn>}
          {canBook && c.found_at_provider && (
            <div className="space-y-2" data-testid="steadfast-link-form">
              <p className="text-xs text-gray-500">Copy the parcel's details from the Steadfast portal (search invoice {c.invoice}):</p>
              {portal && (
                <p className="text-xs text-violet-800 bg-violet-50 rounded px-2 py-1" data-testid="steadfast-sim-portal">
                  Simulator - the portal would show consignment {portal.consignment_id}, tracking {portal.tracking_code}
                </p>
              )}
              <input aria-label="Consignment ID" placeholder="Consignment ID" inputMode="numeric" value={link.consignment_id}
                     onChange={(e) => setLink((l) => ({ ...l, consignment_id: e.target.value }))} data-testid="steadfast-link-cid"
                     className="w-full h-11 border border-gray-300 rounded-md px-3 text-sm outline-none focus:border-aayna-burgundy" />
              <input aria-label="Tracking code" placeholder="Tracking code" value={link.tracking_code}
                     onChange={(e) => setLink((l) => ({ ...l, tracking_code: e.target.value }))} data-testid="steadfast-link-code"
                     className="w-full h-11 border border-gray-300 rounded-md px-3 text-sm outline-none focus:border-aayna-burgundy" />
              <Btn action="link" body={link} okMsg="Parcel linked" disabled={!link.consignment_id || !link.tracking_code} testid="steadfast-link">Link this parcel</Btn>
            </div>
          )}
        </div>
      )}

      {!off && state === "booked" && (
        <div className="space-y-3">
          <div className="border border-gray-100 rounded-md px-3 py-2">
            <Row label="Consignment ID" testid="steadfast-cid">{c.consignment_id}</Row>
            <Row label="Tracking code" testid="steadfast-tracking">{c.tracking_code}</Row>
            <Row label="COD to collect" testid="steadfast-booked-cod">{formatBDT(c.cod_amount)}</Row>
            <Row label="Booked">{when(c.booked_at)}{c.linked_by_hand ? " (linked by hand)" : ""}</Row>
            <Row label="Last checked">{when(c.last_sync_at)}</Row>
          </div>
          <p data-testid="steadfast-status" className={`text-sm border rounded-md px-3 py-2 flex gap-2 ${KIND_STYLE[c.status_kind] || "bg-gray-50 border-gray-200 text-gray-700"}`}>
            {c.status_kind === "delivered" ? <CheckCircle2 className="h-4 w-4 flex-shrink-0 mt-0.5" /> : <Truck className="h-4 w-4 flex-shrink-0 mt-0.5" />}
            <span>{c.status_label || "No status yet"}</span>
          </p>
          {c.attention && (
            <p data-testid="steadfast-attention" className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 flex gap-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" /><span>{c.attention}</span>
            </p>
          )}
          {canSync && <Btn action="sync" okMsg="Status checked" testid="steadfast-sync"><RefreshCw className="h-4 w-4" />Check delivery status</Btn>}
          <p className="text-xs text-gray-500">Booking is not dispatch: set the order to “Sent to Courier” when the parcel is handed over. A confirmed delivery moves the order to Delivered automatically. Returns: arrange them in the Steadfast portal for now and restock only after inspecting the parcel.</p>
        </div>
      )}

      {c?.history?.length > 0 && (
        <details className="mt-4" data-testid="steadfast-history">
          <summary className="text-sm font-medium text-aayna-charcoal cursor-pointer min-h-[44px] flex items-center">Shipment history ({c.history.length})</summary>
          <ul className="mt-1 space-y-1 text-xs text-gray-600">
            {[...c.history].reverse().map((h, i) => (
              <li key={i} className="flex justify-between gap-3"><span>{h.event.replace(/_/g, " ")}{h.status ? ` · ${h.status}` : ""}{h.by ? ` · ${h.by}` : ""}</span><span className="text-gray-400 whitespace-nowrap">{when(h.at)}</span></li>
            ))}
          </ul>
        </details>
      )}

      {mock && canBook && (
        <details className="mt-4 border-t border-dashed border-gray-200 pt-3" data-testid="steadfast-simulator">
          <summary className="text-xs font-semibold text-violet-800 cursor-pointer min-h-[44px] flex items-center">Simulator controls (test preview only)</summary>
          <div className="grid sm:grid-cols-2 gap-2 mt-2">
            <select aria-label="Simulated Steadfast status" value={sim.status} onChange={(e) => setSim((s) => ({ ...s, status: e.target.value }))}
                    className="h-11 border border-gray-300 rounded-md px-2 text-sm bg-white" data-testid="sim-status">
              {SIM_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <Btn action="mock" body={{ action: "set_status", status: sim.status }} okMsg="Simulated status set - now check delivery status" disabled={state !== "booked"} testid="sim-set-status">Set parcel status</Btn>
            <select aria-label="Simulated failure" value={sim.fault} onChange={(e) => setSim((s) => ({ ...s, fault: e.target.value }))}
                    className="h-11 border border-gray-300 rounded-md px-2 text-sm bg-white" data-testid="sim-fault">
              {SIM_FAULTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <Btn action="mock" body={{ action: "fail_next", fault: sim.fault, op: "create_order" }} okMsg="The next booking will fail that way" testid="sim-fail-next">Fail the next booking</Btn>
          </div>
        </details>
      )}
    </div>
  );
}
