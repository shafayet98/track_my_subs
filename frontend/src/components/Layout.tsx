import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { initials } from "../lib/format";

export function Layout() {
  const { user, logout } = useAuth();
  const displayName = user?.name || user?.email?.split("@")[0] || "Account";

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <NavLink to="/" end className="nav-link">
            Dashboard
          </NavLink>
          <Link to="/connect" className="btn">
            Connect
          </Link>
        </div>

        <div className="brand">Track My Subs</div>

        <div className="topbar-right">
          <span className="avatar round">
            {initials(displayName)}
          </span>
          <span className="uname">{displayName}</span>
          <button className="btn-outline" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
