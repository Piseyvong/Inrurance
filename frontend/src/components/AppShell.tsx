import { useState, useSyncExternalStore } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import type { ComponentType, ReactNode } from "react";

import {
  ClockIcon,
  CloseIcon,
  DashboardIcon,
  FileTextIcon,
  LayersIcon,
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
  to: string;
  end?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const publicNavItems: NavItem[] = [
  { to: "/#agents", label: "AI Agents", Icon: DashboardIcon },
  { to: "/#workflow", label: "How It Works", Icon: ClockIcon },
  { to: "/#safeguards", label: "Safeguards", Icon: ShieldCheckIcon },
  { to: "/login", label: "Customer sign in", Icon: LogInIcon },
  { to: "/login?role=officer", label: "Officer sign in", Icon: ShieldCheckIcon }
];

function roleLabel(role: string) {
  if (role === "customer") return "Customer portal";
  if (role === "admin") return "Administration";
  return "Officer workspace";
}

function sidebarGroups(role: string): NavGroup[] {
  if (role === "customer") {
    return [
      {
        label: "Customer",
        items: [
          { to: "/portal", label: "My dashboard", Icon: DashboardIcon, end: true },
          { to: "/customer/claims", label: "My claims", Icon: FileTextIcon }
        ]
      }
    ];
  }
  const administration: NavItem[] = [{ to: "/admin/policies", label: "Policy management", Icon: FileTextIcon }];
  if (role === "admin") administration.unshift({ to: "/admin", label: "Products", Icon: LayersIcon, end: true });
  return [
    {
      label: "Review",
      items: [{ to: "/officer", label: "Officer portal", Icon: UserCheckIcon }]
    },
    {
      label: "Administration",
      items: administration
    }
  ];
}

export function AppShell({ children }: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useSyncExternalStore(subscribeSession, () => sessionStorage.getItem("insuranceSession"), () => null);
  const currentSession = session();
  const authenticated = Boolean(currentSession);
  const navGroups = currentSession ? sidebarGroups(currentSession.role) : [];

  function navActive(item: NavItem, isActive: boolean): boolean {
    if (isActive) return true;
    if (item.to === "/portal") return pathname === "/customer/policies" || pathname.startsWith("/customer/policies/");
    if (item.to === "/customer/claims") return pathname.startsWith("/claims/");
    if (item.to === "/admin") return pathname.startsWith("/admin/policies") === false && pathname.startsWith("/admin");
    return false;
  }

  function logout() {
    clearSession();
    setNavOpen(false);
    navigate("/", { replace: true });
  }

  return (
    <div className={`appShell${authenticated ? " appShell--sidebar" : ""}`}>
      {currentSession ? <>
        <div className={`sidebarScrim${navOpen ? " open" : ""}`} onClick={() => setNavOpen(false)} aria-hidden="true" />
        <aside className={`sidebar${navOpen ? " open" : ""}`} aria-label="Portal navigation">
          <div className="sidebarHead">
            <NavLink className="brand" to={sessionHome(currentSession)} aria-label="Portal home" onClick={() => setNavOpen(false)}>
              <div className="brandMark" aria-hidden="true">
                <ShieldCheckIcon size={22} />
              </div>
              <div>
                <strong>Insurance AI</strong>
                <span>Portal</span>
              </div>
            </NavLink>
            <button type="button" className="navToggle" onClick={() => setNavOpen(false)} aria-label="Close menu">
              <CloseIcon size={20} />
            </button>
          </div>
          <div className="sidebarRole"><UserCheckIcon size={15} /><span>{roleLabel(currentSession.role)}</span></div>
          <nav className="sidebarNav">
            {navGroups.map((group) => (
              <div key={group.label} className="sidebarGroup">
                <span className="sidebarGroupLabel">{group.label}</span>
                {group.items.map((item) => (
                  <NavLink key={item.label} to={item.to} end={item.end} onClick={() => setNavOpen(false)}
                    className={({ isActive }) => (navActive(item, isActive) ? "active" : "")}>
                    <item.Icon size={18} />
                    <span>{item.label}</span>
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="sidebarFoot">
            <div className="sidebarUser">
              <strong>{currentSession.full_name}</strong>
              <span>{currentSession.email}</span>
            </div>
            <button className="navLogout" type="button" onClick={logout}><LogOutIcon size={18} /><span>Log out</span></button>
          </div>
        </aside>
      </> : null}

      <header className={`topBar${authenticated ? " topBar--slim" : ""}`}>
        <div className="topBarInner">
          {currentSession ? <button type="button" className="navToggle" onClick={() => setNavOpen(true)} aria-label="Open portal menu"><MenuIcon size={20} /></button> : null}
          {currentSession ? <NavLink className="brand" to={sessionHome(currentSession)} aria-label="Portal home" onClick={() => setNavOpen(false)}>
            <div className="brandMark" aria-hidden="true">
              <ShieldCheckIcon size={22} />
            </div>
            <div>
              <strong>Insurance AI</strong>
              <span>Portal</span>
            </div>
          </NavLink> : <NavLink className="brand" to="/" aria-label="Insurance AI Agent home">
            <div className="brandMark" aria-hidden="true">
              <ShieldCheckIcon size={22} />
            </div>
            <div>
              <strong>Insurance AI</strong>
              <span>Agents for modern insurers</span>
            </div>
          </NavLink>}
          {!authenticated ? <button
            type="button"
            className="navToggle"
            aria-expanded={navOpen}
            aria-controls="primary-navigation"
            onClick={() => setNavOpen((open) => !open)}
          >
            {navOpen ? <CloseIcon size={20} /> : <MenuIcon size={20} />}
            <span className="srOnly">{navOpen ? "Close Navigation" : "Open Navigation"}</span>
          </button> : null}
          {!authenticated ? <nav id="primary-navigation" aria-label="Main Navigation" className={navOpen ? "open" : undefined}>
            {publicNavItems.map((item) => (
              <NavLink
                key={item.label}
                to={item.to}
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