import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { portal, startPortalClaim } from "../api/portal";
import { Alert } from "../components/Alert";
import { StatusBadge } from "../components/StatusBadge";

export function CustomerPortalPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState("");
  const navigate = useNavigate();
  useEffect(() => { portal().then((value) => { setData(value); setSelected(String(value.policies[0]?.id || "")); }).catch((apiError) => setError(apiError.message)); }, []);
  async function submit(event: FormEvent) { event.preventDefault(); try { const claim = await startPortalClaim({ policy_id: Number(selected) }); navigate(`/claims/${claim.id}/documents`); } catch (apiError) { setError(apiError instanceof Error ? apiError.message : "Unable to start claim"); } }
  if (!data) return <div className="pageStack">{error ? <Alert tone="danger">{error}</Alert> : <p>Loading your portal...</p>}</div>;
  return <div className="pageStack portalPage"><header className="portalHero"><div><p className="landingEyebrow">Customer portal</p><h1>Hello, {data.user.full_name}.</h1><p>Your policies and claims are securely scoped to this account.</p></div></header>{error ? <Alert tone="danger">{error}</Alert> : null}<section className="portalGrid"><article className="panel"><h2>My Policies</h2>{data.policies.map((policy: any) => <div className="portalRow" key={policy.id}><div><strong>{policy.product.name}</strong><span>{policy.policy_number} - version {policy.product.version}</span></div><StatusBadge status={policy.status}/></div>)}</article><article className="panel"><h2>My Claims</h2>{data.claims.length ? data.claims.map((claim: any) => <Link className="portalRow" key={claim.id} to={`/claims/${claim.id}/documents`}><div><strong>Claim #{claim.id}</strong><span>{claim.type} - {claim.amount ? `$${claim.amount}` : "Awaiting document extraction"}</span></div><StatusBadge status={claim.status}/></Link>) : <p>No claims yet.</p>}</article></section><section className="panel"><h2>Start a Claim</h2><p>Select an owned policy, then upload the required documents. Document AI extracts the claim details and prepares the summary after review.</p><form className="portalClaimForm" onSubmit={submit}><label>Policy<select value={selected} onChange={(event) => setSelected(event.target.value)}>{data.policies.map((policy: any) => <option value={policy.id} key={policy.id}>{policy.product.name} - {policy.policy_number}</option>)}</select></label><button type="submit">Continue to documents</button></form></section></div>;
}
