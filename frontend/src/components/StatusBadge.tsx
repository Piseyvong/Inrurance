interface StatusBadgeProps {
  status: string;
}

const statusTone: Record<string, string> = {
  match: "good",
  succeeded: "good",
  completed: "good",
  ok: "good",
  received: "good",
  uploaded: "good",
  backend_connected: "good",
  auto_approved: "good",
  auto_approval_eligible: "good",
  compliant: "good",
  ocr_extracted: "good",
  uploading: "info",
  processing: "info",
  required: "info",
  optional: "neutral",
  mismatch: "danger",
  failed: "danger",
  error: "danger",
  backend_unavailable: "danger",
  database_unavailable: "danger",
  configuration_error: "danger",
  missing: "warning",
  unclear: "warning",
  human_review_required: "warning",
  pending_human_review: "warning",
  missing_required_documents: "warning",
  not_compliant: "danger",
  rejected_not_compliant: "danger",
  pending: "info",
  ready_for_officer_review: "info",
  intake: "info",
  submitted: "neutral",
  not_started: "neutral",
  not_applicable: "neutral"
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalised = status.toLowerCase().split(" ").join("_");
  const tone = statusTone[normalised] ?? "neutral";
  return <span className={`statusBadge ${tone}`}>{normalised.split("_").join(" ")}</span>;
}
