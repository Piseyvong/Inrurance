/** OCR and extraction API functions for uploaded documents. */

import { API_BASE_URL, apiRequest } from "./client";
import { session } from "./portal";
import type { ExtractedField, OCRRun } from "../types/api";

export function processDocument(documentId: number): Promise<OCRRun> {
  return apiRequest<OCRRun>(`/documents/${documentId}/process`, { method: "POST" });
}

export function getOcrRuns(documentId: number): Promise<OCRRun[]> {
  return apiRequest<OCRRun[]>(`/documents/${documentId}/ocr-runs`);
}

export function extractDocumentFields(documentId: number): Promise<ExtractedField[]> {
  return apiRequest<ExtractedField[]>(`/documents/${documentId}/extract`, { method: "POST" });
}

export async function getDocumentPreview(documentId: number): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/preview`, {
    headers: { "X-Demo-User": String(session()?.user_id ?? "") }
  });
  if (!response.ok) throw new Error("Unable to load the document preview.");
  return URL.createObjectURL(await response.blob());
}
