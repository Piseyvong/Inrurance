import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { addOfficerNote, correctField, getOfficerClaimWorkspace, getOfficerDocumentBlob, officerDecision } from "../api/review";
import { Alert } from "../components/Alert";
import { BackButton } from "../components/BackButton";
import { ExtractionField } from "../components/ExtractionField";
import { DownloadIcon, FileTextIcon } from "../components/icons";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import { documentLabel, formatDateTime } from "../utils/documents";
import { verificationRuleDetail } from "../utils/verification";

const tabs = ["Original Document", "Clean OCR", "Raw OCR", "Extracted Fields", "Verification"] as const;

export function OfficerReviewPage() {
  const claimId = useClaimIdParam();
  const [data, setData] = useState<any>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tab, setTab] = useState<(typeof tabs)[number]>("Original Document");
  const [preview, setPreview] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [corrections, setCorrections] = useState<Record<number, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => { if (!claimId) return; const result = await getOfficerClaimWorkspace(claimId); setData(result); setSelectedId((current) => current ?? result.documents[0]?.id ?? null); };

  useEffect(() => { void load().catch((e: Error) => setError(e.message)); }, [claimId]);
  const selected = useMemo(() => data?.documents.find((item: any) => item.id === selectedId), [data, selectedId]);
  const visibleFields = useMemo(() => selected?.fields.filter((field: any) => !["NOT_APPLICABLE", "not_applicable"].includes(field.validation_status)) ?? [], [selected]);

  useEffect(() => {
    if (!claimId || !selectedId || tab !== "Original Document") return;
    let active = true; let url: string | null = null;
    getOfficerDocumentBlob(claimId, selectedId).then((value) => { url = value; if (active) setPreview(value); else URL.revokeObjectURL(value); }).catch((e: Error) => setError(e.message));
    return () => { active = false; if (url) URL.revokeObjectURL(url); setPreview(null); };
  }, [claimId, selectedId, tab]);

  async function saveNote(event: FormEvent) { event.preventDefault(); if (!claimId || !note.trim()) return; setBusy(true); try { await addOfficerNote(claimId, note); setNote(""); setMessage("Internal note saved and audited."); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to save note."); } finally { setBusy(false); } }
  async function saveCorrection(field: any) { if (!corrections[field.id]?.trim()) return; setBusy(true); try { await correctField(selected.id, field.id, corrections[field.id]); setMessage("Candidate correction saved without changing the original OCR evidence."); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to save correction."); } finally { setBusy(false); } }
  async function act(action: string) { if (!claimId) return; setBusy(true); try { const reason = note.trim() || `Officer action: ${action}`; await officerDecision(claimId, action, reason); setMessage("Officer action persisted."); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Officer action failed."); } finally { setBusy(false); } }
  async function download() { if (!claimId || !selected) return; try { const url = await getOfficerDocumentBlob(claimId, selected.id, true); const anchor = document.createElement("a"); anchor.href = url; anchor.download = selected.original_filename || "claim-document"; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (e) { setError(e instanceof Error ? e.message : "Download failed."); } }

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;
  if (!data) return <div className="pageStack">{error ? <Alert tone="danger">{error}</Alert> : <p>Loading claim review workspace…</p>}</div>;

  return <div className="pageStack">
    <BackButton to="/officer" label="Claims queue" />
    <PageHeader title={`${data.claim.claim_number} Review`} eyebrow="Officer claim workspace">
      <Link className="secondaryButton" to={`/claims/${claimId}/audit`}><FileTextIcon size={17}/>Audit history</Link>
    </PageHeader>
    {message ? <Alert tone="success">{message}</Alert> : null}{error ? <Alert tone="danger">{error}</Alert> : null}
    <section className="officerCaseGrid">
      <aside className="panel officerClaimFacts"><h2>Claim information</h2><dl><div><dt>Customer</dt><dd>{data.customer?.full_name || "Unavailable"}</dd></div><div><dt>Policy</dt><dd>{data.policy?.policy_number || "Unavailable"}</dd></div><div><dt>Product</dt><dd>{data.product?.name || "Unavailable"}</dd></div><div><dt>Claim type</dt><dd>{data.claim.claim_type}</dd></div><div><dt>Submitted</dt><dd>{formatDateTime(data.claim.created_at)}</dd></div><div><dt>Amount</dt><dd>{data.claim.requested_amount ?? "Pending"} {data.claim.currency}</dd></div><div><dt>Status</dt><dd><StatusBadge status={data.claim.workflow_status}/></dd></div></dl><h3>Evidence</h3><div className="officerDocList">{data.documents.map((doc: any) => <button key={doc.id} type="button" className={selectedId === doc.id ? "active" : ""} onClick={() => { setSelectedId(doc.id); setTab("Original Document"); }}><strong>{documentLabel(doc.doc_type)}</strong><span>{doc.original_filename}</span><small>OCR {doc.ocr_status} · Extract {doc.extraction_status}</small></button>)}</div></aside>
      <main className="panel officerEvidence"><div className="sectionHeading"><div><h2>{selected ? documentLabel(selected.doc_type) : "Original evidence"}</h2><p>{selected?.original_filename}</p></div>{selected ? <button className="secondaryButton" type="button" onClick={() => void download()}><DownloadIcon size={17}/>Download</button> : null}</div>{selected ? <><div className="evidenceTabs" role="tablist" aria-label="Document evidence views">{tabs.map((item) => <button key={item} type="button" role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item}</button>)}</div><div className="evidenceTabBody">{tab === "Original Document" && (preview ? (selected.mime_type === "application/pdf" ? <iframe title="Original customer document" src={preview}/> : <img src={preview} alt={`Original ${selected.original_filename}`}/>) : <p>Loading authorized original evidence…</p>)}{tab === "Clean OCR" ? <pre>{selected.ocr?.cleaned_text || "Clean OCR is not available."}</pre> : null}{tab === "Raw OCR" ? <pre>{selected.ocr?.raw_text || "Raw Tesseract OCR is not available."}</pre> : null}{tab === "Extracted Fields" ? <div className="extractionList">{visibleFields.length ? visibleFields.map((field: any) => <ExtractionField key={field.id} name={field.field_name} value={field.extracted_value} normalizedValue={field.normalized_value} status={field.validation_status} confidence={field.confidence} extractionMethod={field.extraction_method} lineRefs={field.supporting_line_refs} source={field.source_text ?? field.original_ocr_value} interpretation={field.semantic_reason} actions={<div className="correctionControls"><label><span>Officer correction</span><input aria-label={`Correct ${field.field_name}`} value={corrections[field.id] ?? field.corrected_value ?? ""} onChange={(e) => setCorrections({ ...corrections, [field.id]: e.target.value })} placeholder="Enter corrected value"/></label><button type="button" disabled={busy || !corrections[field.id]?.trim()} onClick={() => void saveCorrection(field)}>Save correction</button></div>}/> ) : <p>No applicable fields were extracted for this document.</p>}</div> : null}{tab === "Verification" ? <div className="verificationRuleList">{selected.verification.length ? selected.verification.map((rule: any) => <div className={`verificationRule rule-${rule.result}`} key={rule.name}><div><strong>{rule.name.replace(/_/g, " ")}</strong>{verificationRuleDetail(rule) ? <span>{verificationRuleDetail(rule)}</span> : null}</div><StatusBadge status={rule.result}/></div>) : <p>No document-specific checks are available.</p>}</div> : null}</div></> : <p>No documents have been uploaded.</p>}</main>
      <aside className="panel officerAnalysis"><h2>Review panel</h2><div className="metricCard"><span>OCR confidence</span><strong>{selected?.ocr?.confidence != null && Number(selected.ocr.confidence) > 0 ? `${Math.round(selected.ocr.confidence * 100)}%` : "Not available"}</strong></div><h3>Risk flags</h3><StatusBadge status={data.risk?.band || "not screened"}/>{data.risk?.checks?.map((check: any) => <div className="riskCheck" key={check.name}><strong>{check.name.replace(/_/g, " ")}</strong><span>{check.evidence?.summary}</span></div>)}<h3>Internal notes</h3><form onSubmit={saveNote}><textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an auditable officer note"/><button disabled={busy || !note.trim()}>Add note</button></form>{data.notes.map((item: any) => <div className="noteCard" key={item.id}><p>{item.note}</p><small>{item.officer} · {formatDateTime(item.created_at)}</small></div>)}<h3>Officer actions</h3><div className="officerActions"><button type="button" disabled={busy} onClick={() => void act("request_documents")}>Request information</button><button type="button" disabled={busy} onClick={() => void act("investigate")}>Escalate</button><button type="button" disabled={busy} onClick={() => void act("close")}>Complete review</button></div></aside>
    </section>
  </div>;
}
