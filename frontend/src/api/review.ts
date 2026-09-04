/** Officer review and audit API functions. */

import { apiRequest } from "./client";
import type { AuditLogEntry, Claim, OfficerReviewPayload } from "../types/api";

export function getOfficerClaims(status = ""): Promise<Claim[]> {
  return apiRequest<Claim[]>(`/officer/claims?status=${encodeURIComponent(status)}`);
}

export function officerDecision(claimId:number, action:string, reason:string, approved_amount?:number){return apiRequest<{status:string}>(`/officer/claims/${claimId}/decision`,{method:"POST",body:JSON.stringify({action,reason,approved_amount})});}

export function correctField(documentId:number,fieldId:number,value:string){return apiRequest(`/documents/${documentId}/fields/${fieldId}`,{method:"PATCH",body:JSON.stringify({value})});}

export function getAuditHistory(claimId: number): Promise<AuditLogEntry[]> {
  return apiRequest<AuditLogEntry[]>(`/claims/${claimId}/audit`);
}

export function submitReview(claimId: number, payload: OfficerReviewPayload): Promise<AuditLogEntry> {
  return apiRequest<AuditLogEntry>(`/claims/${claimId}/review`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
