import { Link } from "react-router-dom";

// True only when the API actually answered 404. Network failures, timeouts and
// 5xx responses are NOT "not found" - they must not tell a customer that a real
// product or category doesn't exist.
export const isNotFoundError = (error) => error?.response?.status === 404;

// Shown when the store API could not be reached or returned a server error.
export default function LoadError({ onRetry, what = "this page" }) {
  return (
    <div data-testid="load-error" role="alert" className="max-w-7xl mx-auto px-4 py-20 text-center">
      <p className="text-aayna-charcoal text-lg mb-2">We couldn't load {what} right now.</p>
      <p className="text-aayna-taupe text-sm mb-6">
        This is a connection problem on our side, not your order or cart. Please try again in a moment.
      </p>
      <div className="flex items-center justify-center gap-6">
        {onRetry && (
          <button
            type="button"
            data-testid="load-error-retry"
            onClick={() => onRetry()}
            className="min-h-[44px] px-5 bg-aayna-burgundy text-aayna-cream text-sm font-semibold"
          >
            Try again
          </button>
        )}
        <Link to="/" className="min-h-[44px] inline-flex items-center text-aayna-burgundy underline underline-offset-2 text-sm">
          Back to home
        </Link>
      </div>
    </div>
  );
}
