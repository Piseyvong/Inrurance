/** Backend health API function used by the dashboard. */

import { apiRequest } from "./client";
import type { HealthStatus, LlmHealthStatus } from "../types/api";

export function getHealth(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>("/health");
}

export function getLlmHealth(): Promise<LlmHealthStatus> {
  return apiRequest<LlmHealthStatus>("/health/llm");
}
