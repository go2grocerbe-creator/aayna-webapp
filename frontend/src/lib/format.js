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
