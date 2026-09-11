import type { ReactNode } from "react";
import { StatusBadge } from "./StatusBadge";
import { parseLineRefs } from "../utils/documents";

interface ExtractionFieldProps {
  name: string;
  value?: string | null;
  normalizedValue?: string | null;
  status?: string | null;
  confidence?: string | number | null;
  extractionMethod?: string | null;
  lineRefs?: string | null;
  source?: string | null;
  interpretation?: string | null;
  actions?: ReactNode;
}

function confidenceDisplay(value: ExtractionFieldProps["confidence"]) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return `${Math.round((numeric <= 1 ? numeric * 100 : numeric) * 10) / 10}%`;
}

function confidenceLabel(method?: string | null) {
  const value = (method ?? "").toLowerCase();
  if (value.includes("ocr") || value.includes("tesseract")) return "OCR confidence";
  if (value.includes("llm") || value.includes("openai") || value.includes("semantic")) return "Semantic extraction confidence";
  return "Extraction confidence";
}

export function ExtractionField({ name, value, normalizedValue, status, confidence, extractionMethod, lineRefs, source, interpretation, actions }: ExtractionFieldProps) {
  const displayValue = normalizedValue || value || ((status ?? "").toUpperCase() === "MISSING" ? "Missing" : "Unclear");
  const confidenceValue = confidenceDisplay(confidence);
  const lines = parseLineRefs(lineRefs).join(", ");
  const long = displayValue.length > 72 || Boolean(source && source.length > 100) || Boolean(interpretation && interpretation.length > 100);
  return <article className={`extractionField${long ? " long" : ""}`}>
    <div className="extractionFieldPrimary">
      <div><span className="extractionFieldName">{name.replace(/_/g," ")}</span><strong className="extractionFieldValue">{displayValue}</strong>{normalizedValue && value && normalizedValue !== value ? <small>Extracted text: {value}</small> : null}</div>
      <StatusBadge status={status || "unclear"}/>
    </div>
    {(confidenceValue || lines) ? <dl className="extractionMetadata">
      {confidenceValue ? <div><dt>{confidenceLabel(extractionMethod)}</dt><dd>{confidenceValue}</dd></div> : null}
      {lines ? <div><dt>OCR evidence lines</dt><dd>{lines}</dd></div> : null}
    </dl> : null}
    {source ? <details className="evidenceDisclosure"><summary>Show source evidence</summary><div><span>Raw OCR evidence</span><blockquote>{source}</blockquote></div></details> : null}
    {interpretation ? <div className="semanticInterpretation"><span>AI semantic interpretation</span><p>{interpretation}</p></div> : null}
    {actions ? <div className="extractionFieldActions">{actions}</div> : null}
  </article>;
}
