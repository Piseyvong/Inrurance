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

export function getOfficerClaimWorkspace(claimId:number):Promise<any>{return apiRequest(`/officer/claims/${claimId}`);}
export function addOfficerNote(claimId:number,note:string):Promise<any>{return apiRequest(`/officer/claims/${claimId}/notes`,{method:"POST",body:JSON.stringify({note})});}
export async function getOfficerDocumentBlob(claimId:number,documentId:number,download=false):Promise<string>{const saved=JSON.parse(sessionStorage.getItem("insuranceSession")||"null");const base=import.meta.env.VITE_API_BASE_URL??"http://127.0.0.1:8000";const response=await fetch(`${base}/officer/claims/${claimId}/documents/${documentId}/${download?"download":"view"}`,{headers:{"X-Demo-User":String(saved?.user_id??"")}});if(!response.ok)throw new Error("Unable to open the authorized document.");return URL.createObjectURL(await response.blob());}
