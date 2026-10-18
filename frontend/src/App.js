import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Toaster } from "@/components/ui/sonner";
import { CartProvider } from "@/context/CartContext";
import Layout from "@/components/Layout";
import Analytics from "@/components/Analytics";
import Home from "@/pages/Home";
import Shop from "@/pages/Shop";
import Category from "@/pages/Category";
import ProductDetail from "@/pages/ProductDetail";
import Cart from "@/pages/Cart";
import Checkout from "@/pages/Checkout";
import OrderConfirmation from "@/pages/OrderConfirmation";
import TrackOrder from "@/pages/TrackOrder";
import Contact from "@/pages/Contact";
import StaticPage from "@/pages/StaticPage";
import NotFound from "@/pages/NotFound";

import { AdminAuthLayout } from "@/admin/AdminAuthContext";
import AdminLayout, { AdminProtected, RequirePermission } from "@/admin/AdminLayout";
import AdminLogin from "@/admin/AdminLogin";
import Dashboard from "@/admin/pages/Dashboard";
import Products from "@/admin/pages/Products";
import ProductForm from "@/admin/pages/ProductForm";
import Categories from "@/admin/pages/Categories";
import Orders from "@/admin/pages/Orders";
import OrderDetail from "@/admin/pages/OrderDetail";
import Inventory from "@/admin/pages/Inventory";
import Customers from "@/admin/pages/Customers";
import CustomerDetail from "@/admin/pages/CustomerDetail";
import Settings from "@/admin/pages/Settings";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  return null;
}

function App() {
  return (
    <div className="App">
      <CartProvider>
        <BrowserRouter>
          <ScrollToTop />
          <Analytics />
          <Routes>
            {/* Storefront */}
            <Route element={<Layout />}>
              <Route path="/" element={<Home />} />
              <Route path="/shop" element={<Shop />} />
              <Route path="/category/:slug" element={<Category />} />
              <Route path="/product/:slug" element={<ProductDetail />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/order-confirmation/:orderNumber" element={<OrderConfirmation />} />
              <Route path="/track-order" element={<TrackOrder />} />
              <Route path="/contact" element={<Contact />} />
              <Route path="/delivery-policy" element={<StaticPage pageKey="delivery" />} />
              <Route path="/returns" element={<StaticPage pageKey="returns" />} />
              <Route path="/privacy" element={<StaticPage pageKey="privacy" />} />
              <Route path="/terms" element={<StaticPage pageKey="terms" />} />
              <Route path="*" element={<NotFound />} />
            </Route>

            {/* Admin */}
            <Route path="/admin" element={<AdminAuthLayout />}>
              <Route path="login" element={<AdminLogin />} />
              <Route element={<AdminProtected />}>
                <Route element={<AdminLayout />}>
                  <Route index element={<RequirePermission perm="dashboard.view"><Dashboard /></RequirePermission>} />
                  <Route path="products" element={<RequirePermission perm="products.view"><Products /></RequirePermission>} />
                  <Route path="products/new" element={<RequirePermission perm="products.edit"><ProductForm /></RequirePermission>} />
                  <Route path="products/:id" element={<RequirePermission perm="products.view"><ProductForm /></RequirePermission>} />
                  <Route path="categories" element={<RequirePermission perm="products.view"><Categories /></RequirePermission>} />
                  <Route path="orders" element={<RequirePermission perm="orders.view"><Orders /></RequirePermission>} />
                  <Route path="orders/:orderNumber" element={<RequirePermission perm="orders.view"><OrderDetail /></RequirePermission>} />
                  <Route path="inventory" element={<RequirePermission perm="inventory.view"><Inventory /></RequirePermission>} />
                  <Route path="customers" element={<RequirePermission perm="customers.view"><Customers /></RequirePermission>} />
                  <Route path="customers/:id" element={<RequirePermission perm="customers.view"><CustomerDetail /></RequirePermission>} />
                  <Route path="settings" element={<RequirePermission perm="settings.view"><Settings /></RequirePermission>} />
                </Route>
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-center" richColors />
      </CartProvider>
    </div>
  );
}

export default App;
