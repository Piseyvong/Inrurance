import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { session, sessionHome, type Session } from "../api/portal";

export function ProtectedRoute({ roles, children }: { roles: Session["role"][]; children: ReactNode }) {
  const current = session();
  const location = useLocation();
  if (!current) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!roles.includes(current.role)) return <Navigate to={sessionHome(current)} replace />;
  return <>{children}</>;
}
