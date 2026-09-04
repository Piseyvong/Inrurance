import type { ClaimWithDocuments, VerificationReport } from "../types/api";

const steps = [
  "Policy matched",
  "Documents uploaded",
  "OCR extracted",
  "Compliance checked",
  "Decision"
];

interface ProgressTrackerProps {
  claim?: ClaimWithDocuments | null;
  verification?: VerificationReport | null;
}

export function ProgressTracker({ claim, verification }: ProgressTrackerProps) {
  const approved = claim?.status === "auto_approved" || verification?.claim_status === "auto_approved";
  const complete = {
    "Policy matched": Boolean(claim?.policy_requirements),
    "Documents uploaded": Boolean(claim?.document_completeness?.is_complete),
    "OCR extracted": approved || Boolean(
      verification?.rule_results.some((rule) => rule.rule_name.startsWith("ocr_available") && rule.result === "match")
    ),
    "Compliance checked": approved || Boolean(verification?.rule_results.length),
    "Decision": Boolean(
      approved || (verification?.claim_status &&
      !["intake", "submitted", "waiting_for_documents"].includes(verification.claim_status))
    )
  };

  return (
    <ol className="progressTracker" aria-label="Claim Progress">
      {steps.map((step) => (
        <li key={step} className={complete[step as keyof typeof complete] ? "done" : ""}>
          <span className="stepMarker" aria-hidden="true" />
          {step}
        </li>
      ))}
    </ol>
  );
}
