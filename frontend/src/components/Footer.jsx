import { Link } from "react-router-dom";
import { Instagram, Facebook, Mail, Phone } from "lucide-react";
import { useSettings, useCategories } from "@/hooks/useStore";

export default function Footer() {
  const { data: settings } = useSettings();
  const { data: categories = [] } = useCategories();
  const year = new Date().getFullYear();

  return (
    <footer data-testid="site-footer" className="bg-aayna-charcoal text-aayna-beige mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-10">
          <div className="col-span-2 md:col-span-1">
            <span className="font-display text-2xl font-extrabold text-aayna-cream tracking-tight">AAYNA</span>
            <p className="mt-3 text-sm text-aayna-beige/80 leading-relaxed max-w-xs">
              {settings?.tagline || "Reflect your everyday style."} Affordable, trendy and feminine
              accessories delivered across Bangladesh.
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
              <li className="flex items-center gap-2 text-sm text-aayna-beige/85">
                <Phone className="h-4 w-4 text-aayna-gold" /> {settings?.whatsapp_number}
              </li>
              <li className="flex items-center gap-2 text-sm text-aayna-beige/85">
                <Mail className="h-4 w-4 text-aayna-gold" /> {settings?.support_email}
              </li>
              <li><Link to="/contact" className="text-sm text-aayna-beige/85 hover:text-aayna-gold transition-colors">Contact Us</Link></li>
            </ul>
            <div className="mt-5">
              <p className="text-xs text-aayna-beige/60 mb-2">We accept</p>
              <div className="flex flex-wrap gap-2">
                {["Cash on Delivery", "bKash", "Nagad"].map((m) => (
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
