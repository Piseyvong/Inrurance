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
    try {
      await runClaimPrecheck(claimId);
      navigate(`/claims/${claimId}/verification`);
    } catch (apiError) {
      setError(apiError instanceof Error ? `Document processing failed. Please retry the affected document. ${apiError.message}` : "Document processing failed. Please retry the affected document.");
      await refresh();
    } finally {
      setBusyKey(null);
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
    try {
      for (const required of missing) {
        await uploadClaimDocument(claimId, required.type, selectedFiles[required.type]!);
      }
      setSelectedFiles({});
      await startAutomaticProcessing();
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Unable to upload all documents.");
    } finally {
      setBusyKey(null);
    }
  }

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  return (
    <div className="pageStack">
      <PageHeader title={`Claim ${claimId} Documents`} eyebrow="Claimant Intake">
        <BackButton to="/portal" label="Dashboard" />
        <span className="sectionNote">{busyKey === "automatic-processing" ? "Processing documents…" : "Processing starts automatically after the last required upload."}</span>
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
              selectedFile={selectedFiles[required.type]}
              processing={busyKey === "automatic-processing"}
              busy={Boolean(busyKey)}
              onSelectFile={(docType, file) => setSelectedFiles({ ...selectedFiles, [docType]: file ?? undefined })}
              onUpload={upload}
            />
          );
        })}
      </div>
      {claim ? <div className="formFooter documentUploadFooter">
        <span>{claim.document_completeness.is_complete ? "All required documents are uploaded. Processing starts automatically." : "Select every required file, then upload them together."}</span>
        {!claim.document_completeness.is_complete ? (
          <button type="button" disabled={Boolean(busyKey)} onClick={() => void uploadAllAndContinue()}>
            {busyKey === "upload-all" ? "Uploading documents…" : "Upload required documents"}
          </button>
        ) : null}
      </div> : null}
    </div>
  );
}
