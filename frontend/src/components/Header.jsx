import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Search, ShoppingBag, Menu, X } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useCart } from "@/context/CartContext";
import { useCategories } from "@/hooks/useStore";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/shop", label: "Shop" },
];

export default function Header() {
  const { count } = useCart();
  const { data: categories = [] } = useCategories();
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

  const linkClass = ({ isActive }) =>
    `text-sm font-medium font-body transition-colors hover:text-aayna-burgundy ${
      isActive ? "text-aayna-burgundy" : "text-aayna-charcoal"
    }`;

  return (
    <header className="sticky top-0 z-40 bg-aayna-cream/95 backdrop-blur border-b border-aayna-beige">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 md:h-20">
          {/* Mobile menu */}
          <div className="flex items-center md:hidden">
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
                  <span className="font-display text-2xl font-semibold text-aayna-burgundy tracking-[0.08em]">
                    AAYNA
                  </span>
                </div>
                <nav className="flex flex-col p-4">
                  {navLinks.map((l) => (
                    <Link
                      key={l.to}
                      to={l.to}
                      data-testid={`mobile-nav-${l.label.toLowerCase()}`}
                      onClick={() => setMobileOpen(false)}
                      className="py-3.5 px-2 text-base font-medium text-aayna-charcoal border-b border-aayna-beige/60"
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
                      className="py-3 px-2 text-sm text-aayna-charcoal"
                    >
                      {c.name}
                    </Link>
                  ))}
                  <div className="mt-4 border-t border-aayna-beige pt-3">
                    <Link to="/track-order" onClick={() => setMobileOpen(false)} className="py-3 px-2 text-sm text-aayna-charcoal block">
                      Track Order
                    </Link>
                    <Link to="/contact" onClick={() => setMobileOpen(false)} className="py-3 px-2 text-sm text-aayna-charcoal block">
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
          <Link to="/" data-testid="logo-link" className="flex-1 md:flex-none text-center md:text-left">
            <span className="font-display text-2xl md:text-3xl font-semibold text-aayna-burgundy tracking-[0.08em]">
              AAYNA
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((l) => (
              <NavLink key={l.to} to={l.to} data-testid={`nav-${l.label.toLowerCase()}`} className={linkClass}>
                {l.label}
              </NavLink>
            ))}
            <div className="relative group">
              <button className="text-sm font-medium font-body text-aayna-charcoal hover:text-aayna-burgundy transition-colors">
                Categories
              </button>
              <div className="absolute left-1/2 -translate-x-1/2 top-full pt-3 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                <div className="bg-white border border-aayna-beige shadow-lg rounded-sm py-2 w-52">
                  {categories.map((c) => (
                    <Link
                      key={c.slug}
                      to={`/category/${c.slug}`}
                      className="block px-4 py-2 text-sm text-aayna-charcoal hover:bg-aayna-mist hover:text-aayna-burgundy transition-colors"
                    >
                      {c.name}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <NavLink to="/track-order" className={linkClass}>Track Order</NavLink>
            <NavLink to="/contact" className={linkClass}>Contact</NavLink>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-1 md:gap-3">
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
                placeholder="Search earrings, necklaces, rings..."
                className="flex-1 px-3 h-11 bg-transparent outline-none text-aayna-charcoal text-sm"
              />
              <button type="button" onClick={() => setSearchOpen(false)} className="px-3">
                <X className="h-4 w-4 text-aayna-taupe" />
              </button>
            </div>
          </form>
        )}
      </div>
    </header>
  );
}
