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

// Customer-facing presentation labels for the real backend order_status
// values (backend/admin_routes.py ORDER_STATUSES - inspected directly, not
// assumed). Admin screens intentionally keep the raw operational terms
// ("Packed", "Sent to Courier") - this mapping is for OrderConfirmation and
// TrackOrder only, and never changes the stored/internal status string.
const ORDER_STATUS_LABELS = {
  New: "Order received",
  Confirmed: "Confirmed",
  Packed: "Preparing your order",
  "Sent to Courier": "On the way",
  Delivered: "Delivered",
  Cancelled: "Cancelled",
  Returned: "Returned",
};

export const customerStatusLabel = (status) => ORDER_STATUS_LABELS[status] || status;
