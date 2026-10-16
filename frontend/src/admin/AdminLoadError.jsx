import { AlertTriangle } from "lucide-react";

// Shown when an admin request fails (server error, network, expired session).
// Replaces endless spinners and misleading "No orders found." empty states.
export default function AdminLoadError({ error, onRetry, what = "this data", compact = false }) {
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;
  return (
    <div
      role="alert"
      data-testid="admin-load-error"
      className={`flex flex-col items-center text-center gap-3 ${compact ? "py-8" : "py-20"}`}
    >
      <AlertTriangle className="h-6 w-6 text-amber-500" aria-hidden="true" />
      <p className="text-sm font-medium text-gray-800">Couldn't load {what}.</p>
      <p className="text-xs text-gray-500 max-w-sm">
        {status ? `The server responded with an error (${status})` : "The server could not be reached"}
        {typeof detail === "string" ? `: ${detail}` : "."} Nothing has been changed.
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={() => onRetry()}
          className="min-h-[44px] px-4 rounded-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Try again
        </button>
      )}
    </div>
  );
}
