import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Search, ShoppingBag, Menu, X } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useCart } from "@/context/CartContext";
import { useCategories } from "@/hooks/useStore";

// Restrained D1.6-D3 header treatment (AAYNA / nav / Search / Bag; Home via
// the wordmark). Phase 3: phones AND tablets (< lg) use the menu sheet, so
// categories, Track Order and Contact are reachable there too - previously
// 768-1023px showed only "Shop" with no menu at all. Desktop (lg+) shows
// Shop, the in-stock categories and Track Order in the same restrained type.
const navLinks = [{ to: "/shop", label: "Shop" }];
const desktopNavClass = ({ isActive }) =>
  `inline-flex items-center min-h-[44px] text-sm font-medium font-body border-b pb-0.5 transition-colors ${
    isActive ? "text-aayna-burgundy border-aayna-burgundy" : "text-aayna-charcoal border-transparent hover:text-aayna-burgundy"
  }`;

export default function Header() {
  const { count } = useCart();
  const { data: allCategories = [] } = useCategories();
  // Nav is a merchandising surface too - don't link to a category with
  // nothing to buy yet (Visual QA Fix Sprint item 4).
  const categories = allCategories.filter((c) => (c.product_count || 0) > 0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [term, setTerm] = useState("");
  const navigate = useNavigate();

  const submitSearch = (e) => {
    e.preventDefault();
    if (term.trim()) {
      navigate(`/shop?search=${encodeURIComponent(term.trim())}`);
      setSearchOpen(false);
      setTerm("");
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-aayna-cream/95 backdrop-blur border-b border-aayna-beige">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 md:h-20">
          {/* Mobile menu */}
          <div className="flex items-center lg:hidden">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <button data-testid="mobile-menu-button" aria-label="Open menu" className="h-11 w-11 -ml-2.5 flex items-center justify-center">
                  <Menu className="h-6 w-6 text-aayna-charcoal" />
                </button>
              </SheetTrigger>
              <SheetContent side="left" className="bg-aayna-cream w-[82%] border-aayna-beige p-0">
                {/* FOUNDER ASSET REQUIRED — FINAL LOGO: restrained text wordmark until an
                    approved logo file exists (Brand Book gives a direction, not a final asset). */}
                <div className="p-6 border-b border-aayna-beige">
                  <Link
                    to="/"
                    onClick={() => setMobileOpen(false)}
                    className="inline-flex items-center min-h-[44px] font-display text-2xl font-semibold text-aayna-burgundy tracking-[0.08em]"
                  >
                    AAYNA
                  </Link>
                </div>
                <nav className="flex flex-col p-4">
                  {navLinks.map((l) => (
                    <Link
                      key={l.to}
                      to={l.to}
                      data-testid={`mobile-nav-${l.label.toLowerCase()}`}
                      onClick={() => setMobileOpen(false)}
                      className="flex items-center min-h-[48px] px-2 text-base font-medium text-aayna-charcoal border-b border-aayna-beige/60"
                    >
                      {l.label}
                    </Link>
                  ))}
                  <p className="mt-4 mb-1 px-2 text-xs uppercase tracking-wider text-aayna-taupe">
                    Categories
                  </p>
                  {categories.map((c) => (
                    <Link
                      key={c.slug}
                      to={`/category/${c.slug}`}
                      onClick={() => setMobileOpen(false)}
                      className="flex items-center min-h-[44px] px-2 text-sm text-aayna-charcoal"
                    >
                      {c.name}
                    </Link>
                  ))}
                  <div className="mt-4 border-t border-aayna-beige pt-3">
                    <Link to="/track-order" onClick={() => setMobileOpen(false)} className="flex items-center min-h-[44px] px-2 text-sm text-aayna-charcoal">
                      Track Order
                    </Link>
                    <Link to="/contact" onClick={() => setMobileOpen(false)} className="flex items-center min-h-[44px] px-2 text-sm text-aayna-charcoal">
                      Contact
                    </Link>
                  </div>
                </nav>
              </SheetContent>
            </Sheet>
          </div>

          {/* Logo — FOUNDER ASSET REQUIRED: FINAL LOGO. Restrained editorial text
              wordmark per the Brand Book's proposed direction until an approved
              logo file exists; do not treat this as a final identity mark. */}
          <Link to="/" data-testid="logo-link" aria-label="AAYNA home" className="flex-1 lg:flex-none flex items-center justify-center lg:justify-start min-h-[44px]">
            <span className="font-display text-2xl md:text-3xl font-semibold text-aayna-burgundy tracking-[0.08em]">
              AAYNA
            </span>
          </Link>

          {/* Desktop nav (lg+): Shop, in-stock categories, Track Order. Contact
              stays in the footer; phones/tablets use the menu sheet above. */}
          <nav aria-label="Main" className="hidden lg:flex items-center gap-7">
            {navLinks.map((l) => (
              <NavLink key={l.to} to={l.to} end data-testid={`nav-${l.label.toLowerCase()}`} className={desktopNavClass}>
                {l.label}
              </NavLink>
            ))}
            {categories.map((c) => (
              <NavLink key={c.slug} to={`/category/${c.slug}`} data-testid={`nav-cat-${c.slug}`} className={desktopNavClass}>
                {c.name}
              </NavLink>
            ))}
            <NavLink to="/track-order" data-testid="nav-track-order" className={desktopNavClass}>
              Track Order
            </NavLink>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-1 lg:gap-3">
            <button
              data-testid="search-toggle"
              aria-label="Search"
              onClick={() => setSearchOpen((s) => !s)}
              className="h-11 w-11 flex items-center justify-center text-aayna-charcoal hover:text-aayna-burgundy transition-colors"
            >
              <Search className="h-5 w-5" />
            </button>
            <Link
              to="/cart"
              data-testid="cart-icon"
              aria-label="Cart"
              className="relative h-11 w-11 flex items-center justify-center text-aayna-charcoal hover:text-aayna-burgundy transition-colors"
            >
              <ShoppingBag className="h-5 w-5" />
              {count > 0 && (
                <span
                  data-testid="cart-count-badge"
                  className="absolute top-1 right-1 bg-aayna-coral text-white text-[10px] font-bold rounded-full h-4 min-w-4 px-1 flex items-center justify-center"
                >
                  {count}
                </span>
              )}
            </Link>
          </div>
        </div>

        {/* Search bar */}
        {searchOpen && (
          <form onSubmit={submitSearch} className="pb-4 animate-fade-up">
            <div className="flex items-center border border-aayna-beige bg-white">
              <Search className="h-4 w-4 ml-3 text-aayna-taupe" />
              <input
                data-testid="search-input"
                autoFocus
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                aria-label="Search products"
                placeholder="Search earrings, necklaces, rings..."
                className="flex-1 px-3 h-11 bg-transparent outline-none text-aayna-charcoal text-sm"
              />
              <button type="button" aria-label="Close search" onClick={() => setSearchOpen(false)} className="h-11 w-11 flex items-center justify-center">
                <X className="h-4 w-4 text-aayna-taupe" />
              </button>
            </div>
          </form>
        )}
      </div>
    </header>
  );
}
