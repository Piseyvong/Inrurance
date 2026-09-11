import { apiRequest } from "./client";
import type { ClaimHistoryResponse } from "../types/api";

export type Session = { user_id:number; full_name:string; email:string; role:"customer"|"officer"|"admin" };
export function session():Session|null { try { return JSON.parse(sessionStorage.getItem("insuranceSession") || "null"); } catch { return null; } }
export function saveSession(value:Session) { sessionStorage.setItem("insuranceSession",JSON.stringify(value)); window.dispatchEvent(new Event("insurance-session-change")); }
export function clearSession() { sessionStorage.removeItem("insuranceSession"); sessionStorage.removeItem("insuranceAgentConversation"); localStorage.removeItem("lastClaimId"); localStorage.removeItem("recentClaims"); window.dispatchEvent(new Event("insurance-session-change")); }
export function subscribeSession(listener:()=>void) { window.addEventListener("insurance-session-change",listener); window.addEventListener("storage",listener); return ()=>{window.removeEventListener("insurance-session-change",listener);window.removeEventListener("storage",listener);}; }
export function sessionHome(value:Session|null=session()) { return value?.role==="customer"?"/portal":value?.role==="admin"?"/admin":"/officer"; }
export function login(email:string,password:string) { return apiRequest<Session>("/auth/login",{method:"POST",body:JSON.stringify({email,password})}); }
export function portal() { const s=session(); return apiRequest<any>("/portal/me",{headers:{"X-Demo-User":String(s?.user_id)}}); }
export function startPortalClaim(payload:unknown) { const s=session(); return apiRequest<any>("/portal/claims",{method:"POST",headers:{"X-Demo-User":String(s?.user_id)},body:JSON.stringify(payload)}); }
export function customerPolicy(id:number){return apiRequest<any>(`/portal/policies/${id}`);}
export function claimHistory(page:number,pageSize:number,status?:string){const params=new URLSearchParams({page:String(page),page_size:String(pageSize)});if(status)params.set("status",status);return apiRequest<ClaimHistoryResponse>(`/portal/claims/history?${params}`);}
export async function customerPolicyDocumentUrl(id:number){const s=session();const base=import.meta.env.VITE_API_BASE_URL??"http://127.0.0.1:8000";const response=await fetch(`${base}/portal/policies/${id}/document`,{headers:{"X-Demo-User":String(s?.user_id??"")}});if(!response.ok)throw new Error("Policy document is not available.");return URL.createObjectURL(await response.blob());}
export function products() { const s=session(); return apiRequest<any[]>("/admin/products",{headers:{"X-Demo-User":String(s?.user_id)}}); }
export function createProduct(payload:unknown) { const s=session(); return apiRequest<any>("/admin/products",{method:"POST",headers:{"X-Demo-User":String(s?.user_id)},body:JSON.stringify(payload)}); }
export function customers(){return apiRequest<any[]>("/admin/customers");}
export function issueCustomerPolicy(payload:unknown){return apiRequest<any>("/admin/customer-policies",{method:"POST",body:JSON.stringify(payload)});}
export function policyDocuments() { return apiRequest<any[]>("/admin/policy-documents"); }
export function uploadPolicyDocument(payload: FormData) { return apiRequest<any>("/admin/policy-documents", { method:"POST", body:payload }); }
export function archivePolicyDocument(id:number) { return apiRequest<any>(`/admin/policy-documents/${id}/archive`, { method:"POST" }); }
export async function policyDocumentUrl(id:number) { const s=session(); const response=await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}/admin/policy-documents/${id}/file`, {headers:{"X-Demo-User":String(s?.user_id ?? "")}}); if(!response.ok) throw new Error("Unable to open policy document."); return URL.createObjectURL(await response.blob()); }
