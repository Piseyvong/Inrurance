import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { correctField, officerDecision, submitReview } from "../api/review";
import { getVerification } from "../api/verification";
import { Alert } from "../components/Alert";
import { PageHeader } from "../components/PageHeader";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import type { VerificationReport } from "../types/api";
import { documentLabel } from "../utils/documents";

export function OfficerReviewPage() {
  const claimId = useClaimIdParam();
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [form, setForm] = useState({
    action: "review_note",
    fieldId: "",
    correctedValue: "",
    details: ""
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!claimId) return;
    getVerification(claimId).then(setReport).catch(() => setReport(null));
  }, [claimId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!claimId) return;
    setLoading(true);
    setError(null);
    try {
      const selectedField = report?.extracted_fields.find((field) => String(field.id) === form.fieldId);
      const details = [
        selectedField ? `field=${selectedField.field_name}` : null,
        form.correctedValue ? `corrected_value=${form.correctedValue}` : null,
        form.details ? `note=${form.details}` : null
      ]
        .filter(Boolean)
        .join("; ");
      if(form.action === "correct_extracted_value" && selectedField && form.correctedValue){
        await correctField(selectedField.document_id, selectedField.id, form.correctedValue);
      } else await submitReview(claimId, {
        actor: "claims_officer",
        action: form.action,
        details: details || null
      });
      setMessage("Review action written to the audit log.");
      setForm({ ...form, correctedValue: "", details: "" });
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Could not submit review action.");
    } finally {
      setLoading(false);
    }
  }

  async function decide(action:string){if(!claimId)return;const reason=form.details.trim()||`Officer ${action} after evidence review`;try{const result=await officerDecision(claimId,action,reason,form.correctedValue?Number(form.correctedValue):undefined);setMessage(`Human decision recorded: ${result.status}.`);}catch(e){setError(e instanceof Error?e.message:"Decision failed");}}

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  return (
    <div className="pageStack">
      <PageHeader title={`Claim ${claimId} Officer Review`} eyebrow="Human Review">
        <Link className="secondaryButton" to="/officer">
          Officer Portal
        </Link>
        <Link className="secondaryButton" to={`/claims/${claimId}/audit`}>
          Audit History
        </Link>
      </PageHeader>
      <Alert>
        This portal is for officer review only. Auto-approval, when eligible, is handled by deterministic rules before claims reach this queue.
      </Alert>
      {message ? <Alert tone="success">{message}</Alert> : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <form className="formPanel" onSubmit={submit}>
        <label>
          Review Action
          <select value={form.action} onChange={(event) => setForm({ ...form, action: event.target.value })}>
            <option value="review_note">Add Review Note</option>
            <option value="correct_extracted_value">Correct Extracted Value</option>
            <option value="mark_document_unreadable">Mark Document Unreadable</option>
            <option value="request_additional_document">Request Another Document</option>
          </select>
        </label>
        <label>
          Field
          <select value={form.fieldId} onChange={(event) => setForm({ ...form, fieldId: event.target.value })}>
            <option value="">No Field Selected</option>
            {report?.extracted_fields.map((field) => {
              const document = report.documents.find((item) => item.id === field.document_id);
              return (
                <option key={field.id} value={field.id}>
                  {document ? documentLabel(document.doc_type) : "Document"} · {field.field_name}
                </option>
              );
            })}
          </select>
        </label>
        <label>
          Corrected Value
          <input value={form.correctedValue} onChange={(event) => setForm({ ...form, correctedValue: event.target.value })} />
        </label>
        <label>
          Review Note
          <textarea value={form.details} onChange={(event) => setForm({ ...form, details: event.target.value })} />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Writing..." : "Write to Audit Log"}
        </button>
      </form>
      <section className="panel"><h2>Human decision authority</h2><p>These actions create a persisted decision and audit event. Risk screening never rejects a claim automatically.</p><div className="heroActions"><button type="button" onClick={()=>void decide("approve")}>Approve</button><button type="button" className="secondaryButton" onClick={()=>void decide("request_documents")}>Request documents</button><button type="button" className="secondaryButton" onClick={()=>void decide("investigate")}>Escalate investigation</button><button type="button" className="secondaryButton" onClick={()=>void decide("reject")}>Reject / not covered</button></div></section>
    </div>
  );
}
