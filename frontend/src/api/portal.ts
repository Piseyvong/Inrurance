import { apiRequest } from "./client";

export type Session = { user_id:number; full_name:string; email:string; role:"customer"|"officer"|"admin" };
export function session():Session|null { try { return JSON.parse(sessionStorage.getItem("insuranceSession") || "null"); } catch { return null; } }
export function login(email:string,password:string) { return apiRequest<Session>("/auth/login",{method:"POST",body:JSON.stringify({email,password})}); }
export function portal() { const s=session(); return apiRequest<any>("/portal/me",{headers:{"X-Demo-User":String(s?.user_id)}}); }
export function startPortalClaim(payload:unknown) { const s=session(); return apiRequest<any>("/portal/claims",{method:"POST",headers:{"X-Demo-User":String(s?.user_id)},body:JSON.stringify(payload)}); }
export function products() { const s=session(); return apiRequest<any[]>("/admin/products",{headers:{"X-Demo-User":String(s?.user_id)}}); }
export function createProduct(payload:unknown) { const s=session(); return apiRequest<any>("/admin/products",{method:"POST",headers:{"X-Demo-User":String(s?.user_id)},body:JSON.stringify(payload)}); }
