/**
 * Shared API transport for the FastAPI backend.
 *
 * Keeping fetch handling in one module avoids divergent error parsing and keeps
 * page components focused on rendering and workflow state.
 */

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    let userHeader: Record<string,string> = {};
    try { const saved = JSON.parse(sessionStorage.getItem("insuranceSession") || "null"); if (saved?.user_id) userHeader = { "X-Demo-User": String(saved.user_id) }; } catch { /* no session */ }
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...userHeader,
        ...init.headers
      }
    });
  } catch (error) {
    throw new ApiError(
      `Cannot reach the backend API at ${API_BASE_URL}. Confirm FastAPI is running and VITE_API_BASE_URL is correct.`,
      0,
      error
    );
  }

  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(extractErrorMessage(body, response.status), response.status, body);
  }
  return body as T;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError("Backend returned malformed JSON.", response.status, text);
  }
}

function extractErrorMessage(body: unknown, status: number): string {
  if (typeof body === "object" && body && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => JSON.stringify(item)).join("; ");
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
  }
  return `Backend request failed with status ${status}.`;
}
