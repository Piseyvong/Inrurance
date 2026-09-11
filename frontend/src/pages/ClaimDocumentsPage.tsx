import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getClaim, uploadClaimDocument } from "../api/claims";
import { runClaimPrecheck } from "../api/verification";
import { Alert } from "../components/Alert";
import { DocumentCard } from "../components/DocumentCard";
import { PageHeader } from "../components/PageHeader";
import { ProgressTracker } from "../components/ProgressTracker";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import type { ClaimWithDocuments, DocumentType } from "../types/api";
import { getDocumentByType } from "../utils/documents";
import { saveRecentClaim } from "../utils/recentClaims";
import { BackButton } from "../components/BackButton";

export function ClaimDocumentsPage() {
  const claimId = useClaimIdParam();
  const navigate = useNavigate();
  const [claim, setClaim] = useState<ClaimWithDocuments | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Partial<Record<DocumentType, File>>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadSteps, setUploadSteps] = useState<Array<{ type: DocumentType; title: string; status: "pending" | "uploading" | "done" }> | null>(null);
  const [processingSteps, setProcessingSteps] = useState<Array<{ type: DocumentType; title: string; status: "pending" | "reading" | "done" }> | null>(null);
  const [finalizingTicks, setFinalizingTicks] = useState(0);

  async function refresh() {
    if (!claimId) return;
    const nextClaim = await getClaim(claimId);
    setClaim(nextClaim);
    saveRecentClaim(nextClaim);
  }

  useEffect(() => {
    refresh().catch((apiError: Error) => setError(apiError.message));
  }, [claimId]);

  async function startAutomaticProcessing() {
    if (!claimId) return;
    setBusyKey("automatic-processing");
    setError(null);
    const required = claim?.policy_requirements?.required_documents ?? [];
    setProcessingSteps(required.map((item) => ({ type: item.type, title: item.title, status: "pending" })));
    setFinalizingTicks(0);
    let precheckDone = false;
    async function animateReadingSteps() {
      // Real OCR + extraction for one document takes a few seconds (Tesseract
      // then Azure OpenAI), so this is paced to roughly track that instead of
      // finishing early and leaving a long silent "Finalizing" wait.
      const stepDelayMs = 1800;
      for (let index = 0; index < required.length; index += 1) {
        setProcessingSteps((steps) => steps?.map((step, i) => (i === index ? { ...step, status: "reading" } : step)) ?? steps);
        await new Promise((resolve) => setTimeout(resolve, stepDelayMs));
        setProcessingSteps((steps) => steps?.map((step, i) => (i === index ? { ...step, status: "done" } : step)) ?? steps);
      }
      // The backend has no incremental progress API, so once every document has
      // been "read" in the UI, keep counting a number up instead of freezing on
      // a bare "Finalizing…" while the real precheck call is still in flight.
      while (!precheckDone) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        setFinalizingTicks((n) => Math.min(n + 1, 9));
      }
    }
    try {
      // Run the real precheck alongside a staged reveal of each document so the
      // wait has visible, numbered progress instead of one opaque spinner - the
      // backend has no incremental progress API, so both settle before navigating.
      await Promise.all([runClaimPrecheck(claimId).finally(() => { precheckDone = true; }), animateReadingSteps()]);
      navigate(`/claims/${claimId}/verification`);
    } catch (apiError) {
      setError(apiError instanceof Error ? `Document processing failed. Please retry the affected document. ${apiError.message}` : "Document processing failed. Please retry the affected document.");
      await refresh();
    } finally {
      setBusyKey(null);
      setProcessingSteps(null);
      setFinalizingTicks(0);
    }
  }

  async function upload(docType: DocumentType) {
    if (!claimId || !selectedFiles[docType]) return;
    setBusyKey(`upload-${docType}`);
    setError(null);
    try {
      await uploadClaimDocument(claimId, docType, selectedFiles[docType]!);
      setSelectedFiles({ ...selectedFiles, [docType]: undefined });
      const nextClaim = await getClaim(claimId);
      setClaim(nextClaim);
      saveRecentClaim(nextClaim);
      if (nextClaim.document_completeness.is_complete) await startAutomaticProcessing();
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Upload failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function uploadAllAndContinue() {
    if (!claimId || !claim) return;
    const missing = (claim.policy_requirements?.required_documents ?? []).filter((required) => !getDocumentByType(claim.documents, required.type));
    const unselected = missing.filter((required) => !selectedFiles[required.type]);
    if (unselected.length) {
      setError(`Select a file for every missing document before uploading: ${unselected.map((item) => item.title).join(", ")}.`);
      return;
    }
    setBusyKey("upload-all");
    setError(null);
    setUploadSteps(missing.map((required) => ({ type: required.type, title: required.title, status: "pending" })));
    try {
      for (let index = 0; index < missing.length; index += 1) {
        const required = missing[index];
        setUploadSteps((steps) => steps!.map((step, i) => (i === index ? { ...step, status: "uploading" } : step)));
        await uploadClaimDocument(claimId, required.type, selectedFiles[required.type]!);
        setUploadSteps((steps) => steps!.map((step, i) => (i === index ? { ...step, status: "done" } : step)));
      }
      setSelectedFiles({});
      setUploadSteps(null);
      await startAutomaticProcessing();
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Unable to upload all documents.");
      setUploadSteps(null);
    } finally {
      setBusyKey(null);
    }
  }

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  // Reading steps fill 0-90%; once every document has been "read", the
  // remaining 90-99% ticks up slowly while the real backend call finishes -
  // this always shows a real, changing number instead of a static "Finalizing…".
  const readingDone = processingSteps ? processingSteps.filter((step) => step.status === "done").length : 0;
  const readingTotal = processingSteps?.length ?? 0;
  const processingPercent = processingSteps
    ? readingDone < readingTotal
      ? Math.round((readingDone / readingTotal) * 90)
      : Math.min(99, 90 + finalizingTicks)
    : null;
  const isFinalizing = Boolean(processingSteps) && readingDone === readingTotal && readingTotal > 0;

  return (
    <div className="pageStack">
      <BackButton to="/portal" label="Dashboard" />
      <PageHeader title={`Claim ${claimId} Documents`} eyebrow="Claimant Intake">
        <span className="sectionNote">{busyKey === "automatic-processing" ? "Processing documents…" : "Processing starts automatically after the last required upload."}</span>
      </PageHeader>
      {claim ? <ProgressTracker claim={claim} phase={processingSteps ? "Processing" : undefined} progress={processingPercent ?? undefined} /> : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <div className="documentsGrid">
        {(claim?.policy_requirements?.required_documents ?? []).map((required) => {
          const document = claim ? getDocumentByType(claim.documents, required.type) : undefined;
          return (
            <DocumentCard
              key={required.type}
              docType={required.type}
              title={required.title}
              description={required.description}
              document={document}
              selectedFile={selectedFiles[required.type]}
              busy={Boolean(busyKey)}
              onSelectFile={(docType, file) => setSelectedFiles({ ...selectedFiles, [docType]: file ?? undefined })}
              onUpload={upload}
            />
          );
        })}
      </div>
      {claim ? <div className={uploadSteps || processingSteps ? "formFooter documentUploadFooter" : "formFooter documentUploadFooter is-idle"}>
        <div className="documentUploadFooterStatus">
          {processingSteps ? (
            <>
              <div className="checklistProgress">
                <div className="checklistProgressBar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={processingPercent ?? 0}>
                  <div className="checklistProgressBarFill" style={{ width: `${processingPercent ?? 0}%` }} />
                </div>
                <span className="checklistProgressLabel">{isFinalizing ? `${processingPercent ?? 0}% · Finalizing…` : `${processingPercent ?? 0}%`}</span>
              </div>
              <ol className="uploadChecklist" aria-label="Document reading progress">
                {processingSteps.map((step, index) => (
                  <li key={step.type} className={step.status}>
                    <span className="uploadChecklistIndex" aria-hidden="true">{step.status === "done" ? "✓" : index + 1}</span>
                    <span className="uploadChecklistLabel">{step.title}</span>
                    <span className="uploadChecklistState">{step.status === "reading" ? "Reading…" : step.status === "done" ? "Complete" : "Waiting"}</span>
                  </li>
                ))}
              </ol>
            </>
          ) : uploadSteps ? (
            <ol className="uploadChecklist" aria-label="Upload progress">
              {uploadSteps.map((step, index) => (
                <li key={step.type} className={step.status}>
                  <span className="uploadChecklistIndex" aria-hidden="true">{step.status === "done" ? "✓" : index + 1}</span>
                  <span className="uploadChecklistLabel">{step.title}</span>
                  <span className="uploadChecklistState">{step.status === "uploading" ? "Uploading…" : step.status === "done" ? "Uploaded" : "Waiting"}</span>
                </li>
              ))}
            </ol>
          ) : (
            <span>{claim.document_completeness.is_complete ? "All required documents are uploaded. Processing starts automatically." : "Select every required file, then upload them together."}</span>
          )}
        </div>
        {!claim.document_completeness.is_complete && busyKey !== "automatic-processing" ? (
          <button type="button" disabled={Boolean(busyKey)} onClick={() => void uploadAllAndContinue()}>
            {uploadSteps ? `Uploading… (${uploadSteps.filter((step) => step.status === "done").length}/${uploadSteps.length})` : "Upload required documents"}
          </button>
        ) : null}
      </div> : null}
    </div>
  );
}
