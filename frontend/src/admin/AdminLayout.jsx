import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, Package, FolderTree, ShoppingCart, Boxes, Users, Settings as SettingsIcon,
  LogOut, Menu, ExternalLink, Loader2, UserCheck, Tag, Wallet,
} from "lucide-react";
import { useAdminAuth } from "@/admin/AdminAuthContext";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useSeo } from "@/lib/seo";

const navItems = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true, perm: "dashboard.view" },
  { to: "/admin/orders", label: "Orders", icon: ShoppingCart, perm: "orders.view" },
  { to: "/admin/courier-money", label: "Courier money", icon: Wallet, perm: "courier.finance" },
  { to: "/admin/products", label: "Products", icon: Package, perm: "products.view" },
  { to: "/admin/categories", label: "Categories", icon: FolderTree, perm: "products.view" },
  { to: "/admin/inventory", label: "Inventory", icon: Boxes, perm: "inventory.view" },
  { to: "/admin/customers", label: "Customers", icon: Users, perm: "customers.view" },
  { to: "/admin/accounts", label: "Accounts", icon: UserCheck, perm: "customers.view" },
  { to: "/admin/promotions", label: "Promotions", icon: Tag, perm: "promotions.view" },
  { to: "/admin/settings", label: "Settings", icon: SettingsIcon, perm: "settings.view" },
];

// Shown when a role opens a page it may not use. The API refuses the data
// anyway (403); this just explains it instead of an error.
export function RequirePermission({ perm, children }) {
  const { can } = useAdminAuth();
  if (can(perm)) return children;
  return (
    <div data-testid="admin-no-access" className="bg-white border border-gray-200 rounded-lg p-8 text-center">
      <h1 className="text-lg font-semibold text-aayna-charcoal">No access</h1>
      <p className="text-sm text-gray-500 mt-1">Your role does not include this section. Ask the account owner if you need it.</p>
    </div>
  );
}

function SidebarContent({ onNavigate, user, onLogout }) {
  const allowed = navItems.filter((i) => (user?.permissions || []).includes(i.perm));
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-5 border-b border-gray-200">
        <span className="font-display text-2xl font-extrabold text-aayna-charcoal tracking-tight">AAYNA</span>
        <p className="text-xs text-gray-400 mt-0.5">Admin Panel</p>
      </div>
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {allowed.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            data-testid={`admin-nav-${item.label.toLowerCase()}`}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 min-h-[44px] rounded-md text-sm font-medium transition-colors ${
                isActive ? "bg-aayna-burgundy text-white" : "text-gray-600 hover:bg-aayna-mist hover:text-aayna-burgundy"
              }`
            }
          >
            <item.icon className="h-4.5 w-4.5 h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-gray-200 space-y-1">
        <a href="/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 min-h-[44px] rounded-md text-sm text-gray-600 hover:bg-gray-100">
          <ExternalLink className="h-5 w-5" /> View Store
        </a>
        <div className="px-3 py-2 text-xs text-gray-400">
          {user?.email}
          <span className="block uppercase tracking-wide text-xs text-aayna-burgundy font-semibold">{user?.role}</span>
        </div>
        <button
          data-testid="admin-logout"
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 min-h-[44px] rounded-md text-sm font-medium text-red-600 hover:bg-red-50"
        >
          <LogOut className="h-5 w-5" /> Log out
        </button>
      </div>
    </div>
  );
}

export function AdminProtected() {
  useSeo({ title: "Admin", noindex: true });
  const { user } = useAdminAuth();
  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-7 w-7 animate-spin text-aayna-burgundy" />
      </div>
    );
  }
  if (!user) return <Navigate to="/admin/login" replace />;
  return <Outlet />;
}

export default function AdminLayout() {
  const { user, logout } = useAdminAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/admin/login");
  };

  return (
    <div className="min-h-screen bg-gray-50 font-body">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-64 fixed inset-y-0 left-0 bg-white border-r border-gray-200">
        <SidebarContent user={user} onLogout={handleLogout} />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden sticky top-0 z-30 bg-white border-b border-gray-200 flex items-center justify-between px-4 h-14">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <button data-testid="admin-mobile-menu" aria-label="Open admin menu" className="h-11 w-11 -ml-2.5 flex items-center justify-center"><Menu className="h-6 w-6" /></button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-64 bg-white">
            <SidebarContent user={user} onLogout={handleLogout} onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
        <span className="font-display text-xl font-extrabold text-aayna-charcoal">AAYNA</span>
        <span className="w-11" />
      </div>

      <main className="md:pl-64">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
