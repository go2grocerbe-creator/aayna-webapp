import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, Package, FolderTree, ShoppingCart, Boxes, Users, Settings as SettingsIcon,
  LogOut, Menu, ExternalLink, Loader2,
} from "lucide-react";
import { useAdminAuth } from "@/admin/AdminAuthContext";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

const navItems = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/orders", label: "Orders", icon: ShoppingCart },
  { to: "/admin/products", label: "Products", icon: Package },
  { to: "/admin/categories", label: "Categories", icon: FolderTree },
  { to: "/admin/inventory", label: "Inventory", icon: Boxes },
  { to: "/admin/customers", label: "Customers", icon: Users },
  { to: "/admin/settings", label: "Settings", icon: SettingsIcon },
];

function SidebarContent({ onNavigate, user, onLogout }) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-5 border-b border-gray-200">
        <span className="font-display text-2xl font-extrabold text-aayna-charcoal tracking-tight">AAYNA</span>
        <p className="text-xs text-gray-400 mt-0.5">Admin Panel</p>
      </div>
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            data-testid={`admin-nav-${item.label.toLowerCase()}`}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                isActive ? "bg-aayna-rose text-white" : "text-gray-600 hover:bg-aayna-mist hover:text-aayna-rose"
              }`
            }
          >
            <item.icon className="h-4.5 w-4.5 h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-gray-200 space-y-1">
        <a href="/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-gray-600 hover:bg-gray-100">
          <ExternalLink className="h-5 w-5" /> View Store
        </a>
        <div className="px-3 py-2 text-xs text-gray-400">
          {user?.email}
          <span className="block uppercase tracking-wide text-[10px] text-aayna-rose font-semibold">{user?.role}</span>
        </div>
        <button
          data-testid="admin-logout"
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-red-600 hover:bg-red-50"
        >
          <LogOut className="h-5 w-5" /> Log out
        </button>
      </div>
    </div>
  );
}

export function AdminProtected() {
  const { user } = useAdminAuth();
  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-7 w-7 animate-spin text-aayna-rose" />
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

  const handleLogout = () => {
    logout();
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
            <button data-testid="admin-mobile-menu" className="p-2 -ml-2"><Menu className="h-6 w-6" /></button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-64 bg-white">
            <SidebarContent user={user} onLogout={handleLogout} onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
        <span className="font-display text-xl font-extrabold text-aayna-charcoal">AAYNA</span>
        <span className="w-6" />
      </div>

      <main className="md:pl-64">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
