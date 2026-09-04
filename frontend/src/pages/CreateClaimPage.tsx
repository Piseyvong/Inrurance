import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createClaim, getClaim, uploadClaimDocument } from "../api/claims";
import { getPolicies } from "../api/policies";
import { runClaimPrecheck } from "../api/verification";
import { Alert } from "../components/Alert";
import { DocumentRequirementRow } from "../components/DocumentRequirementRow";
import { InboxIcon } from "../components/icons";
import { PageHeader } from "../components/PageHeader";
import { Stepper } from "../components/Stepper";
import { saveRecentClaim } from "../utils/recentClaims";
import type { ClaimWithDocuments, DocumentRecord, DocumentType, PolicyRequirements } from "../types/api";

const FLOW = ["Policy requirements", "Document upload", "OCR extraction", "Compliance check", "Decision"] as const;

export function CreateClaimPage() {
  const navigate = useNavigate();
  const [claimType, setClaimType] = useState("");
  const [policies, setPolicies] = useState<PolicyRequirements[]>([]);
  const [claim, setClaim] = useState<ClaimWithDocuments | null>(null);
  const [files, setFiles] = useState<Record<string, File | undefined>>({});
  const [uploadErrors, setUploadErrors] = useState<Record<string, string | undefined>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { getPolicies().then(setPolicies).catch((e: Error) => setError(e.message)); }, []);
  const policy = claim?.policy_requirements ?? policies.find((item) => item.claim_type === claimType);
  const requirements = policy?.required_documents ?? [];
  const missing = claim ? requirements.filter((item) => !claim.documents.some((doc) => doc.doc_type === item.type)) : requirements;
  const allSelected = Boolean(claim) && missing.length > 0 && missing.every((item) => files[item.type]);

  function selectFile(docType: DocumentType, file: File | null) {
    setFiles((current) => ({ ...current, [docType]: file ?? undefined }));
    setUploadErrors((current) => ({ ...current, [docType]: undefined }));
  }
  function status(docType: string) {
    if (claim?.documents.some((doc) => doc.doc_type === docType)) return "uploaded";
    if (busyKey === `upload-${docType}`) return "uploading";
    return uploadErrors[docType] ? "failed" : "missing";
  }
  async function upload(docType: string) {
    if (!claim || !files[docType]) return;
    setBusyKey(`upload-${docType}`);
    try {
      const record = await uploadClaimDocument(claim.id, docType, files[docType]!);
      setClaim((current) => current ? { ...current, documents: [...current.documents.filter((doc) => doc.doc_type !== docType), record as DocumentRecord] } : current);
      setFiles((current) => ({ ...current, [docType]: undefined }));
    } catch (e) { setUploadErrors((current) => ({ ...current, [docType]: e instanceof Error ? e.message : "Upload failed." })); }
    finally { setBusyKey(null); }
  }
  async function continueFlow(event: FormEvent) {
    event.preventDefault(); setError(null);
    if (!claimType) { setError("Select an insurance type."); return; }
    setSaving(true);
    try {
      if (!claim) {
        const created = await createClaim({ claim_type: claimType });
        localStorage.setItem("lastClaimId", String(created.id)); saveRecentClaim(created);
        setClaim(await getClaim(created.id)); return;
      }
      if (missing.some((item) => !files[item.type])) { setError("Select every missing required document before continuing."); return; }
      for (const item of missing) await uploadClaimDocument(claim.id, item.type, files[item.type]!);
      setClaim(await getClaim(claim.id)); await runClaimPrecheck(claim.id);
      navigate(`/claims/${claim.id}/verification`);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to continue the claim."); }
    finally { setSaving(false); setBusyKey(null); }
  }

  return <div className="pageStack claimIntakePage">
    <PageHeader title="Prepare an insurance claim" eyebrow="Claim workspace" />
    <Stepper steps={FLOW} activeIndex={claim ? 1 : 0} />
    {error ? <Alert tone="danger">{error}</Alert> : null}
    <form id="createClaimForm" className="panel claimTypePanel" onSubmit={continueFlow}>
      <label>Insurance or claim type<select value={claimType} disabled={Boolean(claim)} onChange={(e) => setClaimType(e.target.value)}><option value="">Choose the applicable coverage</option>{policies.map((item) => <option key={item.claim_type} value={item.claim_type}>{item.display_name}</option>)}</select></label>
      <p>The checklist and review rules come from the active admin policy configuration.</p>
    </form>
    <section className="claimWorkspace">
      <aside className="policyContext"><span>Matched policy</span><strong>{policy?.display_name ?? "Not selected"}</strong><p>{policy?.description ?? "Choose a claim type to retrieve its requirements."}</p>{policy ? <dl><div><dt>Policy version</dt><dd>{policy.version}</dd></div><div><dt>Minimum OCR</dt><dd>{Math.round(policy.minimum_ocr_confidence * 100)}%</dd></div><div><dt>Auto-approval limit</dt><dd>{policy.auto_approval_threshold ?? "Not enabled"} {policy.auto_approval_threshold ? policy.currency : ""}</dd></div></dl> : null}</aside>
      <div className="panel documentsRequired"><div className="sectionHeading"><div><h2>Required evidence</h2><p>Upload the exact evidence listed by the policy.</p></div>{claim ? <span className="sectionNote">{requirements.length - missing.length} of {requirements.length} uploaded</span> : null}</div>
        {!policy ? <div className="emptyState"><span className="emptyStateIcon"><InboxIcon size={24}/></span><h3>No claim type selected</h3><p>Requirements appear after you select coverage.</p></div> : <div className="docRequirementsList">{requirements.map((item) => <DocumentRequirementRow key={item.type} docType={item.type} title={item.title} purpose={`${item.description}${item.required_fields.length ? ` · Fields: ${item.required_fields.join(", ")}` : ""}`} selectedFile={files[item.type]} busy={busyKey === `upload-${item.type}`} disabled={!claim} uploadStatus={status(item.type)} uploadError={uploadErrors[item.type]} onSelectFile={selectFile} onUpload={upload}/>)}</div>}
      </div>
    </section>
    <div className="formFooter"><span>{claim ? "Upload evidence, then run OCR and policy checks" : "Start with the applicable policy"}</span><button type="submit" form="createClaimForm" disabled={saving}>{saving ? "Working…" : claim ? allSelected ? "Upload and review claim" : "Select missing documents" : "Load requirements"}</button></div>
  </div>;
}
