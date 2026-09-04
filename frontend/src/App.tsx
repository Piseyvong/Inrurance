import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AuditHistoryPage } from "./pages/AuditHistoryPage";
import { ClaimDocumentsPage } from "./pages/ClaimDocumentsPage";
import { CreateClaimPage } from "./pages/CreateClaimPage";
import { DashboardPage } from "./pages/DashboardPage";
import { OfficerReviewPage } from "./pages/OfficerReviewPage";
import { OfficerPortalPage } from "./pages/OfficerPortalPage";
import { VerificationPage } from "./pages/VerificationPage";
import { LoginPage } from "./pages/LoginPage";
import { CustomerPortalPage } from "./pages/CustomerPortalPage";
import { AdminProductsPage } from "./pages/AdminProductsPage";

function LegacyOfficerReviewRedirect() {
  const { claimId } = useParams();
  return <Navigate to={claimId ? `/officer/claims/${claimId}/review` : "/officer"} replace />;
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/portal" element={<CustomerPortalPage />} />
        <Route path="/admin" element={<AdminProductsPage />} />
        <Route path="/claims/new" element={<CreateClaimPage />} />
        <Route path="/claims/:claimId/documents" element={<ClaimDocumentsPage />} />
        <Route path="/claims/:claimId/verification" element={<VerificationPage />} />
        <Route path="/claims/:claimId/review" element={<LegacyOfficerReviewRedirect />} />
        <Route path="/claims/:claimId/audit" element={<AuditHistoryPage />} />
        <Route path="/officer" element={<OfficerPortalPage />} />
        <Route path="/officer/claims/:claimId/review" element={<OfficerReviewPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
