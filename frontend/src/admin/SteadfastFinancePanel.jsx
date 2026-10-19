import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Wallet } from "lucide-react";
import { getCourierFinance, courierFinanceAction } from "@/admin/adminApi";
import { formatBDT } from "@/lib/format";

// STEADFAST FINANCIALS (super admin / admin only; the server enforces it).
// Unknown amounts are shown as pending, never as ৳0; estimates are labelled.
const STATUS = {
  NOT_AVAILABLE: ["Not enough information yet", "bg-gray-100 text-gray-700"],
  ESTIMATED: ["Estimated - not confirmed", "bg-amber-100 text-amber-900"],
  PROVIDER_CONFIRMED: ["Charges confirmed - payout not received", "bg-sky-100 text-sky-800"],
  SETTLED: ["Payout recorded", "bg-indigo-100 text-indigo-800"],
  RECONCILED: ["Reconciled", "bg-green-100 text-green-800"],
  DISPUTED: ["Disputed", "bg-red-100 text-red-700"],
};
const BASIS = { provider_confirmed: "from Steadfast", statement: "from statement", estimated: "estimate", not_applicable: "", not_available: "" };
const newKey = () => (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `k-${Date.now()}-${Math.random()}`);

function Money({ v, testid }) {
  if (!v || v.amount === null || v.amount === undefined) {
    return <span data-testid={testid} className="text-gray-400 italic">Pending provider confirmation</span>;
  }
  return (
    <span data-testid={testid}>
      {formatBDT(v.amount)}
      {BASIS[v.basis] ? <span className={`ml-1.5 text-[11px] ${v.basis === "estimated" ? "text-amber-800" : "text-gray-400"}`}>({BASIS[v.basis]})</span> : null}
    </span>
  );
}

function Row({ label, children, strong }) {
  return (
    <div className={`flex justify-between gap-3 py-1.5 text-sm ${strong ? "font-semibold" : ""}`}>
      <span className="text-gray-500">{label}</span>
      <span className="text-right text-aayna-charcoal">{children}</span>
    </div>
  );
}

export default function SteadfastFinancePanel({ orderNumber }) {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["admin-courier-finance", orderNumber], queryFn: () => getCourierFinance(orderNumber) });
  const [mode, setMode] = useState(null); // amounts | deduction | adjustment | payout | reconcile | dispute
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  if (isLoading) return <div className="bg-white border border-gray-200 rounded-lg p-5"><Loader2 className="h-5 w-5 animate-spin text-aayna-burgundy" /></div>;
  if (isError || !data) return null;
  const f = data.finance;
  const [label, cls] = STATUS[f.status] || STATUS.NOT_AVAILABLE;

  const submit = async () => {
    const num = (k) => (form[k] === undefined || form[k] === "" ? undefined : Number(form[k]));
    const body = { key: newKey(), source: form.source || "steadfast_statement", reference: form.reference || undefined, note: form.note || undefined };
    if (mode === "amounts") Object.assign(body, { action: "record_amounts", cod_collected: num("cod_collected"), delivery_fee: num("delivery_fee"), cod_fee: num("cod_fee"), return_fee: num("return_fee") });
    if (mode === "deduction") Object.assign(body, { action: "add_deduction", amount: num("amount"), label: form.label });
    if (mode === "adjustment") Object.assign(body, { action: "add_adjustment", amount: num("amount"), label: form.label });
    if (mode === "payout") Object.assign(body, { action: "record_payout", amount: num("amount"), paid_on: form.paid_on || undefined });
    if (mode === "reconcile") body.action = "reconcile";
    if (mode === "dispute") body.action = "dispute";
    setBusy(true);
    try {
      const r = await courierFinanceAction(orderNumber, body);
      toast.success(r.duplicate ? "Already recorded - nothing changed" : "Saved");
      setMode(null); setForm({});
      qc.invalidateQueries({ queryKey: ["admin-courier-finance", orderNumber] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save");
    } finally { setBusy(false); }
  };

  const input = "w-full h-11 border border-gray-300 rounded-md px-3 text-sm outline-none focus:border-aayna-burgundy";
  const fld = (k, lbl, type = "number") => (
    <label className="block text-xs text-gray-600">{lbl}
      <input data-testid={`fin-${k}`} type={type} step="0.01" inputMode={type === "number" ? "decimal" : undefined} className={`${input} mt-1`} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} />
    </label>
  );
  const actions = [["amounts", "Record charges / COD"], ["deduction", "Add deduction"], ["adjustment", "Add adjustment"], ["payout", "Record payout"], ["reconcile", "Reconcile"], ["dispute", "Flag dispute"]];

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5" data-testid="steadfast-finance">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold text-aayna-charcoal flex items-center gap-2"><Wallet className="h-4 w-4 text-gray-400" /> Steadfast financials</h2>
        <span data-testid="fin-status" className={`text-[11px] font-semibold px-2 py-1 rounded ${cls}`}>{label}</span>
      </div>
      <div className="border border-gray-100 rounded-md px-3 py-2">
        <Row label="Customer payable">{f.customer_payable.amount !== null ? formatBDT(f.customer_payable.amount) : f.customer_payable.problem}</Row>
        <Row label="COD requested">{f.cod_requested !== null ? formatBDT(f.cod_requested) : <span className="text-gray-400 italic">Not booked</span>}</Row>
        <Row label="COD collected"><Money v={f.cod_collected} testid="fin-cod-collected" /></Row>
        <Row label="Courier delivery fee"><Money v={f.fees.delivery_fee} testid="fin-delivery-fee" /></Row>
        <Row label="COD service fee"><Money v={f.fees.cod_fee} testid="fin-cod-fee" /></Row>
        <Row label="Return fee"><Money v={f.fees.return_fee} testid="fin-return-fee" /></Row>
        <Row label="Other deductions">{f.deductions_total ? `− ${formatBDT(f.deductions_total)}` : "None recorded"}</Row>
        {f.adjustments_total ? <Row label="Adjustments">{formatBDT(f.adjustments_total)}</Row> : null}
        <div className="border-t border-gray-100 mt-1 pt-1">
          <Row label="Expected settlement" strong><Money v={f.expected_settlement.amount === null ? null : { amount: f.expected_settlement.amount, basis: f.expected_settlement.basis === "estimate" ? "estimated" : "statement" }} testid="fin-expected" /></Row>
          <Row label="Actual settlement" strong>
            <span data-testid="fin-actual">{f.actual_settlement ? `${formatBDT(f.actual_settlement.amount)} · ${f.actual_settlement.reference}` : <span className="text-gray-400 italic font-normal">No payout recorded</span>}</span>
          </Row>
          {f.difference !== null && <Row label="Difference"><span data-testid="fin-difference" className={f.difference ? "text-red-700 font-semibold" : "text-green-700"}>{f.difference > 0 ? "+" : ""}{formatBDT(f.difference)}</span></Row>}
          <Row label="Last verified update">{f.updated_at ? `${new Date(f.updated_at).toLocaleString("en-GB")} · ${(f.last_verified_source || "").replace(/_/g, " ")}` : "-"}</Row>
        </div>
      </div>
      {f.flag_note && <p className="text-xs text-gray-600 mt-2">Note: {f.flag_note}</p>}
      <p className="text-xs text-gray-500 mt-2">Steadfast's fees are AAYNA's costs and never change what the customer pays. A delivered parcel is not a payout: record the payout only when Steadfast pays.</p>

      <div className="flex flex-wrap gap-2 mt-3">
        {actions.map(([m, l]) => (
          <button key={m} type="button" data-testid={`fin-open-${m}`} onClick={() => { setMode(mode === m ? null : m); setForm({}); }}
                  disabled={f.cod_requested === null}
                  className={`min-h-[44px] px-3 text-xs font-semibold rounded-md border disabled:opacity-50 ${mode === m ? "border-aayna-burgundy text-aayna-burgundy" : "border-gray-300 text-gray-700 hover:bg-gray-50"}`}>{l}</button>
        ))}
      </div>
      {mode && (
        <div className="mt-3 border border-gray-200 rounded-md p-3 space-y-3" data-testid="fin-form">
          <div className="grid grid-cols-2 gap-3">
            {mode === "amounts" && (<>{fld("cod_collected", "COD collected (৳)")}{fld("delivery_fee", "Delivery fee (৳)")}{fld("cod_fee", "COD fee (৳)")}{fld("return_fee", "Return fee (৳)")}</>)}
            {(mode === "deduction" || mode === "adjustment") && (<>{fld("amount", mode === "adjustment" ? "Amount (৳, minus for a reduction)" : "Amount (৳)")}{fld("label", "What it is", "text")}</>)}
            {mode === "payout" && (<>{fld("amount", "Amount Steadfast paid for this order (৳)")}{fld("paid_on", "Paid on", "date")}</>)}
          </div>
          {mode !== "reconcile" && mode !== "dispute" && (
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-gray-600">Source
                <select data-testid="fin-source" className={`${input} mt-1 bg-white`} value={form.source || "steadfast_statement"} onChange={(e) => set("source", e.target.value)}>
                  <option value="steadfast_statement">Steadfast statement</option>
                  <option value="steadfast_portal">Steadfast portal</option>
                  <option value="bank_statement">Bank / bKash statement</option>
                  <option value="other">Other</option>
                </select>
              </label>
              {fld("reference", mode === "payout" ? "Payment reference *" : "Reference", "text")}
            </div>
          )}
          <label className="block text-xs text-gray-600">{mode === "dispute" ? "What is wrong *" : "Note / reason (required when changing a recorded amount or reconciling a difference)"}
            <textarea data-testid="fin-note" rows={2} className={`${input} h-auto py-2 mt-1`} value={form.note || ""} onChange={(e) => set("note", e.target.value)} />
          </label>
          <button type="button" data-testid="fin-submit" disabled={busy} onClick={submit} className="min-h-[44px] px-4 bg-aayna-burgundy text-white rounded-md text-sm font-semibold disabled:opacity-60 inline-flex items-center gap-2">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}Save
          </button>
        </div>
      )}
      {data.events?.length > 0 && (
        <details className="mt-3" data-testid="fin-history">
          <summary className="text-sm text-gray-600 cursor-pointer min-h-[44px] flex items-center">Financial history ({data.events.length})</summary>
          <ul className="text-xs text-gray-600 space-y-1">
            {data.events.map((e) => (
              <li key={e.id} className="flex justify-between gap-3"><span>{e.action.replace(/_/g, " ")} · {e.actor}{e.reference ? ` · ${e.reference}` : ""}{e.note ? ` · ${e.note}` : ""}</span><span className="text-gray-400 whitespace-nowrap">{new Date(e.created_at).toLocaleString("en-GB")}</span></li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
