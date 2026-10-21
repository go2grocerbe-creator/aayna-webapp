import { Link } from "react-router-dom";
import { Instagram, Facebook, Phone, Mail } from "lucide-react";
import { useSettings, useCategories } from "@/hooks/useStore";
import BrandLogo from "@/components/BrandLogo";
import { CONTACT, PARENT_COMPANY } from "@/constants/contact";

export default function Footer() {
  const { data: settings } = useSettings();
  const { data: categories = [] } = useCategories();
  const year = new Date().getFullYear();

  // 21 Oct 2026: phone and email are the founder-approved public contacts (constants/contact.js).
  // 21 Oct 2026: only Cash on Delivery is approved; bKash/Nagad are not offered or shown.
  const paymentBadges = [
    settings?.cod_available !== false && "Cash on Delivery",
  ].filter(Boolean);

  // Header and footer both hide categories with nothing to buy.
  const shopCategories = categories.filter((c) => (c.product_count || 0) > 0);
  const linkCls = "inline-flex items-center min-h-[44px] text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors";
  const legalCls = "inline-flex items-center min-h-[44px] text-xs text-aayna-beige/70 hover:text-aayna-gold transition-colors";

  return (
    <footer data-testid="site-footer" className="bg-aayna-burgundy-dark text-aayna-beige mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-10">
          <div className="col-span-2 md:col-span-1">
            {/* Founder-approved logo, golden version for the dark footer (see BrandLogo.jsx). */}
            <BrandLogo variant="golden" className="h-14 w-auto" alt="AAYNA" data-testid="footer-logo" />
            <p className="mt-3 text-sm text-aayna-beige/80 leading-relaxed max-w-xs">
              {settings?.tagline || "Reflect Your Aura."} Modern jewellery and
              accessories for the everyday Bangladeshi woman — delivered
              nationwide, with care.
            </p>
            <div className="flex items-center gap-1 mt-4 -ml-3">
              <a href={settings?.instagram_url} target="_blank" rel="noopener noreferrer" aria-label="Instagram" className="h-11 w-11 flex items-center justify-center hover:text-aayna-gold transition-colors">
                <Instagram className="h-5 w-5" />
              </a>
              <a href={settings?.facebook_url} target="_blank" rel="noopener noreferrer" aria-label="Facebook" className="h-11 w-11 flex items-center justify-center hover:text-aayna-gold transition-colors">
                <Facebook className="h-5 w-5" />
              </a>
            </div>
          </div>

          <nav aria-label="Shop">
            <h4 className="text-sm font-bold text-aayna-cream mb-1">Shop</h4>
            <ul>
              <li><Link to="/shop" className={linkCls}>All jewellery</Link></li>
              {shopCategories.map((c) => (
                <li key={c.slug}>
                  <Link to={`/category/${c.slug}`} className={linkCls}>{c.name}</Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Help">
            <h4 className="text-sm font-bold text-aayna-cream mb-1">Help</h4>
            <ul>
              <li><Link to="/track-order" className={linkCls}>Track Order</Link></li>
              <li><Link to="/delivery-policy" className={linkCls}>Delivery Policy</Link></li>
              <li><Link to="/returns" className={linkCls}>Returns &amp; Exchange</Link></li>
            </ul>
          </nav>

          <div>
            <h4 className="text-sm font-bold text-aayna-cream mb-1">Contact</h4>
            <ul>
              <li>
                <a href={`tel:${CONTACT.phoneE164}`} data-testid="footer-phone" className={`${linkCls} gap-2`}>
                  <Phone className="h-4 w-4 text-aayna-gold" /> {CONTACT.phoneDisplay}
                </a>
              </li>
              <li>
                <a href={`mailto:${CONTACT.general}`} data-testid="footer-email" className={`${linkCls} gap-2 break-all`}>
                  <Mail className="h-4 w-4 text-aayna-gold shrink-0" /> {CONTACT.general}
                </a>
              </li>
              <li><Link to="/contact" className={linkCls}>Contact Us</Link></li>
            </ul>
            <div className="mt-4">
              <p className="text-xs text-aayna-beige/60 mb-2">We accept</p>
              <div className="flex flex-wrap gap-2">
                {paymentBadges.map((m) => (
                  <span key={m} className="text-xs font-semibold bg-white/10 border border-white/15 px-2.5 py-1 rounded-sm">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Legal row. Each footer destination appears exactly once (Phase 3 removed
            the round-3 "all pages" row that repeated six column links). */}
        <div className="border-t border-white/10 mt-10 pt-4 flex flex-col-reverse md:flex-row md:items-center justify-between gap-x-6 gap-y-2">
          <p className="text-xs text-aayna-beige/60 py-2">
            <span className="block md:inline">© {year} AAYNA. All rights reserved.</span>
            <span className="hidden md:inline"> · </span>
            <span className="block md:inline">
              <a href={PARENT_COMPANY.url} target="_blank" rel="noopener noreferrer" data-testid="footer-parent-company"
                 className="underline underline-offset-2 hover:text-aayna-gold">{PARENT_COMPANY.text}</a>
            </span>
          </p>
          <nav aria-label="Legal" className="flex flex-wrap gap-x-6">
            <Link to="/privacy" className={legalCls}>Privacy Policy</Link>
            <Link to="/terms" className={legalCls}>Terms &amp; Conditions</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
