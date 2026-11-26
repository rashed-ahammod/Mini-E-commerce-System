/** Page frame: navigation on top, routed page in the middle, footer below. */

import { Outlet } from 'react-router-dom';

import NavBar from './NavBar';

export default function Layout() {
  return (
    <div className="app">
      <NavBar />
      <main className="app__main">
        <Outlet />
      </main>
      <footer className="app__footer">
        Mini E-commerce — React frontend for the Django REST API.
      </footer>
    </div>
  );
}
