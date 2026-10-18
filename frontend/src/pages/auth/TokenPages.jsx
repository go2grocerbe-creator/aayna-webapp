import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCustomer } from "@/context/CustomerAuthContext";
import {
  verifyEmail, resendVerification, forgotPassword, resetPassword, confirmEmailChange, confirmOrderClaim,
  takeFragmentToken, apiError,
} from "@/lib/customerApi";
import { AuthShell, Field, PasswordField, SubmitButton, Notice, Spinner } from "@/components/account/ui";
import { useSeo } from "@/lib/seo";

// Links in AAYNA emails carry their one-time token in the URL fragment
// (#token=...). Fragments never reach servers, logs or Referer headers; each
// page reads it once and immediately removes it from the address bar.
function useFragmentToken() {
  const ref = useRef(undefined);
  if (ref.current === undefined) ref.current = takeFragmentToken();
  return ref.current;
}

function ResendForm({ initialEmail = "" }) {
  const [email, setEmail] = useState(initialEmail);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      setStatus({ tone: "success", text: (await resendVerification(email.trim())).message });
    } catch (err) {
      setStatus({ tone: "error", text: apiError(err).message });
    } finally {
      setLoading(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-4 mt-6" noValidate>
      {status && <Notice tone={status.tone} testid="resend-status">{status.text}</Notice>}
      <Field label="Email" type="email" autoComplete="email" value={email} data-testid="resend-email" onChange={(e) => setEmail(e.target.value)} />
      <SubmitButton loading={loading} variant="secondary" data-testid="resend-submit">Send a new confirmation link</SubmitButton>
    </form>
  );
}

export function VerifyEmail() {
  useSeo({ title: "Confirm your email", description: "Confirm your AAYNA account.", noindex: true });
  const token = useFragmentToken();
  const { setAccount } = useCustomer();
  const [state, setState] = useState(token ? "working" : "no_token");
  const [message, setMessage] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;
    verifyEmail(token)
      .then((r) => { setAccount(r.account); setState("done"); })
      .catch((err) => { const e = apiError(err); setMessage(e.message); setState(e.code || "invalid"); });
  }, [token, setAccount]);

  if (state === "working") return <AuthShell testid="verify-working" title="Confirming…"><Spinner label="Confirming your email" /></AuthShell>;
  if (state === "done") {
    return (
      <AuthShell testid="verify-success" title="Email confirmed" intro="Your AAYNA account is active and you're signed in.">
        <div className="space-y-3">
          <Link to="/account" data-testid="verify-continue" className="w-full min-h-[48px] bg-aayna-coral text-white font-semibold flex items-center justify-center hover:bg-aayna-coral-dark">Go to my account</Link>
          <Link to="/shop" className="w-full min-h-[48px] border border-aayna-burgundy text-aayna-burgundy font-semibold flex items-center justify-center hover:bg-aayna-mist">Continue shopping</Link>
        </div>
      </AuthShell>
    );
  }
  if (state === "no_token") {
    return (
      <AuthShell testid="verify-pending" title="Check your email" intro="Open the confirmation link we sent you to activate your account. Links expire after 24 hours.">
        <ResendForm />
      </AuthShell>
    );
  }
  return (
    <AuthShell testid={`verify-${state}`} title={state === "expired" ? "This link has expired" : state === "used" ? "Already confirmed" : "This link isn't valid"}
               footer={<Link to="/login" className="text-aayna-burgundy font-medium hover:underline underline-offset-2">Go to sign in</Link>}>
      <Notice tone={state === "used" ? "info" : "error"}>{state === "used" ? "This confirmation link has already been used. If your account is confirmed, just sign in." : message}</Notice>
      {state !== "used" && <ResendForm />}
    </AuthShell>
  );
}

export function ForgotPassword() {
  useSeo({ title: "Forgot password", description: "Reset your AAYNA password.", noindex: true });
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) { setError("Please enter a valid email address."); return; }
    setLoading(true);
    try {
      setStatus({ tone: "success", text: (await forgotPassword(email.trim())).message });
    } catch (err) {
      setStatus({ tone: "error", text: apiError(err).message });
    } finally {
      setLoading(false);
    }
  };
  return (
    <AuthShell testid="forgot-page" title="Forgot your password?" intro="Enter your account email and we'll send you a link to choose a new password. The link works for 15 minutes."
               footer={<Link to="/login" className="text-aayna-burgundy font-medium hover:underline underline-offset-2">Back to sign in</Link>}>
      <form onSubmit={submit} noValidate className="space-y-4">
        {status && <Notice tone={status.tone} testid="forgot-status">{status.text}</Notice>}
        <Field label="Email" type="email" autoComplete="email" inputMode="email" data-testid="forgot-email" value={email} error={error}
               onChange={(e) => { setEmail(e.target.value); setError(""); }} />
        <SubmitButton loading={loading} data-testid="forgot-submit">Send reset link</SubmitButton>
      </form>
      <p className="text-xs text-aayna-taupe mt-4 leading-relaxed">Signed up with Google? You don't need a password - use "Continue with Google" on the sign-in page.</p>
    </AuthShell>
  );
}

export function ResetPassword() {
  useSeo({ title: "Choose a new password", description: "Reset your AAYNA password.", noindex: true });
  const token = useFragmentToken();
  const navigate = useNavigate();
  const [form, setForm] = useState({ password: "", confirm_password: "" });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (form.password.length < 12) errs.password = "Use at least 12 characters.";
    if (form.password !== form.confirm_password) errs.confirm_password = "The passwords do not match.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    try {
      const r = await resetPassword({ token, ...form });
      setDone(true);
      setStatus({ tone: "success", text: r.message });
    } catch (err) {
      const e2 = apiError(err);
      setErrors(e2.fields || {});
      setStatus({ tone: "error", text: e2.message, code: e2.code });
    } finally {
      setLoading(false);
    }
  };
  if (!token) {
    return (
      <AuthShell testid="reset-missing" title="Reset link needed" intro="Open the password reset link from your email. Each link works once, for 15 minutes.">
        <Link to="/forgot-password" className="w-full min-h-[48px] bg-aayna-coral text-white font-semibold flex items-center justify-center">Request a new link</Link>
      </AuthShell>
    );
  }
  if (done) {
    return (
      <AuthShell testid="reset-done" title="Password changed">
        <Notice tone="success">{status.text}</Notice>
        <button type="button" onClick={() => navigate("/login")} className="mt-5 w-full min-h-[48px] bg-aayna-coral text-white font-semibold">Sign in</button>
      </AuthShell>
    );
  }
  return (
    <AuthShell testid="reset-page" title="Choose a new password" intro="You'll be signed out of every device, then you can sign in with the new password.">
      <form onSubmit={submit} noValidate className="space-y-4">
        {status && <Notice tone={status.tone} testid="reset-status">{status.text}
          {["expired", "used", "invalid"].includes(status.code) && <Link to="/forgot-password" className="block mt-2 font-semibold underline underline-offset-2">Request a new link</Link>}
        </Notice>}
        {/* hidden username helps password managers save the new password against the right account */}
        <input type="text" name="username" autoComplete="username" className="sr-only" tabIndex={-1} aria-hidden="true" readOnly value="" />
        <PasswordField label="New password" autoComplete="new-password" data-testid="reset-password" hint="At least 12 characters. Long phrases are welcome."
                       value={form.password} error={errors.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <PasswordField label="Confirm new password" autoComplete="new-password" data-testid="reset-confirm"
                       value={form.confirm_password} error={errors.confirm_password} onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} />
        <SubmitButton loading={loading} data-testid="reset-submit">Change password</SubmitButton>
      </form>
    </AuthShell>
  );
}

export function ConfirmEmailChange() {
  useSeo({ title: "Confirm new email", description: "Confirm your new AAYNA email.", noindex: true });
  const token = useFragmentToken();
  const { refresh } = useCustomer();
  const [state, setState] = useState({ working: !!token, tone: token ? null : "error", text: token ? "" : "Open the confirmation link from your email." });
  const ran = useRef(false);
  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;
    confirmEmailChange(token)
      .then((r) => { setState({ working: false, tone: "success", text: r.message }); refresh(); })
      .catch((err) => setState({ working: false, tone: "error", text: apiError(err).message }));
  }, [token, refresh]);
  return (
    <AuthShell testid="confirm-email-page" title="Confirm new email"
               footer={<Link to="/login" className="text-aayna-burgundy font-medium hover:underline underline-offset-2">Go to sign in</Link>}>
      {state.working ? <Spinner /> : <Notice tone={state.tone}>{state.text}</Notice>}
    </AuthShell>
  );
}

export function ConfirmOrderClaim() {
  useSeo({ title: "Add order to account", description: "Add an AAYNA order to your account.", noindex: true });
  const token = useFragmentToken();
  const { signedIn, loading } = useCustomer();
  const [state, setState] = useState({ working: !!token, tone: token ? null : "error", text: token ? "" : "Open the link from your email." });
  const ran = useRef(false);
  useEffect(() => {
    if (!token || ran.current || loading || !signedIn) return;
    ran.current = true;
    confirmOrderClaim(token)
      .then((r) => setState({ working: false, tone: "success", text: `Order ${r.order_number} is now in your account.`, num: r.order_number }))
      .catch((err) => setState({ working: false, tone: "error", text: apiError(err).message }));
  }, [token, loading, signedIn]);
  if (!loading && !signedIn) {
    return (
      <AuthShell title="Sign in to continue" intro="Sign in to the account that asked for this link, then open the link from your email again.">
        <Link to="/login?next=/account/orders" className="w-full min-h-[48px] bg-aayna-coral text-white font-semibold flex items-center justify-center">Sign in</Link>
      </AuthShell>
    );
  }
  return (
    <AuthShell testid="claim-confirm-page" title="Add order to your account"
               footer={<Link to="/account/orders" className="text-aayna-burgundy font-medium hover:underline underline-offset-2">View my orders</Link>}>
      {state.working ? <Spinner /> : <Notice tone={state.tone}>{state.text}</Notice>}
    </AuthShell>
  );
}
