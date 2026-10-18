import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useCustomer } from "@/context/CustomerAuthContext";
import { login, resendVerification, confirmGoogleLink, googleStartUrl, apiError } from "@/lib/customerApi";
import { AuthShell, Field, PasswordField, SubmitButton, Notice, GoogleButton, OrDivider } from "@/components/account/ui";
import { useSeo } from "@/lib/seo";

const ERRORS = {
  google_failed: "We couldn't sign you in with Google. Please try again.",
  google_cancelled: "Google sign-in was cancelled.",
  google_unavailable: "Google sign-in isn't available yet. Please use your email and password.",
  google_email_unverified: "Your Google account's email address isn't verified, so we can't use it to sign in.",
  account_unavailable: "This account is not available. Please contact us for help.",
  signin_required: "Please sign in first.",
};

export function safeNext(value, fallback = "/account") {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return fallback;
  return value;
}

export default function Login() {
  useSeo({ title: "Sign in", description: "Sign in to your AAYNA account.", noindex: true });
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setAccount, config, signedIn, loading: sessionLoading } = useCustomer();
  const next = safeNext(params.get("next"));
  const linking = params.get("link") === "google";
  const [form, setForm] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState(params.get("error") ? { tone: "error", text: ERRORS[params.get("error")] || ERRORS.google_failed } : null);
  const [unverified, setUnverified] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionLoading && signedIn && !linking) navigate(next, { replace: true });
  }, [sessionLoading, signedIn, linking, next, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.email.trim()) errs.email = "Enter your email address.";
    if (!form.password) errs.password = "Enter your password.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    setStatus(null);
    setUnverified(false);
    try {
      const res = await login({ email: form.email.trim(), password: form.password });
      if (linking) {
        try {
          await confirmGoogleLink();
        } catch (err) {
          setAccount(res.account);
          setStatus({ tone: "error", text: apiError(err).message });
          setLoading(false);
          return;
        }
      }
      setAccount(res.account);
      navigate(linking ? "/account/security?google=linked" : next, { replace: true });
    } catch (err) {
      const e2 = apiError(err);
      if (e2.code === "email_unverified") setUnverified(true);
      setStatus({ tone: "error", text: e2.message });
      setLoading(false);
    }
  };

  const resend = async () => {
    try {
      const r = await resendVerification(form.email.trim());
      setStatus({ tone: "success", text: r.message });
      setUnverified(false);
    } catch (err) {
      setStatus({ tone: "error", text: apiError(err).message });
    }
  };

  return (
    <AuthShell testid="login-page" title="Sign in" intro={linking
      ? "This email already has an AAYNA account. Sign in with your password to link your Google account to it."
      : "Welcome back. Sign in to see your orders, saved addresses and rewards."}
      footer={<>New to AAYNA? <Link to={`/register${next !== "/account" ? `?next=${encodeURIComponent(next)}` : ""}`} className="text-aayna-burgundy font-medium underline-offset-2 hover:underline">Create an account</Link></>}>
      <div className="space-y-4">
        {status && <Notice tone={status.tone} testid="login-status">{status.text}
          {unverified && <button type="button" onClick={resend} data-testid="login-resend" className="block mt-2 font-semibold underline underline-offset-2">Send a new confirmation link</button>}
        </Notice>}
        {!linking && config.google_enabled && (<><GoogleButton href={googleStartUrl(next)} /><OrDivider /></>)}
        <form onSubmit={submit} noValidate className="space-y-4">
          <Field label="Email" type="email" name="email" autoComplete="username" inputMode="email" data-testid="login-email"
                 value={form.email} error={errors.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <PasswordField label="Password" name="password" autoComplete="current-password" data-testid="login-password"
                         value={form.password} error={errors.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <div className="flex justify-end -mt-1">
            <Link to="/forgot-password" className="text-sm text-aayna-burgundy underline-offset-2 hover:underline min-h-[44px] inline-flex items-center">Forgot password?</Link>
          </div>
          <SubmitButton loading={loading} data-testid="login-submit">{linking ? "Sign in and link Google" : "Sign in"}</SubmitButton>
        </form>
      </div>
    </AuthShell>
  );
}
