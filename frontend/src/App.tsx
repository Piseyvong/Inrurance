import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AuditHistoryPage } from "./pages/AuditHistoryPage";
import { ClaimDocumentsPage } from "./pages/ClaimDocumentsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { OfficerReviewPage } from "./pages/OfficerReviewPage";
import { OfficerPortalPage } from "./pages/OfficerPortalPage";
import { VerificationPage } from "./pages/VerificationPage";
import { LoginPage } from "./pages/LoginPage";
import { CustomerPortalPage } from "./pages/CustomerPortalPage";
import { ClaimHistoryPage } from "./pages/ClaimHistoryPage";
import { AdminProductsPage } from "./pages/AdminProductsPage";
import { PolicyManagementPage } from "./pages/PolicyManagementPage";
import { CustomerPolicyPage } from "./pages/CustomerPolicyPage";
import { ProtectedRoute } from "./components/ProtectedRoute";

function LegacyOfficerReviewRedirect() {
  const { claimId } = useParams();
  return <Navigate to={claimId ? `/officer/claims/${claimId}` : "/officer"} replace />;
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/portal" element={<ProtectedRoute roles={["customer"]}><CustomerPortalPage /></ProtectedRoute>} />
        <Route path="/customer/policies/:policyId" element={<ProtectedRoute roles={["customer"]}><CustomerPolicyPage /></ProtectedRoute>} />
        <Route path="/customer/claims" element={<ProtectedRoute roles={["customer"]}><ClaimHistoryPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute roles={["admin"]}><AdminProductsPage /></ProtectedRoute>} />
        <Route path="/admin/policies" element={<ProtectedRoute roles={["admin","officer"]}><PolicyManagementPage /></ProtectedRoute>} />
        <Route path="/claims/new" element={<Navigate to="/portal" replace />} />
        <Route path="/claims/:claimId/documents" element={<ProtectedRoute roles={["customer"]}><ClaimDocumentsPage /></ProtectedRoute>} />
        <Route path="/claims/:claimId/verification" element={<ProtectedRoute roles={["customer"]}><VerificationPage /></ProtectedRoute>} />
        <Route path="/claims/:claimId/review" element={<LegacyOfficerReviewRedirect />} />
        <Route path="/claims/:claimId/audit" element={<ProtectedRoute roles={["officer","admin"]}><AuditHistoryPage /></ProtectedRoute>} />
        <Route path="/officer" element={<ProtectedRoute roles={["officer","admin"]}><OfficerPortalPage /></ProtectedRoute>} />
        <Route path="/officer/claims/:claimId" element={<ProtectedRoute roles={["officer","admin"]}><OfficerReviewPage /></ProtectedRoute>} />
        <Route path="/officer/claims/:claimId/review" element={<LegacyOfficerReviewRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
