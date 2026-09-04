import { apiRequest } from "./client";
import type { PolicyRequirements } from "../types/api";

export function getPolicies(): Promise<PolicyRequirements[]> {
  return apiRequest<PolicyRequirements[]>("/policies");
}
