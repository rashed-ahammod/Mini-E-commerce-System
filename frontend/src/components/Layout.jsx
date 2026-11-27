/** Page frame: navigation on top, routed page below it. */

import { Outlet } from 'react-router-dom';

import NavBar from './NavBar';

export default function Layout() {
  return (
    <div className="app">
      <NavBar />
      <main className="app__main">
        <Outlet />
      </main>
    </div>
  );
}
