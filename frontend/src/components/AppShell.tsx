import { useState, useSyncExternalStore } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import type { ComponentType, ReactNode } from "react";

import {
  ClockIcon,
  CloseIcon,
  DashboardIcon,
  LogInIcon,
  LogOutIcon,
  MenuIcon,
  ShieldCheckIcon,
  UserCheckIcon
} from "./icons";
import { InsuranceAgentBubble } from "./InsuranceAgentBubble";
import { clearSession, session, sessionHome, subscribeSession } from "../api/portal";

interface AppShellProps {
  children: ReactNode;
}

interface NavItem {
  label: string;
  Icon: ComponentType<{ size?: number; className?: string }>;
  to?: string;
}

const publicNavItems: NavItem[] = [
  { to: "/#agents", label: "AI Agents", Icon: DashboardIcon },
  { to: "/#workflow", label: "How It Works", Icon: ClockIcon },
  { to: "/#safeguards", label: "Safeguards", Icon: ShieldCheckIcon },
  { to: "/login", label: "Customer sign in", Icon: LogInIcon },
  { to: "/login?role=officer", label: "Officer sign in", Icon: ShieldCheckIcon }
];

const officerNavItems: NavItem[] = [
  { to: "/officer", label: "Officer Portal", Icon: UserCheckIcon },
  { to: "/admin/policies", label: "Policy Management", Icon: DashboardIcon }
];

const customerNavItems: NavItem[] = [
  { to: "/portal", label: "My dashboard", Icon: DashboardIcon }
];

export function AppShell({ children }: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  useSyncExternalStore(subscribeSession, () => sessionStorage.getItem("insuranceSession"), () => null);
  const currentSession = session();
  const authenticated = Boolean(currentSession);
  const activeNavItems = !currentSession ? publicNavItems : currentSession.role === "customer" ? customerNavItems : officerNavItems;

  function logout() {
    clearSession();
    setNavOpen(false);
    navigate("/", { replace: true });
  }

  return (
    <div className="appShell">
      <header className="topBar">
        <div className="topBarInner">
          <NavLink className="brand" to={authenticated ? sessionHome(currentSession) : "/"} aria-label="Insurance AI Agent home">
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
            {currentSession ? <button className="navLogout" type="button" onClick={logout} aria-label={`Log out ${currentSession.full_name}`}><LogOutIcon size={18}/><span>Logout</span></button> : null}
          </nav> : null}
        </div>
      </header>
      <main className="mainContent">{children}</main>
      <InsuranceAgentBubble />
    </div>
  );
}
