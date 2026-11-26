/** Shown for any URL the router does not recognise. */

import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="status">
      <h1>Page not found</h1>
      <p>That page does not exist.</p>
      <Link to="/">← Back to products</Link>
    </div>
  );
}
