export type DocumentType = string;

export interface DocumentRequirement {
  type: string;
  title: string;
  description: string;
  required_fields: string[];
}

export interface PolicyRequirements {
  id: number | null;
  claim_type: string;
  policy_version?: number;
  display_name: string;
  description: string | null;
  required_documents: DocumentRequirement[];
  validation_rules: Record<string, unknown>;
  auto_approval_threshold: string | number | null;
  currency: string;
  minimum_ocr_confidence: number;
  active: boolean;
  version: number;
}

export type RuleOutcome = "match" | "mismatch" | "missing" | "unclear" | "not_applicable";

export interface HealthStatus {
  api: "ok";
  database: "ok" | "error";
  ocr_provider?: string;
  backend_status?: "ready" | "database_unavailable" | string;
  message?: string;
}

export interface LlmHealthStatus {
  llm: "ok";
  provider: "azure_openai";
  deployment: string;
  response_received: boolean;
  sample_response?: string;
}

export interface ClaimCreatePayload {
  claim_type: string;
}

export interface Claim {
  id: number;
  claimant_name: string | null;
  policy_number: string | null;
  claim_type: string;
  incident_date: string | null;
  claimed_amount: string | number | null;
  status: string;
  created_at: string | null;
}

export interface DocumentRecord {
  id: number;
  claim_id: number;
  doc_type: DocumentType;
  original_filename: string | null;
  stored_filename?: string | null;
  /** Legacy test fixture only; the API no longer returns internal paths. */
  file_path?: string;
  view_url?: string;
  download_url?: string;
  mime_type: string | null;
  file_size: number | null;
  uploaded_at: string | null;
  ocr_status?: string;
  extraction_status?: string;
  verification_status?: string;
}

export interface ClaimWithDocuments extends Claim {
  documents: DocumentRecord[];
  document_completeness: {
    is_complete?: boolean;
    missing_document_types?: DocumentType[];
    [key: string]: unknown;
  };
  missing_required_document_types: DocumentType[];
  policy_requirements?: PolicyRequirements;
}

export interface OCRRun {
  id: number;
  document_id: number;
  engine: string;
  engine_version: string | null;
  status: "pending" | "processing" | "succeeded" | "failed" | string;
  raw_text: string | null;
  result_json: string | null;
  average_confidence: string | number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExtractedField {
  id: number;
  document_id: number;
  ocr_run_id: number | null;
  field_name: string;
  field_value: string | null;
  normalized_value?: string | null;
  confidence: string | number | null;
  supporting_line_refs: string | null;
  source_text?: string | null;
  semantic_reason?: string | null;
  extraction_method: string | null;
  validation_status: string | null;
  created_at: string | null;
}

export interface RuleResult {
  id: number;
  claim_id: number;
  rule_name: string;
  result: RuleOutcome | string;
  details: string | null;
  evaluated_at: string | null;
}

export interface DocumentReviewScore {
  document_id: number;
  doc_type: DocumentType;
  score: number;
  status: string;
  ocr_confidence: number | null;
  extracted_required_fields: number;
  required_fields: number;
  issue_count: number;
}

export interface EvidenceReviewSummary {
  overall_score: number;
  status: string;
  passed_checks: number;
  total_checks: number;
  issue_count: number;
  summary: string;
  document_scores: DocumentReviewScore[];
}

export interface VerificationReport {
  claim_id: number;
  claim_status: string;
  document_completeness: {
    is_complete?: boolean;
    missing_document_types?: DocumentType[];
    [key: string]: unknown;
  };
  documents: DocumentRecord[];
  extracted_fields: ExtractedField[];
  rule_results: RuleResult[];
  reasons_for_human_review: string[];
  evidence_review: EvidenceReviewSummary;
  policy_requirements?: PolicyRequirements;
}

export interface AuditLogEntry {
  id: number;
  claim_id: number;
  actor: string;
  action: string;
  details: string | null;
  timestamp: string | null;
}

export interface OfficerReviewPayload {
  actor: string;
  action: string;
  details: string | null;
}
