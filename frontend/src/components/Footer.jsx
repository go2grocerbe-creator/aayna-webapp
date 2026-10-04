import { Link } from "react-router-dom";
import { Instagram, Facebook, Phone } from "lucide-react";
import { useSettings, useCategories } from "@/hooks/useStore";
import { isPlaceholder } from "@/lib/format";

export default function Footer() {
  const { data: settings } = useSettings();
  const { data: categories = [] } = useCategories();
  const year = new Date().getFullYear();

  // L3.1: WhatsApp/phone only renders once it's a real, non-placeholder
  // number - same isPlaceholder() gate WhatsAppFloat/PDP already use, now
  // applied here too. Support email is intentionally not shown as a launch
  // contact channel yet - founder has not approved one for production (not
  // a placeholder-detection question, a launch-readiness one); see
  // LAUNCH_BUSINESS_SETTINGS_AUDIT.md. "We accept" only lists methods that
  // are actually selectable at checkout today, instead of a hardcoded list
  // that claimed bKash/Nagad were accepted while Checkout disabled both.
  const hasWhatsapp = !isPlaceholder(settings?.whatsapp_number);
  const paymentBadges = [
    settings?.cod_available !== false && "Cash on Delivery",
    !isPlaceholder(settings?.bkash_number) && "bKash",
    !isPlaceholder(settings?.nagad_number) && "Nagad",
  ].filter(Boolean);

  return (
    <footer data-testid="site-footer" className="bg-aayna-burgundy-dark text-aayna-beige mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-10">
          <div className="col-span-2 md:col-span-1">
            {/* FOUNDER ASSET REQUIRED — FINAL LOGO: text wordmark, see Header.jsx */}
            <span className="font-display text-2xl font-semibold text-aayna-cream tracking-[0.08em]">AAYNA</span>
            <p className="mt-3 text-sm text-aayna-beige/80 leading-relaxed max-w-xs">
              {settings?.tagline || "Reflect Your Aura."} Accessible premium jewelry for
              everyday wear, delivered across Bangladesh.
            </p>
            <div className="flex items-center gap-3 mt-5">
              <a href={settings?.instagram_url} target="_blank" rel="noopener noreferrer" aria-label="Instagram" className="hover:text-aayna-gold transition-colors">
                <Instagram className="h-5 w-5" />
              </a>
              <a href={settings?.facebook_url} target="_blank" rel="noopener noreferrer" aria-label="Facebook" className="hover:text-aayna-gold transition-colors">
                <Facebook className="h-5 w-5" />
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-bold text-aayna-cream mb-4">Shop</h4>
            <ul className="space-y-2.5">
              {categories.map((c) => (
                <li key={c.slug}>
                  <Link to={`/category/${c.slug}`} className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">
                    {c.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-bold text-aayna-cream mb-4">Help</h4>
            <ul className="space-y-2.5">
              <li><Link to="/track-order" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Track Order</Link></li>
              <li><Link to="/delivery-policy" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Delivery Policy</Link></li>
              <li><Link to="/returns" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Returns & Exchange</Link></li>
              <li><Link to="/privacy" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Privacy Policy</Link></li>
              <li><Link to="/terms" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Terms & Conditions</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-bold text-aayna-cream mb-4">Contact</h4>
            <ul className="space-y-3">
              {hasWhatsapp && (
                <li className="flex items-center gap-2 text-sm text-aayna-beige/85">
                  <Phone className="h-4 w-4 text-aayna-gold" /> {settings.whatsapp_number}
                </li>
              )}
              <li><Link to="/contact" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Contact Us</Link></li>
            </ul>
            <div className="mt-5">
              <p className="text-xs text-aayna-beige/60 mb-2">We accept</p>
              <div className="flex flex-wrap gap-2">
                {paymentBadges.map((m) => (
                  <span key={m} className="text-[11px] font-semibold bg-white/10 border border-white/15 px-2.5 py-1 rounded-sm">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 mt-12 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-aayna-beige/60">© {year} AAYNA. All rights reserved.</p>
          <p className="text-xs text-aayna-beige/60">Made with care in Bangladesh</p>
        </div>
      </div>
    </footer>
  );
}
