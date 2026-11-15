import { Link, NavLink } from "react-router-dom";
import { Mark } from "./Icons";
import type { ReactNode } from "react";

export function TopBar({ right }: { right?: ReactNode }) {
  return (
    <header className="bar">
      <div className="wrap">
        <Link className="mark" to="/" aria-label="Claim check, start a new check">
          <Mark />
          Claim check
        </Link>
        <nav className="topnav" aria-label="Views">
          <NavLink to="/" end>
            Check a claim
          </NavLink>
          <NavLink to="/story">Jensen Huang story</NavLink>
          <NavLink to="/challenge">
            <span className="nav-long">Spot the automation</span>
            <span className="nav-short">Spot it</span>
          </NavLink>
          {right}
        </nav>
      </div>
    </header>
  );
}

export function Footer({ children }: { children?: ReactNode }) {
  return (
    <footer className="foot">
      <div className="wrap">
        <span>Bluesky public posts only. Private accounts are counted, never named.</span>
        {children}
      </div>
    </footer>
  );
}
