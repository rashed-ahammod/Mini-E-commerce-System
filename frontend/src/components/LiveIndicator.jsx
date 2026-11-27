/**
 * "This page keeps itself up to date, and here is when it last did."
 *
 * A page that quietly changes under you is unsettling if nothing says it is
 * going to. This says so, and — more usefully — shows when the last refresh
 * landed, so that a stale page caused by a dropped connection looks
 * different from a quiet one where simply nothing has happened.
 *
 * It pauses with the polling when the tab is hidden, and says so, rather
 * than letting the timestamp drift and implying data that is not arriving.
 */

import { useEffect, useState } from 'react';

function sinceLabel(at, now) {
  if (!at) return 'syncing…';

  const seconds = Math.max(0, Math.round((now - at) / 1000));
  if (seconds < 10) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;

  return at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function LiveIndicator({ at, label = 'Live' }) {
  const [now, setNow] = useState(() => Date.now());
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    // Only to re-render the relative time; the data itself is refreshed by
    // whoever owns the fetch.
    const timer = setInterval(() => setNow(Date.now()), 5000);
    const onVisibility = () => setHidden(document.hidden);

    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return (
    <span className={`live ${hidden ? 'live--paused' : ''}`} role="status">
      <span className="live__dot" aria-hidden="true" />
      <span className="live__text">
        {hidden ? 'Paused' : label} · updated {sinceLabel(at, now)}
      </span>
    </span>
  );
}
