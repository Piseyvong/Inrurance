import type { DocumentRecord, DocumentType, RuleOutcome } from "../types/api";

export const REQUIRED_DOCUMENTS: Array<{ type: DocumentType; title: string; description: string }> = [];

export const ACCEPTED_FILE_TYPES = ".pdf,.jpg,.jpeg,.png";

export function documentLabel(docType: string): string {
  return docType.split("_").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}

export function formatBytes(size: number | null | undefined): string {
  if (!size) return "Unknown size";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function getDocumentByType(documents: DocumentRecord[], docType: DocumentType): DocumentRecord | undefined {
  return documents.find((document) => document.doc_type === docType);
}

export function isAcceptedFile(file: File): boolean {
  const lowerName = file.name.toLowerCase();
  return [".pdf", ".jpg", ".jpeg", ".png"].some((extension) => lowerName.endsWith(extension));
}

export function outcomeLabel(result: string): string {
  const labels: Record<RuleOutcome, string> = {
    match: "Match",
    mismatch: "Mismatch",
    missing: "Missing",
    unclear: "Unclear",
    not_applicable: "Not Applicable"
  };
  return labels[result as RuleOutcome] ?? result;
}

export function parseLineRefs(value: string | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [value];
  }
}

export function formatDateTime(value: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}
