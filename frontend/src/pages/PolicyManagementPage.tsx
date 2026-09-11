import { FormEvent, useEffect, useState } from "react";
import { archivePolicyDocument, customers, issueCustomerPolicy, policyDocumentUrl, policyDocuments, products, session, uploadPolicyDocument } from "../api/portal";
import { Alert } from "../components/Alert";
import { StatusBadge } from "../components/StatusBadge";

export function PolicyManagementPage() {
  const admin = session()?.role === "admin";
  const [items, setItems] = useState<any[]>([]);
  const [productItems, setProductItems] = useState<any[]>([]);
  const [customerItems, setCustomerItems] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [productId, setProductId] = useState("");
  const [name, setName] = useState("Health Standard 2026");
  const [code, setCode] = useState("HLT-STD-2026");
  const [version, setVersion] = useState("1.0");
  const [effectiveDate, setEffectiveDate] = useState("2026-01-01");
  const [status, setStatus] = useState("active");
  const [customerId, setCustomerId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [number, setNumber] = useState("HLT-2026-000123");
  const [start, setStart] = useState("2026-01-01");
  const [end, setEnd] = useState("2026-12-31");
  const [limit, setLimit] = useState("5000");

  const load = async () => {
    const [documents, productList, customerList] = await Promise.all([policyDocuments(), products(), admin ? customers() : Promise.resolve([])]);
    setItems(documents);
    setProductItems(productList);
    setCustomerItems(customerList);
    setProductId((current) => current || String(productList[0]?.id || ""));
    setCustomerId((current) => current || String(customerList[0]?.id || ""));
    setTemplateId((current) => current || String(documents.find((item: any) => item.status === "active")?.id || ""));
  };

  useEffect(() => {
    void load().catch((e: Error) => setError(e.message));
  }, []);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !productId) {
      setError("Select a product and a PDF or DOCX policy document.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const data = new FormData();
      data.set("insurance_product_id", productId);
      data.set("policy_name", name);
      data.set("policy_code", code);
      data.set("version", version);
      data.set("effective_date", effectiveDate);
      data.set("language", "Khmer-English");
      data.set("status", status);
      data.set("file", file);
      await uploadPolicyDocument(data);
      setFile(null);
      setMessage("Policy version uploaded and indexed.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to upload policy document.");
    } finally {
      setSaving(false);
    }
  }

  async function issue(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const template = items.find((item) => String(item.id) === templateId);
      await issueCustomerPolicy({
        user_id: Number(customerId),
        insurance_product_id: template?.insurance_product_id,
        policy_template_id: Number(templateId),
        policy_number: number,
        start_date: start,
        end_date: end,
        coverage_limit: limit ? Number(limit) : null,
        deductible: 0,
        currency: "USD"
      });
      setMessage("Customer policy issued and linked to this exact template version.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to issue customer policy.");
    } finally {
      setSaving(false);
    }
  }

  async function archive(id: number) {
    try {
      await archivePolicyDocument(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to archive policy version.");
    }
  }

  async function view(id: number) {
    try {
      const url = await policyDocumentUrl(id);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open policy document.");
    }
  }

  return (
    <div className="pageStack">
      <header className="portalHero">
        <div>
          <p className="landingEyebrow">Officer / Admin</p>
          <h1>Policy Management</h1>
          <p>Products, versioned policy wording, and customer-issued policies remain separate records.</p>
        </div>
      </header>
      {message ? <Alert tone="success">{message}</Alert> : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <section className="panel">
        <h2>Upload a policy version</h2>
        <form className="policyUploadForm" onSubmit={upload}>
          <label className="policyField wide">
            <span>Insurance product</span>
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">Select product</option>
              {productItems.map((product) => (
                <option key={product.id} value={product.id}>{product.name} · {product.type}</option>
              ))}
            </select>
          </label>
          <label className="policyField">
            <span>Policy name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="policyField">
            <span>Policy code</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
          <label className="policyField">
            <span>Version</span>
            <input value={version} onChange={(e) => setVersion(e.target.value)} />
          </label>
          <label className="policyField">
            <span>Effective date</span>
            <input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
          </label>
          <label className="policyField">
            <span>Status</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </label>
          <label className="policyField wide">
            <span>Policy document (PDF or DOCX)</span>
            <input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <div className="policyUploadFooter">
            <span className="policyUploadHint">Uploading indexes the wording and pins claim decisions to this exact version.</span>
            <button disabled={saving}>{saving ? "Indexing policy…" : "Upload policy"}</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Policy version history</h2>
        {items.length === 0 ? (
          <p>No policy documents uploaded yet.</p>
        ) : (
          items.map((item) => (
            <div className="portalRow" key={item.id}>
              <div>
                <strong>{item.policy_name}</strong>
                <span>{item.policy_code} · Version {item.version} · {item.product_category} · Effective {item.effective_date} · {item.chunk_count} indexed sections</span>
              </div>
              <StatusBadge status={item.status} />
              <div className="actionRow">
                <button type="button" className="secondaryButton" onClick={() => void view(item.id)}>View document</button>
                {item.status !== "archived" ? <button type="button" className="secondaryButton" onClick={() => void archive(item.id)}>Archive</button> : null}
              </div>
            </div>
          ))
        )}
      </section>

      {admin ? (
        <section className="panel">
          <h2>Issue policy to customer</h2>
          <form className="portalAgent" onSubmit={issue}>
            <select aria-label="Customer" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              {customerItems.map((customer) => (
                <option key={customer.id} value={customer.id}>{customer.full_name} · {customer.email}</option>
              ))}
            </select>
            <select aria-label="Policy template" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              <option value="">Select active policy version</option>
              {items.filter((item) => item.status === "active").map((item) => (
                <option key={item.id} value={item.id}>{item.policy_name} · {item.version}</option>
              ))}
            </select>
            <input aria-label="Issued policy number" value={number} onChange={(e) => setNumber(e.target.value)} />
            <input aria-label="Coverage start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            <input aria-label="Coverage end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            <input aria-label="Coverage limit" type="number" value={limit} onChange={(e) => setLimit(e.target.value)} />
            <button disabled={saving || !customerId || !templateId}>Issue customer policy</button>
          </form>
        </section>
      ) : null}
    </div>
  );
}