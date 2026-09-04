/** Deterministic verification API functions. */

import { apiRequest } from "./client";
import type { VerificationReport } from "../types/api";

export function runVerification(claimId: number): Promise<VerificationReport> {
  return apiRequest<VerificationReport>(`/claims/${claimId}/verification`, { method: "POST" });
}

export function runClaimPrecheck(claimId: number): Promise<VerificationReport> {
  return apiRequest<VerificationReport>(`/claims/${claimId}/precheck`, { method: "POST" });
}

export function getVerification(claimId: number): Promise<VerificationReport> {
  return apiRequest<VerificationReport>(`/claims/${claimId}/verification`);
}
