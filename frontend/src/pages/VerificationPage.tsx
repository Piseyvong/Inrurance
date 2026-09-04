import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getClaim } from "../api/claims";
import { getVerification, runClaimPrecheck } from "../api/verification";
import { Alert } from "../components/Alert";
import { PageHeader } from "../components/PageHeader";
import { ProgressTracker } from "../components/ProgressTracker";
import { StatusBadge } from "../components/StatusBadge";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import type { ClaimWithDocuments, VerificationReport } from "../types/api";
import { comparisonRules, groupFieldsByDocument, hasHumanReviewReasons } from "../utils/verification";
import { documentLabel, formatDateTime, outcomeLabel, parseLineRefs } from "../utils/documents";

function reviewReasonText(reason: string) {
  if (reason.startsWith("ocr_confidence_")) return `${documentLabel(reason.replace("ocr_confidence_", ""))} OCR confidence is below the 80% automatic-approval threshold.`;
  if (reason.startsWith("required_field_")) return `Missing required extracted evidence: ${reason.replace("required_field_", "").replace(/_/g, " ")}.`;
  if (reason.startsWith("claim_")) return `Claim evidence needs confirmation: ${reason.replace("claim_", "").replace(/_/g, " ")}.`;
  return reason.replace(/_/g, " ");
}

export function VerificationPage() {
  const claimId = useClaimIdParam();
  const [claim, setClaim] = useState<ClaimWithDocuments | null>(null);
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    if (!claimId) return;
    setClaim(await getClaim(claimId));
    setReport(await getVerification(claimId).catch(() => null));
  }

  useEffect(() => {
    refresh().catch((apiError: Error) => setError(apiError.message));
  }, [claimId]);

  async function verify() {
    if (!claimId) return;
    setLoading(true);
    setError(null);
    try {
      setReport(await runClaimPrecheck(claimId));
      setClaim(await getClaim(claimId));
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Verification failed.");
    } finally {
      setLoading(false);
    }
  }

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  const fieldsByDocument = groupFieldsByDocument(report?.extracted_fields ?? []);
  const approved = claim?.status === "auto_approved";
  const reviewRequired = !approved && report ? hasHumanReviewReasons(report.reasons_for_human_review) : false;
  const missingDocuments = claim?.missing_required_document_types ?? [];
  const canRunPrecheck = Boolean(claim && missingDocuments.length === 0);
  const extractedValue = (fieldName: string, preferredTypes: string[] = []) => {
    const candidates = (report?.extracted_fields ?? []).filter((field) => field.field_name === fieldName && field.field_value && field.validation_status === "valid");
    for (const documentType of preferredTypes) {
      const document = report?.documents.find((item) => item.doc_type === documentType);
      const match = candidates.find((field) => field.document_id === document?.id);
      if (match?.field_value) return match.field_value;
    }
    return candidates[0]?.field_value ?? "Not found in extracted evidence";
  };

  return (
    <div className="pageStack">
      <PageHeader title={`Claim ${claimId} Verification`} eyebrow="Deterministic Verification">
        {approved ? <Link className="secondaryButton" to="/portal">Return to customer portal</Link> : <button type="button" onClick={verify} disabled={loading || !canRunPrecheck} title={!canRunPrecheck ? "Upload every required document before running the pre-check." : undefined}>
          {loading ? "Reading Documents..." : canRunPrecheck ? "Run Document AI Pre-Check" : "Upload documents to continue"}
        </button>}
      </PageHeader>
      {claim ? <ProgressTracker claim={claim} verification={report} /> : null}
      {approved ? <Alert tone="success"><strong>Claim approved.</strong> The benefit payment will be issued within seven business days.</Alert> : <Alert>AI and OCR provide evidence only. Eligibility is determined by the matched policy rules; incomplete or uncertain evidence always goes to a person.</Alert>}
      {missingDocuments.length ? (
        <Alert tone="warning">
          Upload all required documents before OCR can start: <strong>{missingDocuments.map(documentLabel).join(", ")}</strong>.{" "}
          <Link to={`/claims/${claimId}/documents`}>Go to document upload</Link>
        </Alert>
      ) : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}
      {reviewRequired ? (
        <Alert tone="warning">
          <strong>Review reasons</strong>
          <ul>
            {report!.reasons_for_human_review.map((reason) => (
              <li key={reason}>{reviewReasonText(reason)}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {!approved && report?.rule_results.length ? (
        <section className="panel evidenceReviewPanel" aria-labelledby="evidence-review-title">
          <div className="sectionHeading">
            <div>
              <h2 id="evidence-review-title">AI Evidence Review</h2>
              <p>{report.evidence_review.summary}</p>
            </div>
            <div className={`scoreDial ${report.evidence_review.status}`}>
              <strong>{report.evidence_review.overall_score}%</strong>
              <span>Evidence score</span>
            </div>
          </div>
          <div className="scoreGrid">
            <div>
              <span>Checks Passed</span>
              <strong>
                {report.evidence_review.passed_checks} / {report.evidence_review.total_checks}
              </strong>
            </div>
            <div>
              <span>Review Issues</span>
              <strong>{report.evidence_review.issue_count}</strong>
            </div>
            {report.evidence_review.document_scores.map((score) => (
              <div key={score.document_id}>
                <span>{documentLabel(score.doc_type)}</span>
                <strong>{score.score}%</strong>
                <small>
                  {score.extracted_required_fields}/{score.required_fields} fields
                  {score.ocr_confidence !== null ? `, OCR ${Math.round(score.ocr_confidence * 100)}% (80% required for automatic approval)` : ""}
                </small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {!approved && claim && report?.extracted_fields.length ? (
        <section className="panel">
          <h2>Extracted Claim Summary</h2>
          <div className="summaryGrid">
            <span>Claim ID</span>
            <strong>{claim.id}</strong>
            <span>Claimant</span>
            <strong>{extractedValue("claimant_name", ["claim_form", "medical_report", "invoice"])}</strong>
            <span>Policy</span>
            <strong>{extractedValue("policy_number", ["claim_form"])}</strong>
            <span>Incident Date</span>
            <strong>{extractedValue("incident_date", ["claim_form"])}</strong>
            <span>Claimed Amount</span>
            <strong>{extractedValue("claim_amount", ["claim_form", "invoice"])}</strong>
            <span>Medical Evidence</span>
            <strong>{extractedValue("incident_description", ["medical_report"]) !== "Not found in extracted evidence" ? extractedValue("incident_description", ["medical_report"]) : extractedValue("diagnosis", ["medical_report"])}</strong>
          </div>
        </section>
      ) : null}

      <section className="panel">
        <h2>Document Completeness</h2>
        <div className="tableLike">
          {(claim?.documents ?? report?.documents ?? []).map((document) => (
            <div key={document.id}>
              <span>{documentLabel(document.doc_type)}</span>
              <StatusBadge status="received" />
              <span>{document.original_filename ?? document.file_path}</span>
            </div>
          ))}
        </div>
        {claim?.missing_required_document_types?.length ? (
          <p className="fieldError">Missing: {claim.missing_required_document_types.map(documentLabel).join(", ")}</p>
        ) : null}
      </section>

      {!approved ? <section className="panel">
        <h2>Extracted Fields</h2>
        {!report?.extracted_fields.length ? <p>No extracted fields are available yet.</p> : null}
        {report?.documents.map((document) => (
          <div className="evidenceGroup" key={document.id}>
            <h3>{documentLabel(document.doc_type)}</h3>
            {(fieldsByDocument.get(document.id) ?? []).map((field) => (
              <div className="fieldRow" key={field.id}>
                <span>{field.field_name}</span>
                <strong>{field.field_value || "Empty or unclear"}</strong>
                <span>Confidence: {field.confidence ?? "Not available"}</span>
                <span>Lines: {parseLineRefs(field.supporting_line_refs).join(", ") || "Not available"}</span>
                <StatusBadge status={field.validation_status ?? "unclear"} />
              </div>
            ))}
          </div>
        ))}
      </section> : null}

      {!approved ? <section className="panel">
        <h2>Cross-Document Comparison</h2>
        {!comparisonRules(report?.rule_results ?? []).length ? <p>Run verification to see comparison results.</p> : null}
        <div className="comparisonTable">
          {comparisonRules(report?.rule_results ?? []).map((rule) => (
            <div key={rule.id}>
              <span>{rule.rule_name.split("_").join(" ")}</span>
              <StatusBadge status={outcomeLabel(rule.result)} />
              <code>{rule.details ?? "No details"}</code>
              <span>{formatDateTime(rule.evaluated_at)}</span>
            </div>
          ))}
        </div>
      </section> : null}
    </div>
  );
}
