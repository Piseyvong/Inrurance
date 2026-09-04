/** Claim intake API functions. */

import { apiRequest } from "./client";
import type { Claim, ClaimCreatePayload, ClaimWithDocuments, DocumentRecord } from "../types/api";

export function createClaim(payload: ClaimCreatePayload): Promise<Claim> {
  return apiRequest<Claim>("/claims", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getClaim(claimId: number): Promise<ClaimWithDocuments> {
  return apiRequest<ClaimWithDocuments>(`/claims/${claimId}`);
}

export function getClaimDocuments(claimId: number): Promise<DocumentRecord[]> {
  return apiRequest<DocumentRecord[]>(`/claims/${claimId}/documents`);
}

export function uploadClaimDocument(claimId: number, docType: string, file: File): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("file", file);
  return apiRequest<DocumentRecord>(`/claims/${claimId}/documents`, {
    method: "POST",
    body: formData
  });
}

export function completeFilenameDemo(claimId: number): Promise<{ matched: boolean; status: string; message: string | null }> {
  return apiRequest(`/claims/${claimId}/demo-complete`, { method: "POST" });
}
