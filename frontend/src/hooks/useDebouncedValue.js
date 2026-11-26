/**
 * Delay a fast-changing value.
 *
 * Used by the search box so the product list is re-fetched once the user
 * stops typing, instead of on every keystroke.
 */

import { useEffect, useState } from 'react';

export function useDebouncedValue(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
