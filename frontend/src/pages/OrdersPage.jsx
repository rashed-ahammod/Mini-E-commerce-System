/** The logged-in user's order history, paginated. */

import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import Pagination from '../components/Pagination';
import { orderApi } from '../api/endpoints';
import { formatDate, formatPrice } from '../utils/format';

const PAGE_SIZE = 10;

export default function OrdersPage() {
  const location = useLocation();
  // Set by the cart after a successful checkout.
  const justOrdered = location.state?.justOrdered;

  const [orders, setOrders] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    orderApi
      .list({ page, page_size: PAGE_SIZE })
      .then((data) => {
        setOrders(data.results);
        setCount(data.count);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [page]);

  return (
    <div className="orders">
      <h1>My orders</h1>

      {justOrdered > 0 && (
        <p className="alert alert--success">
          {justOrdered} order{justOrdered === 1 ? '' : 's'} placed successfully.
        </p>
      )}

      {error && <p className="alert alert--error">{error}</p>}

      {loading ? (
        <p className="status">Loading your orders…</p>
      ) : orders.length === 0 ? (
        <p className="status">
          You have not placed any orders yet. <Link to="/">Browse products →</Link>
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Product</th>
              <th>Qty</th>
              <th>Total</th>
              <th>Placed</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id}>
                <td>#{order.id}</td>
                <td>
                  <div className="table__product">
                    {order.product.image && (
                      <img src={order.product.image} alt="" loading="lazy" />
                    )}
                    <Link to={`/products/${order.product.id}`}>
                      {order.product.name}
                    </Link>
                  </div>
                </td>
                <td>{order.quantity}</td>
                <td>{formatPrice(order.total_price)}</td>
                <td className="muted">{formatDate(order.created_at)}</td>
                <td>
                  <Link to={`/orders/${order.id}`}>Details</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Pagination page={page} count={count} pageSize={PAGE_SIZE} onChange={setPage} />
    </div>
  );
}
