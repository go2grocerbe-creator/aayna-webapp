import { Check, XCircle, RotateCcw } from "lucide-react";

const fmt = (iso) => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "Asia/Dhaka" });
  } catch {
    return null;
  }
};

// Renders the backend's timeline exactly: a step shows a time only when that
// transition was actually recorded. Older orders (before history was kept)
// show their current status without invented dates.
export default function OrderTimeline({ timeline, testid = "order-timeline" }) {
  if (!timeline) return null;
  const { steps, exception } = timeline;
  return (
    <div data-testid={testid}>
      {exception && (
        <div className="flex items-center gap-2 mb-4 text-sm text-red-800 border border-red-200 bg-red-50 px-3 py-2" role="status">
          {exception.status === "Returned" ? <RotateCcw className="h-4 w-4" aria-hidden="true" /> : <XCircle className="h-4 w-4" aria-hidden="true" />}
          <span>This order was {exception.label.toLowerCase()}{exception.at ? ` on ${fmt(exception.at)}` : ""}.</span>
        </div>
      )}
      <ol className="relative">
        {steps.map((s, i) => {
          const done = s.done && !exception;
          return (
            <li key={s.status} className="flex gap-3 pb-5 last:pb-0 relative" aria-current={s.current && !exception ? "step" : undefined}>
              {i < steps.length - 1 && (
                <span aria-hidden="true" className={`absolute left-[11px] top-6 bottom-0 w-px ${steps[i + 1].done && !exception ? "bg-aayna-burgundy" : "bg-aayna-beige"}`} />
              )}
              <span aria-hidden="true" className={`relative z-10 h-6 w-6 flex-shrink-0 rounded-full flex items-center justify-center border ${
                done ? "bg-aayna-burgundy border-aayna-burgundy text-white" : "bg-white border-aayna-beige"}`}>
                {done && <Check className="h-3.5 w-3.5" />}
              </span>
              <div className="min-w-0 pt-0.5">
                <p className={`text-sm ${s.current && !exception ? "font-semibold text-aayna-burgundy" : done ? "text-aayna-charcoal" : "text-aayna-taupe"}`}>
                  {s.label}
                  <span className="sr-only">{done ? " - completed" : " - not yet"}</span>
                </p>
                {done && s.at && <p className="text-xs text-aayna-taupe mt-0.5">{fmt(s.at)}</p>}
              </div>
            </li>
          );
        })}
      </ol>
      {!timeline.history_complete && (
        <p className="text-xs text-aayna-taupe mt-4">Detailed step times are shown for updates recorded from now on.</p>
      )}
    </div>
  );
}

export { fmt as formatDhakaDateTime };
