/** API calls for the OpenAI-backed public platform guide. */

import { apiRequest } from "./client";

export type AgentAction = { type:"link"|"consultation"; label:string; href:string };
export type ConsultationPayload = { name:string; email?:string; phone?:string; product_interest?:string; preferred_time?:string; question?:string };
export type ConsultationResponse = { id:number; status:string; message:string };
export type GuideChatResponse = {
  reply: string;
  mode: "guest" | "customer";
  actions: AgentAction[];
};

export function askInsuranceAgent(message:string):Promise<GuideChatResponse>{return apiRequest<GuideChatResponse>("/chat",{method:"POST",body:JSON.stringify({message})});}

export function requestConsultation(payload:ConsultationPayload):Promise<ConsultationResponse>{return apiRequest<ConsultationResponse>("/chat/consultations",{method:"POST",body:JSON.stringify(payload)});}

export async function askInsuranceGuide(message: string): Promise<string> {
  const response = await askInsuranceAgent(message);
  return response.reply;
}
