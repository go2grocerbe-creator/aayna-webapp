export const formatBDT = (n) => `৳${Number(n || 0).toLocaleString("en-US")}`;

export const effectivePrice = (p) =>
  p && p.discount_price && p.discount_price > 0 ? p.discount_price : p?.selling_price;

export const discountPercent = (p) => {
  if (p && p.discount_price && p.discount_price > 0 && p.selling_price) {
    return Math.round((1 - p.discount_price / p.selling_price) * 100);
  }
  return 0;
};

export const isOutOfStock = (p) =>
  !p || p.stock_quantity <= 0 || p.status === "out_of_stock";

// Mirrors backend/auth.py-adjacent server.py `_looks_placeholder()` so the
// storefront never shows a founder-unconfigured value (e.g. "01XXXXXXXXX")
// as if it were real, live payment/contact information.
export const isPlaceholder = (value) => {
  const v = (value || "").trim().toLowerCase();
  if (!v) return true;
  if (v.startsWith("test")) return true;
  return ["xxxx", "example.com", "changeme", "placeholder"].some((m) => v.includes(m));
};
