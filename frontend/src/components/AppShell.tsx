import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { ComponentType, ReactNode } from "react";

import {
  ClockIcon,
  CloseIcon,
  DashboardIcon,
  MenuIcon,
  ShieldCheckIcon,
  UserCheckIcon
} from "./icons";
import { InsuranceAgentBubble } from "./InsuranceAgentBubble";
import { session } from "../api/portal";

interface AppShellProps {
  children: ReactNode;
}

interface NavItem {
  label: string;
  Icon: ComponentType<{ size?: number; className?: string }>;
  to?: string;
}

const navItems: NavItem[] = [
  { to: "/#agents", label: "AI Agents", Icon: DashboardIcon },
  { to: "/#workflow", label: "How It Works", Icon: ClockIcon },
  { to: "/#safeguards", label: "Safeguards", Icon: ShieldCheckIcon },
  { to: "/login", label: "Sign in", Icon: UserCheckIcon }
];

const officerNavItems: NavItem[] = [
  { to: "/officer", label: "Officer Portal", Icon: UserCheckIcon }
];

export function AppShell({ children }: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();
  const authenticated = Boolean(session());
  const activeNavItems = authenticated ? (location.pathname.startsWith("/officer") ? officerNavItems : []) : navItems;

  return (
    <div className="appShell">
      <header className="topBar">
        <div className="topBarInner">
          <NavLink className="brand" to={authenticated ? "/portal" : "/"} aria-label="Insurance AI Agent home">
            <div className="brandMark" aria-hidden="true">
              <ShieldCheckIcon size={22} />
            </div>
            <div>
              <strong>Insurance AI</strong>
              <span>Agents for modern insurers</span>
            </div>
          </NavLink>
          {activeNavItems.length ? <button
            type="button"
            className="navToggle"
            aria-expanded={navOpen}
            aria-controls="primary-navigation"
            onClick={() => setNavOpen((open) => !open)}
          >
            {navOpen ? <CloseIcon size={20} /> : <MenuIcon size={20} />}
            <span className="srOnly">{navOpen ? "Close Navigation" : "Open Navigation"}</span>
          </button> : null}
          {activeNavItems.length ? <nav id="primary-navigation" aria-label="Main Navigation" className={navOpen ? "open" : undefined}>
            {activeNavItems.map((item) => (
              <NavLink
                key={item.label}
                to={item.to!}
                end={item.to === "/"}
                onClick={() => setNavOpen(false)}
              >
                <item.Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav> : null}
        </div>
      </header>
      <main className="mainContent">{children}</main>
      <InsuranceAgentBubble />
    </div>
  );
}
