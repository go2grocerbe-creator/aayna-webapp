import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useCustomer } from "@/context/CustomerAuthContext";
import { register, resendVerification, googleStartUrl, getWelcomeOffer, apiError } from "@/lib/customerApi";
import { AuthShell, Field, PasswordField, SubmitButton, Notice, GoogleButton, OrDivider } from "@/components/account/ui";
import { useSeo } from "@/lib/seo";
import { safeNext } from "@/pages/auth/Login";

const PHONE_RE = /^(?:\+?880|0)1[3-9]\d{8}$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function markRegistered() {
  try { localStorage.setItem("aayna_welcome_popup", JSON.stringify({ registered: true, at: Date.now() })); } catch { /* storage unavailable */ }
}

export default function Register() {
  useSeo({ title: "Create account", description: "Create your AAYNA account.", noindex: true });
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { config, signedIn, loading: sessionLoading } = useCustomer();
  const next = safeNext(params.get("next"));
  const { data: offer } = useQuery({ queryKey: ["welcome-offer"], queryFn: getWelcomeOffer, staleTime: 300000 });
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "", confirm_password: "", accept_terms: false });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState(null);
  const [sentTo, setSentTo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const min = config.password_min_length || 12;

  useEffect(() => { if (!sessionLoading && signedIn) navigate("/account", { replace: true }); }, [sessionLoading, signedIn, navigate]);
  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const set = (k, v) => { setForm((f) => ({ ...f, [k]: v })); setErrors((e) => ({ ...e, [k]: undefined })); };

  const validate = () => {
    const e = {};
    if (form.full_name.trim().length < 2) e.full_name = "Please enter your full name.";
    if (!EMAIL_RE.test(form.email.trim())) e.email = "Please enter a valid email address.";
    if (!PHONE_RE.test(form.phone.replace(/[\s-]/g, ""))) e.phone = "Please enter a valid Bangladesh mobile number, e.g. 01712345678.";
    if (form.password.length < min) e.password = `Use at least ${min} characters. A short phrase of a few words works well.`;
    if (form.password !== form.confirm_password) e.confirm_password = "The passwords do not match.";
    if (!form.accept_terms) e.accept_terms = "Please accept the Terms and Privacy Policy to continue.";
    setErrors(e);
    if (Object.keys(e).length) document.querySelector(`[name="${Object.keys(e)[0]}"]`)?.focus();
    return !Object.keys(e).length;
  };

  const submit = async (ev) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setStatus(null);
    try {
      const r = await register({ ...form, email: form.email.trim(), full_name: form.full_name.trim() });
      markRegistered();
      setSentTo(form.email.trim());
      setStatus({ tone: "success", text: r.message });
      setCooldown(60);
    } catch (err) {
      const e = apiError(err);
      setErrors(e.fields || {});
      setStatus({ tone: "error", text: e.message });
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    try {
      const r = await resendVerification(sentTo);
      setStatus({ tone: "success", text: r.message });
      setCooldown(60);
    } catch (err) {
      setStatus({ tone: "error", text: apiError(err).message });
    }
  };

  if (sentTo) {
    return (
      <AuthShell testid="register-sent" title="Check your email" intro={null}
                 footer={<>Already confirmed? <Link to="/login" className="text-aayna-burgundy font-medium hover:underline underline-offset-2">Sign in</Link></>}>
        <Notice tone="success" testid="register-success">{status?.text}</Notice>
        <p className="text-sm text-aayna-taupe mt-5 leading-relaxed">
          We sent the link to <span className="font-medium text-aayna-charcoal break-all">{sentTo}</span>. It expires in 24 hours.
          Didn't get it? Check your spam folder, or send a new link.
        </p>
        <button type="button" onClick={resend} disabled={cooldown > 0} data-testid="register-resend"
                className="mt-5 w-full min-h-[48px] border border-aayna-burgundy text-aayna-burgundy font-semibold disabled:opacity-50">
          {cooldown > 0 ? `Send a new link in ${cooldown}s` : "Send a new link"}
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell testid="register-page" title="Create your account"
               intro={offer?.enabled
                 ? `Track your orders, save addresses, and get ${offer.type === "percent" ? `${offer.value}%` : `৳${offer.value}`} off your first order once you confirm your email.`
                 : "Track your orders, save your delivery addresses and check out faster."}
               footer={<>Already have an account? <Link to={`/login${next !== "/account" ? `?next=${encodeURIComponent(next)}` : ""}`} className="text-aayna-burgundy font-medium hover:underline underline-offset-2">Sign in</Link></>}>
      <div className="space-y-4">
        {status && <Notice tone={status.tone} testid="register-status">{status.text}</Notice>}
        {config.google_enabled && (<><GoogleButton href={googleStartUrl(next)} label="Sign up with Google" /><OrDivider /></>)}
        <form onSubmit={submit} noValidate className="space-y-4">
          <Field label="Full name" name="full_name" autoComplete="name" required data-testid="register-name" maxLength={80}
                 value={form.full_name} error={errors.full_name} onChange={(e) => set("full_name", e.target.value)} />
          <Field label="Email" type="email" name="email" autoComplete="email" inputMode="email" required data-testid="register-email" maxLength={254}
                 value={form.email} error={errors.email} onChange={(e) => set("email", e.target.value)} />
          <Field label="Mobile number" type="tel" name="phone" autoComplete="tel" inputMode="tel" required data-testid="register-phone"
                 placeholder="01712345678" hint="Used for delivery updates. We don't send OTPs." maxLength={20}
                 value={form.phone} error={errors.phone} onChange={(e) => set("phone", e.target.value)} />
          <PasswordField label="Password" name="password" autoComplete="new-password" data-testid="register-password" maxLength={256}
                         hint={`At least ${min} characters. Long phrases are welcome.`}
                         value={form.password} error={errors.password} onChange={(e) => set("password", e.target.value)} />
          <PasswordField label="Confirm password" name="confirm_password" autoComplete="new-password" data-testid="register-confirm" maxLength={256}
                         value={form.confirm_password} error={errors.confirm_password} onChange={(e) => set("confirm_password", e.target.value)} />
          <div>
            <label className="flex items-start gap-3 text-sm text-aayna-charcoal cursor-pointer min-h-[44px]">
              <input type="checkbox" name="accept_terms" data-testid="register-terms" checked={form.accept_terms}
                     aria-invalid={!!errors.accept_terms} aria-describedby={errors.accept_terms ? "terms-error" : undefined}
                     onChange={(e) => set("accept_terms", e.target.checked)} className="mt-1 h-4 w-4 accent-[#7a2238]" />
              <span>I agree to AAYNA's <Link to="/terms" target="_blank" className="underline underline-offset-2 text-aayna-burgundy">Terms</Link> and <Link to="/privacy" target="_blank" className="underline underline-offset-2 text-aayna-burgundy">Privacy Policy</Link>.</span>
            </label>
            {errors.accept_terms && <p id="terms-error" className="text-xs text-red-700 mt-1">{errors.accept_terms}</p>}
          </div>
          <SubmitButton loading={loading} data-testid="register-submit">Create account</SubmitButton>
        </form>
      </div>
    </AuthShell>
  );
}
