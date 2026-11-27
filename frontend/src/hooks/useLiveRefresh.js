/**
 * Re-run a fetch on an interval, so a page keeps up with the server.
 *
 * The order queue is worked by several people at once: one person confirming
 * an order while another is looking at the same list means the second one is
 * reading something that is no longer true. Customers have the same problem
 * from the other side — an order moves to shipped and the page still says
 * pending until they think to reload.
 *
 * Deliberately polling rather than pushing. Live updates over a socket would
 * mean Django Channels, an ASGI server and a Redis broker — real
 * infrastructure, and more than this earns. Polling a cheap, paginated,
 * already-indexed endpoint gets the same result for the handful of people
 * who use a console like this.
 *
 * Two rules keep it from being wasteful:
 *
 *   - it stops while the tab is hidden, and refreshes once on return, so a
 *     console left open on a second monitor overnight costs nothing;
 *   - it never overlaps with itself or with a refresh the page is already
 *     doing, so a slow response cannot pile requests up behind it.
 *
 * `onTick` must be stable (useCallback), or the interval resets on render.
 */

import { useCallback, useEffect, useRef } from 'react';

/** Long enough to be cheap, short enough that staff are not reading stale rows. */
export const DEFAULT_INTERVAL = 15000;

export function useLiveRefresh(onTick, { interval = DEFAULT_INTERVAL, enabled = true } = {}) {
  // Held in a ref so changing the callback does not restart the timer.
  const callback = useRef(onTick);
  useEffect(() => {
    callback.current = onTick;
  }, [onTick]);

  const running = useRef(false);

  const run = useCallback(async () => {
    // Already fetching: skip this tick rather than queue behind it.
    if (running.current || document.hidden) return;
    running.current = true;
    try {
      await callback.current();
    } catch {
      // A failed poll is not worth interrupting anyone over — the page is
      // still showing the last good data, and the next tick tries again.
    } finally {
      running.current = false;
    }
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;

    const timer = setInterval(run, interval);

    // Coming back to the tab should show current data at once, not after
    // however much of the interval happens to be left.
    const onVisible = () => {
      if (!document.hidden) run();
    };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [run, interval, enabled]);
}
