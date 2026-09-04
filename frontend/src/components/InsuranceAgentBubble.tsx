import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { askInsuranceAgent, requestConsultation, type AgentAction, type ConsultationPayload } from "../api/chat";
import { session } from "../api/portal";
import { ArrowRightIcon, CloseIcon, LayersIcon } from "./icons";

type Message = { sender: "agent" | "user"; text: string; actions?: AgentAction[] };
const STORAGE_KEY = "insuranceAgentConversation";
const GREETING: Message = { sender: "agent", text: "Hi — សួស្តី! I’m your Insurance AI Agent. How can I help you with insurance today?" };

function savedMessages(): Message[] {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if (Array.isArray(value)) return value;
  } catch {
    // Start a new conversation if stored browser data is invalid.
  }
  return [GREETING];
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
      setMessages((current) => [...current, { sender: "agent", text: result.reply, actions: result.actions }]);
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

  if (hidden) return null;
  return <>
    <button className="chatLauncher" type="button" onClick={() => setOpen((value) => !value)} aria-label={open ? "Close Insurance AI Agent" : "Open Insurance AI Agent"} aria-expanded={open}><span className="chatPulse" /><LayersIcon size={22} /></button>
    {open && <aside className="chatPanel" aria-label="Insurance AI Agent" aria-live="polite">
      <header><div><span><LayersIcon size={18} /></span><div><strong>Insurance AI Agent</strong><small><i />{authenticated ? "Customer mode" : "Guest mode"}</small></div></div><button type="button" onClick={() => setOpen(false)} aria-label="Close Agent"><CloseIcon size={18} /></button></header>
      <div className="agentIntro"><strong>How can I help you?</strong><span>{authenticated ? "Ask about your policies or claims." : "Ask general insurance questions in English or Khmer."}</span></div>
      <div className="chatMessages">
        {messages.map((message, index) => <div key={index} className={message.sender}><span>{message.text}</span>{message.actions?.map(renderAction)}</div>)}
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
