import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { completeFilenameDemo, getClaim, uploadClaimDocument } from "../api/claims";
import { extractDocumentFields, getOcrRuns, processDocument } from "../api/documents";
import { Alert } from "../components/Alert";
import { DocumentCard } from "../components/DocumentCard";
import { PageHeader } from "../components/PageHeader";
import { ProgressTracker } from "../components/ProgressTracker";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import type { ClaimWithDocuments, DocumentRecord, DocumentType, OCRRun } from "../types/api";
import { getDocumentByType } from "../utils/documents";
import { saveRecentClaim } from "../utils/recentClaims";

export function ClaimDocumentsPage() {
  const claimId = useClaimIdParam();
  const navigate = useNavigate();
  const [claim, setClaim] = useState<ClaimWithDocuments | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Partial<Record<DocumentType, File>>>({});
  const [ocrRuns, setOcrRuns] = useState<Record<number, OCRRun | undefined>>({});
  const [extractionStatus, setExtractionStatus] = useState<Record<number, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!claimId) return;
    const nextClaim = await getClaim(claimId);
    setClaim(nextClaim);
    saveRecentClaim(nextClaim);
    const runEntries = await Promise.all(
      nextClaim.documents.map(async (document) => {
        const runs = await getOcrRuns(document.id).catch(() => []);
        return [document.id, runs[0]] as const;
      })
    );
    setOcrRuns(Object.fromEntries(runEntries));
  }

  useEffect(() => {
    refresh().catch((apiError: Error) => setError(apiError.message));
  }, [claimId]);

  async function upload(docType: DocumentType) {
    if (!claimId || !selectedFiles[docType]) return;
    setBusyKey(`upload-${docType}`);
    setError(null);
    try {
      await uploadClaimDocument(claimId, docType, selectedFiles[docType]!);
      await completeFilenameDemo(claimId);
      setSelectedFiles({ ...selectedFiles, [docType]: undefined });
      await refresh();
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
    try {
      for (const required of missing) {
        await uploadClaimDocument(claimId, required.type, selectedFiles[required.type]!);
      }
      await completeFilenameDemo(claimId);
      setSelectedFiles({});
      await refresh();
      navigate(`/claims/${claimId}/verification`);
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Unable to upload all documents.");
    } finally {
      setBusyKey(null);
    }
  }

  async function continueToVerification() {
    if (!claimId) return;
    setBusyKey("continue");
    setError(null);
    try {
      await completeFilenameDemo(claimId);
      navigate(`/claims/${claimId}/verification`);
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Unable to continue.");
    } finally {
      setBusyKey(null);
    }
  }

  async function process(document: DocumentRecord) {
    setBusyKey(`process-${document.id}`);
    setError(null);
    try {
      const run = await processDocument(document.id);
      setOcrRuns((current) => ({ ...current, [document.id]: run }));
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Processing failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function extract(document: DocumentRecord) {
    setBusyKey(`extract-${document.id}`);
    setError(null);
    try {
      await extractDocumentFields(document.id);
      setExtractionStatus((current) => ({ ...current, [document.id]: "completed" }));
    } catch (apiError) {
      setExtractionStatus((current) => ({ ...current, [document.id]: "failed" }));
      setError(apiError instanceof Error ? apiError.message : "Extraction failed.");
    } finally {
      setBusyKey(null);
    }
  }

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  return (
    <div className="pageStack">
      <PageHeader title={`Claim ${claimId} Documents`} eyebrow="Claimant Intake">
        {claim?.document_completeness.is_complete ? <button type="button" className="secondaryButton" disabled={Boolean(busyKey)} onClick={() => void continueToVerification()}>
          Go to Verification
        </button> : <span className="sectionNote">Upload all required documents to continue</span>}
      </PageHeader>
      {claim ? <ProgressTracker claim={claim} /> : null}
      <Alert tone="warning">Use synthetic or anonymised documents only.</Alert>
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
              ocrRun={document ? ocrRuns[document.id] : undefined}
              selectedFile={selectedFiles[required.type]}
              extractionStatus={document ? extractionStatus[document.id] : undefined}
              busy={Boolean(busyKey)}
              onSelectFile={(docType, file) => setSelectedFiles({ ...selectedFiles, [docType]: file ?? undefined })}
              onUpload={upload}
              onProcess={process}
              onExtract={extract}
            />
          );
        })}
      </div>
      {claim ? <div className="formFooter documentUploadFooter">
        <span>{claim.document_completeness.is_complete ? "All required documents are uploaded." : "Select every required file, then upload them together."}</span>
        {claim.document_completeness.is_complete ? (
          <button type="button" disabled={Boolean(busyKey)} onClick={() => void continueToVerification()}>Continue to Verification</button>
        ) : (
          <button type="button" disabled={Boolean(busyKey)} onClick={() => void uploadAllAndContinue()}>
            {busyKey === "upload-all" ? "Uploading documents…" : "Upload all and continue to verification"}
          </button>
        )}
      </div> : null}
    </div>
  );
}
