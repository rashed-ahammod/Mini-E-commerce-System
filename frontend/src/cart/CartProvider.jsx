/**
 * A client-side shopping cart.
 *
 * The backend has no cart: one order is one product and one quantity. The
 * cart exists purely so a visitor can gather several products before
 * checking out, and checkout then posts one order per cart line. Keeping it
 * here, rather than inventing a cart API, keeps the backend matching the
 * assignment while the UI still behaves like a shop.
 *
 * The cart is saved to localStorage so a page refresh does not empty it.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import { CartContext } from './cartContext';

const STORAGE_KEY = 'mini-ecommerce-cart';

function readStoredCart() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function CartProvider({ children }) {
  // Each line: { id, name, price, image, stock, quantity }
  // Price and name are copied in so the cart can be rendered without
  // re-fetching every product.
  const [items, setItems] = useState(readStoredCart);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      // Not fatal: the cart just will not survive a refresh.
    }
  }, [items]);

  const addItem = useCallback((product, quantity = 1) => {
    setItems((current) => {
      const existing = current.find((item) => item.id === product.id);
      if (existing) {
        // Never let the cart hold more than the stock the API reported;
        // the server re-checks at checkout anyway.
        const combined = Math.min(existing.quantity + quantity, product.stock);
        return current.map((item) =>
          item.id === product.id ? { ...item, quantity: combined } : item,
        );
      }
      return [
        ...current,
        {
          id: product.id,
          name: product.name,
          price: product.price,
          image: product.image,
          stock: product.stock,
          quantity: Math.min(quantity, product.stock),
        },
      ];
    });
  }, []);

  const updateQuantity = useCallback((productId, quantity) => {
    setItems((current) =>
      current.map((item) =>
        item.id === productId
          ? { ...item, quantity: Math.max(1, Math.min(quantity, item.stock)) }
          : item,
      ),
    );
  }, []);

  const removeItem = useCallback((productId) => {
    setItems((current) => current.filter((item) => item.id !== productId));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const itemCount = useMemo(
    () => items.reduce((total, item) => total + item.quantity, 0),
    [items],
  );

  const total = useMemo(
    () => items.reduce((sum, item) => sum + Number(item.price) * item.quantity, 0),
    [items],
  );

  const value = useMemo(
    () => ({ items, itemCount, total, addItem, updateQuantity, removeItem, clear }),
    [items, itemCount, total, addItem, updateQuantity, removeItem, clear],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
