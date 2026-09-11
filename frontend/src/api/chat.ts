/** API calls for the OpenAI-backed public platform guide. */

import { apiRequest } from "./client";

export type AgentAction = { type:"link"|"consultation"; label:string; href:string };
export type ConsultationPayload = { name:string; email?:string; phone?:string; product_interest?:string; preferred_time?:string; question?:string };
export type ConsultationResponse = { id:number; status:string; message:string };

export type DocumentChecklistItem = { name:string; submitted:boolean };
export type ClaimStatusData = { id:number; claim_type:string; status:string; amount:number | null; documents:DocumentChecklistItem[] | null; next_steps:string[] | null };
export type PolicyInfoData = { policy_number:string; product_name:string; status:string; coverage_type:string | null; end_date:string | null; benefits:string[] | null };
export type StructuredData = { type:"claim_status" | "policy_info"; claims:ClaimStatusData[] | null; policies:PolicyInfoData[] | null };

export type GuideChatResponse = {
  reply: string;
  mode: "guest" | "customer";
  actions: AgentAction[];
  structured_data: StructuredData | null;
};

export function askInsuranceAgent(message:string):Promise<GuideChatResponse>{return apiRequest<GuideChatResponse>("/chat",{method:"POST",body:JSON.stringify({message})});}

export function requestConsultation(payload:ConsultationPayload):Promise<ConsultationResponse>{return apiRequest<ConsultationResponse>("/chat/consultations",{method:"POST",body:JSON.stringify(payload)});}

export async function askInsuranceGuide(message: string): Promise<string> {
  const response = await askInsuranceAgent(message);
  return response.reply;
}
