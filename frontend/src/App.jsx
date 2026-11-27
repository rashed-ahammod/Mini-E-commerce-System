/**
 * Routes.
 *
 * Two trees. The shop sits inside <Layout>; the organization console sits
 * under /org inside <OrgLayout>, gated by <OrganizationRoute>.
 *
 * Access is decided in exactly two components — <ProtectedRoute> for "needs
 * a login" and <OrganizationRoute> for "needs the right kind of account" —
 * so no page has to remember to check for itself.
 */

import { Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import OrgLayout from './org/components/OrgLayout';
import OrganizationRoute from './org/OrganizationRoute';
import OrgDashboardPage from './org/pages/OrgDashboardPage';
import OrgOrderDetailPage from './org/pages/OrgOrderDetailPage';
import OrgCategoriesPage from './org/pages/OrgCategoriesPage';
import OrgCustomerDetailPage from './org/pages/OrgCustomerDetailPage';
import OrgCustomersPage from './org/pages/OrgCustomersPage';
import OrgOrdersPage from './org/pages/OrgOrdersPage';
import OrgProductsPage from './org/pages/OrgProductsPage';
import OrgStaffPage from './org/pages/OrgStaffPage';
import CartPage from './pages/CartPage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import OrderDetailPage from './pages/OrderDetailPage';
import OrdersPage from './pages/OrdersPage';
import ProductDetailPage from './pages/ProductDetailPage';
import ProductListPage from './pages/ProductListPage';
import RegisterPage from './pages/RegisterPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* public */}
        <Route index element={<ProductListPage />} />
        <Route path="products/:id" element={<ProductDetailPage />} />
        <Route path="cart" element={<CartPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />

        {/* requires a token */}
        <Route
          path="orders"
          element={
            <ProtectedRoute>
              <OrdersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="orders/:id"
          element={
            <ProtectedRoute>
              <OrderDetailPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* The organization console. Its own layout, because it is a
          different job from shopping and should not look like it. */}
      <Route
        path="/org"
        element={
          <OrganizationRoute>
            <OrgLayout />
          </OrganizationRoute>
        }
      >
        <Route index element={<OrgDashboardPage />} />
        <Route path="orders" element={<OrgOrdersPage />} />
        <Route path="orders/:id" element={<OrgOrderDetailPage />} />
        <Route path="products" element={<OrgProductsPage />} />
        <Route path="categories" element={<OrgCategoriesPage />} />
        <Route path="customers" element={<OrgCustomersPage />} />
        <Route path="customers/:id" element={<OrgCustomerDetailPage />} />

        {/* Managing colleagues is an admin job; staff are sent back to
            the dashboard rather than shown a page of 403s. */}
        <Route
          path="staff"
          element={
            <OrganizationRoute adminOnly>
              <OrgStaffPage />
            </OrganizationRoute>
          }
        />
      </Route>
    </Routes>
  );
}
