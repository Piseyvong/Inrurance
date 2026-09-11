import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { askInsuranceAgent, requestConsultation, type AgentAction, type ClaimStatusData, type ConsultationPayload, type DocumentChecklistItem, type PolicyInfoData, type StructuredData } from "../api/chat";
import { session } from "../api/portal";
import { ArrowRightIcon, CloseIcon, LayersIcon } from "./icons";

type Message = { sender: "agent" | "user"; text: string; actions?: AgentAction[]; structuredData?: StructuredData };

const STORAGE_KEY = "insuranceAgentConversation";
const GREETING: Message = { sender: "agent", text: "Hi — សួស្តី! I'm your Insurance AI Agent. How can I help you with insurance today?" };

function savedMessages(): Message[] {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if (Array.isArray(value)) return value;
  } catch {
    // Start a new conversation if stored browser data is invalid.
  }
  return [GREETING];
}

// Status badge configuration
const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  approved: { color: "#15803d", bg: "#dcfce7", label: "Approved" },
  pending: { color: "#92400e", bg: "#fef3c7", label: "Pending" },
  rejected: { color: "#b91c1c", bg: "#fee2e2", label: "Rejected" },
  human_review_required: { color: "#1e40af", bg: "#dbeafe", label: "Under Review" },
  waiting_for_documents: { color: "#6b21a8", bg: "#f3e8ff", label: "Awaiting Docs" },
  processing: { color: "#0369a1", bg: "#e0f2fe", label: "Processing" },
};

function getStatusConfig(status: string) {
  return STATUS_CONFIG[status] || { color: "#475569", bg: "#f1f5f9", label: status.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()) };
}

// Status Badge Component
function StatusBadge({ status }: { status: string }) {
  const config = getStatusConfig(status);
  return (
    <span className="statusBadge" style={{ background: config.bg, color: config.color }}>
      {config.label}
    </span>
  );
}

// Document Checklist Component
function DocumentChecklist({ documents }: { documents: DocumentChecklistItem[] }) {
  if (!documents || documents.length === 0) return null;
  return (
    <div className="documentChecklist">
      <strong>Required Documents:</strong>
      <ul>
        {documents.map((doc, i) => (
          <li key={i} className={doc.submitted ? "submitted" : "pending"}>
            <span className="checkIcon">{doc.submitted ? "✓" : "○"}</span>
            <span>{doc.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Claim Status Card Component
function ClaimStatusCard({ claim }: { claim: ClaimStatusData }) {
  return (
    <div className="claimStatusCard">
      <div className="claimHeader">
        <span className="claimId">#{claim.id}</span>
        <StatusBadge status={claim.status} />
      </div>
      <div className="claimDetails">
        <div className="detailRow">
          <span className="label">Type</span>
          <span className="value">{claim.claim_type}</span>
        </div>
        {claim.amount !== undefined && claim.amount !== null && (
          <div className="detailRow">
            <span className="label">Amount</span>
            <span className="value">${claim.amount.toLocaleString()}</span>
          </div>
        )}
      </div>
      {claim.documents && <DocumentChecklist documents={claim.documents} />}
      {claim.next_steps && claim.next_steps.length > 0 && (
        <div className="nextSteps">
          <strong>Next Steps:</strong>
          <ul>
            {claim.next_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Policy Info Card Component
function PolicyInfoCard({ policy }: { policy: PolicyInfoData }) {
  return (
    <div className="policyInfoCard">
      <div className="policyHeader">
        <span className="policyNumber">{policy.policy_number}</span>
        <StatusBadge status={policy.status} />
      </div>
      <div className="policyDetails">
        <div className="detailRow">
          <span className="label">Product</span>
          <span className="value">{policy.product_name}</span>
        </div>
        {policy.coverage_type && (
          <div className="detailRow">
            <span className="label">Coverage</span>
            <span className="value">{policy.coverage_type}</span>
          </div>
        )}
        {policy.end_date && (
          <div className="detailRow">
            <span className="label">Valid Until</span>
            <span className="value">{policy.end_date}</span>
          </div>
        )}
      </div>
      {policy.benefits && policy.benefits.length > 0 && (
        <div className="policyBenefits">
          <strong>Covered Benefits:</strong>
          <ul>
            {policy.benefits.map((benefit, i) => (
              <li key={i}>{benefit}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Message Parser - renders basic markdown-like formatting
function parseMessageText(text: string): ReactNode[] {
  const lines = text.split("\n");
  const elements: ReactNode[] = [];
  let inList = false;
  let listItems: string[] = [];
  let listType: "ul" | "ol" = "ul";

  function flushList() {
    if (listItems.length > 0) {
      const Tag = listType;
      elements.push(
        <Tag key={`list-${elements.length}`}>
          {listItems.map((item, i) => (
            <li key={i}>{formatInlineText(item)}</li>
          ))}
        </Tag>
      );
      listItems = [];
      inList = false;
    }
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim();

    // Headers
    if (trimmed.startsWith("## ")) {
      flushList();
      elements.push(<div key={i} className="headerText">{formatInlineText(trimmed.slice(3))}</div>);
      return;
    }
    if (trimmed.startsWith("### ")) {
      flushList();
      elements.push(<div key={i} className="headerText" style={{ fontSize: "0.88rem" }}>{formatInlineText(trimmed.slice(4))}</div>);
      return;
    }

    // Divider
    if (trimmed === "---" || trimmed === "***") {
      flushList();
      elements.push(<div key={i} className="divider" />);
      return;
    }

    // Unordered list
    if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      if (!inList || listType !== "ul") {
        flushList();
        inList = true;
        listType = "ul";
      }
      listItems.push(trimmed.slice(2));
      return;
    }

    // Ordered list
    const olMatch = trimmed.match(/^(\d+)\.\s+(.+)/);
    if (olMatch) {
      if (!inList || listType !== "ol") {
        flushList();
        inList = true;
        listType = "ol";
      }
      listItems.push(olMatch[2]);
      return;
    }

    // Empty line
    if (trimmed === "") {
      flushList();
      return;
    }

    // Regular text
    flushList();
    elements.push(<span key={i}>{formatInlineText(trimmed)}{" "}</span>);
  });

  flushList();
  return elements;
}

// Format inline text (bold, italic)
function formatInlineText(text: string): ReactNode {
  const parts: ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Bold
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    // Italic
    const italicMatch = remaining.match(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/);

    if (boldMatch && (!italicMatch || (boldMatch.index ?? 0) <= (italicMatch.index ?? 0))) {
      const idx = boldMatch.index ?? 0;
      if (idx > 0) parts.push(remaining.slice(0, idx));
      parts.push(<strong key={key++}>{boldMatch[1]}</strong>);
      remaining = remaining.slice(idx + boldMatch[0].length);
    } else if (italicMatch) {
      const idx = italicMatch.index ?? 0;
      if (idx > 0) parts.push(remaining.slice(0, idx));
      parts.push(<em key={key++}>{italicMatch[1]}</em>);
      remaining = remaining.slice(idx + italicMatch[0].length);
    } else {
      parts.push(remaining);
      break;
    }
  }

  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

export function InsuranceAgentBubble() {
  const location = useLocation();
  const authenticated = session()?.role === "customer";
  const hidden = location.pathname.startsWith("/officer") || location.pathname.startsWith("/admin");
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>(savedMessages);
  const [loading, setLoading] = useState(false);
  const [consultationOpen, setConsultationOpen] = useState(false);
  const [consultation, setConsultation] = useState<ConsultationPayload>({ name: "", email: "", phone: "", product_interest: "", preferred_time: "", question: "" });
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    if (typeof endRef.current?.scrollIntoView === "function") endRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages, open, consultationOpen]);

  async function send(text: string) {
    const value = text.trim();
    if (!value || loading) return;
    setMessages((current) => [...current, { sender: "user", text: value }]);
    setInput("");
    setLoading(true);
    try {
      const result = await askInsuranceAgent(value);
      setMessages((current) => [...current, { sender: "agent", text: result.reply, actions: result.actions, structuredData: result.structured_data ?? undefined }]);
    } catch (error) {
      setMessages((current) => [...current, { sender: "agent", text: error instanceof Error ? error.message : "The Insurance AI Agent is unavailable right now." }]);
    } finally {
      setLoading(false);
    }
  }

  async function submitConsultation(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const result = await requestConsultation(consultation);
      setMessages((current) => [...current, { sender: "agent", text: result.message }]);
      setConsultationOpen(false);
    } catch (error) {
      setMessages((current) => [...current, { sender: "agent", text: error instanceof Error ? error.message : "We could not save your request." }]);
    } finally {
      setLoading(false);
    }
  }

  function renderAction(action: AgentAction) {
    if (action.type === "link") {
      return <Link key={action.label} className="agentAction" to={action.href} onClick={() => setOpen(false)}>{action.label}</Link>;
    }
    return <button key={action.label} className="agentAction" type="button" onClick={() => setConsultationOpen(true)}>{action.label}</button>;
  }

  function renderStructuredData(data: StructuredData) {
    if (data.type === "claim_status" && data.claims) {
      return (
        <div className="structuredDataContainer">
          {data.claims.length === 1 ? (
            <ClaimStatusCard claim={data.claims[0]} />
          ) : (
            <div className="claimsList">
              {data.claims.map((claim) => (
                <ClaimStatusCard key={claim.id} claim={claim} />
              ))}
            </div>
          )}
        </div>
      );
    }
    if (data.type === "policy_info" && data.policies) {
      return (
        <div className="structuredDataContainer">
          {data.policies.length === 1 ? (
            <PolicyInfoCard policy={data.policies[0]} />
          ) : (
            <div className="policiesList">
              {data.policies.map((policy) => (
                <PolicyInfoCard key={policy.policy_number} policy={policy} />
              ))}
            </div>
          )}
        </div>
      );
    }
    return null;
  }

  if (hidden) return null;
  return <>
    <button className="chatLauncher" type="button" onClick={() => setOpen((value) => !value)} aria-label={open ? "Close Insurance AI Agent" : "Open Insurance AI Agent"} aria-expanded={open}><span className="chatPulse" /><LayersIcon size={22} /></button>
    {open && <aside className="chatPanel" aria-label="Insurance AI Agent" aria-live="polite">
      <header><div><span><LayersIcon size={18} /></span><div><strong>Insurance AI Agent</strong><small><i />{authenticated ? "Customer mode" : "Guest mode"}</small></div></div><button type="button" onClick={() => setOpen(false)} aria-label="Close Agent"><CloseIcon size={18} /></button></header>
      <div className="agentIntro"><strong>How can I help you?</strong><span>{authenticated ? "Ask about your policies or claims." : "Ask general insurance questions in English or Khmer."}</span></div>
      <div className="chatMessages">
        {messages.map((message, index) => (
          <div key={index} className={message.sender}>
            <div className="messageContent">{parseMessageText(message.text)}</div>
            {message.structuredData && renderStructuredData(message.structuredData)}
            {message.actions?.map(renderAction)}
          </div>
        ))}
        {consultationOpen && <form className="consultationForm" onSubmit={submitConsultation}>
          <strong>Request a consultation</strong>
          <input required aria-label="Name" placeholder="Your name" value={consultation.name} onChange={(event) => setConsultation({ ...consultation, name: event.target.value })} />
          <div><input type="email" aria-label="Email" placeholder="Email" value={consultation.email} onChange={(event) => setConsultation({ ...consultation, email: event.target.value })} /><input aria-label="Phone" placeholder="Phone" value={consultation.phone} onChange={(event) => setConsultation({ ...consultation, phone: event.target.value })} /></div>
          <input aria-label="Product interest" placeholder="Product of interest (optional)" value={consultation.product_interest} onChange={(event) => setConsultation({ ...consultation, product_interest: event.target.value })} />
          <input aria-label="Preferred time" placeholder="Preferred date/time (optional)" value={consultation.preferred_time} onChange={(event) => setConsultation({ ...consultation, preferred_time: event.target.value })} />
          <textarea aria-label="Question" placeholder="What would you like to discuss?" value={consultation.question} onChange={(event) => setConsultation({ ...consultation, question: event.target.value })} />
          <small>Provide either an email address or phone number.</small>
          <div><button type="button" className="secondary" onClick={() => setConsultationOpen(false)}>Cancel</button><button type="submit" disabled={loading}>Send request</button></div>
        </form>}
        {loading && !consultationOpen && <div className="agent">Thinking…</div>}
        <div ref={endRef} />
      </div>
      <div className="chatSuggestions">{(authenticated ? ["What policies do I have?", "What is my claim status?"] : ["តើ health insurance cover អ្វីខ្លះ?", "How do claims work?"]).map((text) => <button type="button" key={text} disabled={loading} onClick={() => void send(text)}>{text}</button>)}</div>
      <form onSubmit={(event) => { event.preventDefault(); void send(input); }}><label className="srOnly" htmlFor="global-agent-input">Ask Insurance AI Agent</label><input id="global-agent-input" value={input} disabled={loading} onChange={(event) => setInput(event.target.value)} placeholder="Ask in English or Khmer…" /><button type="submit" disabled={loading} aria-label="Send message"><ArrowRightIcon size={17} /></button></form>
    </aside>}
  </>;
}
