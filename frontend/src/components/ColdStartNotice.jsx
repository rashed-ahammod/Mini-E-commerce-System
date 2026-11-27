/**
 * "The server is waking up" — shown only when that is genuinely the reason.
 *
 * The API runs on Render's free tier, which spins a service down after about
 * 15 minutes of inactivity. The request that wakes it up can take the best
 * part of a minute, and a judge or a first-time visitor staring at a spinner
 * has no way to tell that from a broken app.
 *
 * Two conditions, both required, so the notice never misleads:
 *
 *   1. the API really is on Render (`isRenderApi`) — against a local backend
 *      a slow request means something else, and blaming a host that is not
 *      involved would send someone looking in the wrong place;
 *   2. the request has actually been slow (`DELAY_MS`) — a warm server
 *      answers immediately, and a cold-start warning on a fast response is
 *      just noise.
 *
 * Everywhere else, nothing renders and nothing changes.
 */

import { useEffect, useState } from 'react';

import { isRenderApi } from '../api/client';

/** How long a request may take before it is worth explaining. */
const DELAY_MS = 2500;

/** Roughly how long a cold start takes, for the progress hint. */
const WAKE_SECONDS = 50;

export default function ColdStartNotice({ waiting }) {
  const [elapsed, setElapsed] = useState(0);

  const armed = waiting && isRenderApi;

  useEffect(() => {
    if (!armed) {
      setElapsed(0);
      return undefined;
    }

    const startedAt = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.round((Date.now() - startedAt) / 1000)),
      1000,
    );

    return () => clearInterval(timer);
  }, [armed]);

  // Nothing to say until the request has actually taken a while.
  if (!armed || elapsed < DELAY_MS / 1000) return null;

  const progress = Math.min(100, Math.round((elapsed / WAKE_SECONDS) * 100));

  return (
    <div className="cold-start" role="status" aria-live="polite">
      <p className="cold-start__title">Waking the server up…</p>
      <p className="cold-start__body">
        The API is hosted on Render&rsquo;s free tier, which puts the service
        to sleep after about 15 minutes of inactivity. The first request has
        to wake it, which takes roughly {WAKE_SECONDS} seconds. Everything is
        immediate once it is up — this happens only once.
      </p>
      <div
        className="cold-start__track"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Server wake-up progress"
      >
        <div className="cold-start__bar" style={{ width: `${progress}%` }} />
      </div>
      <p className="cold-start__elapsed">
        {elapsed}s elapsed — please keep this tab open.
      </p>
    </div>
  );
}
