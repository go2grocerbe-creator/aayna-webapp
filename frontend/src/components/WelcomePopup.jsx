import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useCustomer } from "@/context/CustomerAuthContext";
import { getWelcomeOffer } from "@/lib/customerApi";

// A small, non-blocking invitation to create an account. It is a convenience
// only: no code is ever shown here - the welcome coupon (when the campaign is
// enabled) is issued server-side after email verification.
const KEY = "aayna_welcome_popup";
const DELAY_MS = 12000;
const SNOOZE_DAYS = 14;
const HIDDEN_PREFIXES = ["/checkout", "/cart", "/account", "/login", "/register", "/verify-email", "/forgot-password",
  "/reset-password", "/confirm-email", "/order-confirmation", "/admin"];

function readPref() {
  try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; }
}
function writePref(v) {
  try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* storage unavailable: shown at most once per page load */ }
}
let shownThisLoad = false;

export default function WelcomePopup() {
  const { pathname } = useLocation();
  const { signedIn, loading } = useCustomer();
  const [open, setOpen] = useState(false);
  const closeRef = useRef(null);
  const { data: offer } = useQuery({ queryKey: ["welcome-offer"], queryFn: getWelcomeOffer, staleTime: 300000, retry: false });

  const hiddenHere = HIDDEN_PREFIXES.some((p) => pathname.startsWith(p)) ||
    (pathname.startsWith("/product/") && typeof window !== "undefined" && window.innerWidth < 768);

  useEffect(() => {
    if (loading || signedIn || hiddenHere || shownThisLoad) return undefined;
    const pref = readPref();
    if (pref?.registered) return undefined;
    if (pref?.dismissedAt && Date.now() - pref.dismissedAt < SNOOZE_DAYS * 86400000) return undefined;
    const t = setTimeout(() => { shownThisLoad = true; setOpen(true); }, DELAY_MS);
    return () => clearTimeout(t);
  }, [loading, signedIn, hiddenHere]);

  useEffect(() => { if (hiddenHere || signedIn) setOpen(false); }, [hiddenHere, signedIn]);
  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus({ preventScroll: true });
    const onKey = (e) => { if (e.key === "Escape") dismiss(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const dismiss = () => { setOpen(false); writePref({ dismissedAt: Date.now() }); };
  if (!open) return null;
  const hasOffer = offer?.enabled;
  const amount = hasOffer ? (offer.type === "percent" ? `${offer.value}% off` : `৳${offer.value} off`) : null;

  return (
    <div role="dialog" aria-modal="false" aria-labelledby="welcome-popup-title" data-testid="welcome-popup"
         className="fixed z-50 inset-x-3 bottom-3 sm:inset-x-auto sm:left-5 sm:bottom-5 sm:w-[360px] bg-aayna-cream border border-aayna-burgundy/25 shadow-xl animate-fade-up">
      <button ref={closeRef} type="button" onClick={dismiss} aria-label="Close" data-testid="welcome-popup-close"
              className="absolute top-1 right-1 h-11 w-11 flex items-center justify-center text-aayna-taupe hover:text-aayna-burgundy">
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
      <div className="p-5 pr-12">
        <p className="text-aayna-coral-dark text-[11px] font-bold tracking-[0.22em] uppercase mb-1.5">Join AAYNA</p>
        <h2 id="welcome-popup-title" className="font-display text-xl font-semibold text-aayna-burgundy-dark leading-snug">
          {hasOffer ? `${amount} your first order` : "Make AAYNA yours"}
        </h2>
        <p className="text-sm text-aayna-taupe mt-2 leading-relaxed">
          {hasOffer
            ? `Create an account and confirm your email to receive a personal code${offer.min_subtotal ? ` for orders of ৳${Number(offer.min_subtotal).toLocaleString("en-US")}+` : ""}. Valid ${offer.validity_days} days.`
            : "Create an account to track your orders, save addresses and check out faster."}
        </p>
        <div className="flex items-center gap-4 mt-4">
          <Link to="/register" onClick={() => { setOpen(false); writePref({ dismissedAt: Date.now() }); }} data-testid="welcome-popup-cta"
                className="inline-flex items-center min-h-[44px] px-5 bg-aayna-coral text-white text-sm font-semibold hover:bg-aayna-coral-dark">
            Create account
          </Link>
          <button type="button" onClick={dismiss} className="min-h-[44px] text-sm text-aayna-taupe hover:text-aayna-burgundy">Not now</button>
        </div>
      </div>
    </div>
  );
}
