import { useId, useState } from "react";
import { Eye, EyeOff, Loader2, AlertCircle, CheckCircle2, Info } from "lucide-react";

// Shared, brand-consistent building blocks for the customer auth and account
// pages: labelled inputs with inline errors, password visibility toggle,
// accessible status notices and the "Continue with Google" button.

export function AuthShell({ eyebrow = "AAYNA", title, intro, children, footer, testid }) {
  return (
    <div data-testid={testid} className="max-w-md mx-auto px-4 sm:px-6 py-12 md:py-16">
      <div className="text-center mb-8">
        <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2">{eyebrow}</p>
        <h1 className="font-display font-semibold text-3xl md:text-4xl text-aayna-burgundy-dark">{title}</h1>
        {intro && <p className="text-aayna-taupe mt-3 text-sm leading-relaxed">{intro}</p>}
      </div>
      {children}
      {footer && <div className="mt-8 pt-6 border-t border-aayna-beige text-center text-sm text-aayna-taupe">{footer}</div>}
    </div>
  );
}

export const inputClass = (invalid) =>
  `w-full h-12 border bg-white px-4 text-[15px] text-aayna-charcoal outline-none focus:border-aayna-burgundy focus:ring-1 focus:ring-aayna-burgundy ${
    invalid ? "border-red-500" : "border-aayna-beige"
  }`;

export function Field({ label, error, hint, id, required, className = "", children, ...props }) {
  const auto = useId();
  const fid = id || auto;
  const describedBy = [error ? `${fid}-error` : null, hint ? `${fid}-hint` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={className}>
      <label htmlFor={fid} className="block text-sm font-medium text-aayna-charcoal mb-1.5">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children || (
        <input id={fid} aria-invalid={!!error} aria-describedby={describedBy} required={required} className={inputClass(error)} {...props} />
      )}
      {hint && !error && <p id={`${fid}-hint`} className="text-xs text-aayna-taupe mt-1">{hint}</p>}
      {error && <p id={`${fid}-error`} className="text-xs text-red-700 mt-1">{error}</p>}
    </div>
  );
}

export function PasswordField({ label = "Password", error, hint, id, ...props }) {
  const auto = useId();
  const fid = id || auto;
  const [show, setShow] = useState(false);
  const describedBy = [error ? `${fid}-error` : null, hint ? `${fid}-hint` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <label htmlFor={fid} className="block text-sm font-medium text-aayna-charcoal mb-1.5">{label}</label>
      <div className="relative">
        <input id={fid} type={show ? "text" : "password"} aria-invalid={!!error} aria-describedby={describedBy}
               className={`${inputClass(error)} pr-12`} {...props} />
        <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"}
                aria-pressed={show}
                className="absolute right-0 top-0 h-12 w-12 flex items-center justify-center text-aayna-taupe hover:text-aayna-burgundy focus-visible:outline focus-visible:outline-2 focus-visible:outline-aayna-burgundy">
          {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
      {hint && !error && <p id={`${fid}-hint`} className="text-xs text-aayna-taupe mt-1">{hint}</p>}
      {error && <p id={`${fid}-error`} className="text-xs text-red-700 mt-1">{error}</p>}
    </div>
  );
}

export function SubmitButton({ loading, children, className = "", variant = "primary", ...props }) {
  const styles = variant === "primary"
    ? "bg-aayna-coral text-white hover:bg-aayna-coral-dark active:bg-aayna-coral-pressed"
    : "border border-aayna-burgundy text-aayna-burgundy hover:bg-aayna-mist";
  return (
    <button type="submit" disabled={loading} aria-busy={loading}
            className={`w-full min-h-[48px] h-12 font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-60 ${styles} ${className}`}
            {...props}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Notice({ tone = "info", children, testid }) {
  const map = {
    info: ["border-aayna-beige bg-white text-aayna-charcoal", Info],
    error: ["border-red-200 bg-red-50 text-red-800", AlertCircle],
    success: ["border-emerald-200 bg-emerald-50 text-emerald-900", CheckCircle2],
  };
  const [cls, Icon] = map[tone] || map.info;
  return (
    <div data-testid={testid} role={tone === "error" ? "alert" : "status"} className={`flex gap-3 border p-4 text-sm leading-relaxed ${cls}`}>
      <Icon className="h-4 w-4 mt-0.5 flex-shrink-0" aria-hidden="true" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function GoogleButton({ href, label = "Continue with Google", disabled }) {
  if (disabled) return null;
  return (
    <a href={href} data-testid="google-signin"
       className="w-full min-h-[48px] h-12 border border-aayna-beige bg-white text-aayna-charcoal font-medium flex items-center justify-center gap-3 hover:border-aayna-burgundy transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-aayna-burgundy">
      <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden="true">
        <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.2l7.9 6.2C12.5 13.6 17.8 9.5 24 9.5z" />
        <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.4c-.5 2.8-2.1 5.2-4.5 6.8l7.3 5.7c4.3-4 6.9-9.9 6.9-16.5z" />
        <path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.2C1 16.6 0 20.2 0 24s1 7.4 2.7 10.8l7.9-6.2z" />
        <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.3-5.7c-2 1.4-4.7 2.3-8.6 2.3-6.2 0-11.5-4.1-13.4-9.8l-7.9 6.2C6.6 42.6 14.6 48 24 48z" />
      </svg>
      {label}
    </a>
  );
}

export function OrDivider() {
  return (
    <div className="flex items-center gap-3 my-6" aria-hidden="true">
      <span className="h-px flex-1 bg-aayna-beige" />
      <span className="text-xs uppercase tracking-[0.18em] text-aayna-taupe">or</span>
      <span className="h-px flex-1 bg-aayna-beige" />
    </div>
  );
}

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="py-16 flex justify-center" role="status" aria-live="polite">
      <Loader2 className="h-6 w-6 animate-spin text-aayna-burgundy" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
