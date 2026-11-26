/** Read and change the cart from anywhere in the tree. */

import { useContext } from 'react';

import { CartContext } from './cartContext';

export function useCart() {
  const context = useContext(CartContext);
  if (context === null) {
    throw new Error('useCart must be used inside a <CartProvider>.');
  }
  return context;
}
