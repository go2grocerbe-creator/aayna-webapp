import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";

const CartContext = createContext(null);
const STORAGE_KEY = "aayna_cart";

export function CartProvider({ children }) {
  const [items, setItems] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const addItem = useCallback((product, qty = 1) => {
    const unit =
      product.discount_price && product.discount_price > 0
        ? product.discount_price
        : product.selling_price;
    const stock = product.stock_quantity;
    setItems((prev) => {
      const existing = prev.find((i) => i.product_id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.product_id === product.id
            ? { ...i, quantity: Math.min(i.quantity + qty, stock) }
            : i
        );
      }
      return [
        ...prev,
        {
          product_id: product.id,
          slug: product.slug,
          name: product.product_name,
          image: product.images?.[0]?.image_url,
          sku: product.sku,
          selling_price: product.selling_price,
          discount_price: product.discount_price,
          unit_price: unit,
          stock,
          quantity: Math.min(qty, stock),
        },
      ];
    });
  }, []);

  const updateQty = useCallback((productId, qty) => {
    setItems((prev) =>
      prev
        .map((i) =>
          i.product_id === productId
            ? { ...i, quantity: Math.max(1, Math.min(qty, i.stock)) }
            : i
        )
        .filter((i) => i.quantity > 0)
    );
  }, []);

  const removeItem = useCallback((productId) => {
    setItems((prev) => prev.filter((i) => i.product_id !== productId));
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  const count = useMemo(() => items.reduce((s, i) => s + i.quantity, 0), [items]);
  const subtotal = useMemo(
    () => items.reduce((s, i) => s + i.unit_price * i.quantity, 0),
    [items]
  );

  const value = { items, addItem, updateQty, removeItem, clearCart, count, subtotal };
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export const useCart = () => {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
};
