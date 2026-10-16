import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

// Plain-language reason for a failed admin request.
export function describeAdminError(error) {
  const status = error?.response?.status;
  const detail = typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "";
  if (!error?.response) {
    return { title: "The server could not be reached.", body: "Check your internet connection, or the API may be down. Try again in a moment.", status: null };
  }
  if (status === 401) return { title: "Your session has expired.", body: "Sign in again to continue.", status, signIn: true };
  if (status === 403) return { title: "You don't have permission to view this.", body: detail, status };
  if (status === 404) return { title: "Not found.", body: detail || "It may have been removed, or the link is wrong.", status };
  if (status >= 500) return { title: "The server hit an error.", body: detail || "Please try again. If it keeps happening, check the server logs.", status };
  return { title: "The request was refused.", body: detail, status };
}

// Shown when an admin request fails. Replaces endless spinners and misleading
// "No orders found." empty states with what actually went wrong.
export default function AdminLoadError({ error, onRetry, what = "this data", compact = false }) {
  const info = describeAdminError(error);
  return (
    <div
      role="alert"
      data-testid="admin-load-error"
      className={`flex flex-col items-center text-center gap-3 ${compact ? "py-8" : "py-20"}`}
    >
      <AlertTriangle className="h-6 w-6 text-amber-500" aria-hidden="true" />
      <p className="text-sm font-medium text-gray-800">Couldn't load {what}. {info.title}</p>
      {(info.body || info.status) && (
        <p className="text-xs text-gray-500 max-w-sm">
          {info.body}
          {info.status ? ` (HTTP ${info.status})` : ""}
        </p>
      )}
      {info.signIn && (
        <Link to="/admin/login" className="min-h-[44px] inline-flex items-center px-4 rounded-md bg-aayna-burgundy text-white text-sm font-medium">
          Sign in again
        </Link>
      )}
      {onRetry && !info.signIn && (
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
