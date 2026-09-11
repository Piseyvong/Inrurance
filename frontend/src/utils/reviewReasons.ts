import type { RuleResult } from "../types/api";
import { documentLabel } from "./documents";

/**
 * Translates the rules engine's machine-readable reason codes (e.g.
 * "valid_date_claim_form_incident_date") into short sentences a claims
 * handler can act on without knowing the rule names, grouped by what kind
 * of problem it is.
 */

export type ReasonTone = "good" | "warning" | "danger" | "neutral";
export type ReasonCategory = "conflict" | "missing" | "scan_quality" | "timing" | "other";

export interface ReviewReasonCard {
  key: string;
  text: string;
}

export interface ReviewReasonGroup {
  category: ReasonCategory;
  label: string;
  tone: ReasonTone;
  items: ReviewReasonCard[];
}

const CATEGORY_META: Record<ReasonCategory, { label: string; tone: ReasonTone }> = {
  conflict: { label: "Doesn't match", tone: "danger" },
  missing: { label: "Missing information", tone: "warning" },
  scan_quality: { label: "Scan quality too low", tone: "warning" },
  timing: { label: "Dates need a look", tone: "warning" },
  other: { label: "Other checks", tone: "neutral" }
};

const CATEGORY_ORDER: ReasonCategory[] = ["conflict", "missing", "scan_quality", "timing", "other"];

// Ordered longest-first so e.g. "medical_invoice" is matched before "invoice".
const KNOWN_DOC_TYPES = ["medical_invoice", "travel_itinerary", "incident_report", "claim_form", "medical_report", "invoice", "receipt"];

function fieldLabel(name: string): string {
  return name
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function splitDocType(remainder: string): { doc: string; rest: string } | null {
  for (const docType of KNOWN_DOC_TYPES) {
    if (remainder === docType) return { doc: docType, rest: "" };
    if (remainder.startsWith(`${docType}_`)) return { doc: docType, rest: remainder.slice(docType.length + 1) };
    if (remainder.endsWith(`_${docType}`)) return { doc: docType, rest: remainder.slice(0, -(docType.length + 1)) };
  }
  return null;
}

function parseDetails(raw: string | null | undefined): Record<string, unknown> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function fieldValueOf(value: unknown): string | undefined {
  if (value && typeof value === "object" && "field_value" in value) {
    const fieldValue = (value as { field_value?: unknown }).field_value;
    return typeof fieldValue === "string" && fieldValue ? fieldValue : undefined;
  }
  return undefined;
}

function categorize(reason: string, details: Record<string, unknown>): { category: ReasonCategory; text: string } {
  if (reason.startsWith("ocr_confidence_")) {
    const doc = documentLabel(reason.replace("ocr_confidence_", ""));
    const confidence = typeof details.confidence === "number" ? `${Math.round(details.confidence * 100)}%` : null;
    return {
      category: "scan_quality",
      text: confidence
        ? `${doc}: the scan is only ${confidence} readable (80% is needed to trust it automatically) — please check the original document.`
        : `${doc}: the scan quality could not be measured — please check the original document.`
    };
  }

  if (reason.startsWith("ocr_available_")) {
    const doc = documentLabel(reason.replace("ocr_available_", ""));
    return { category: "scan_quality", text: `${doc}: the scan hasn't finished or failed — please re-upload or check the file.` };
  }

  if (reason.startsWith("required_field_")) {
    const remainder = reason.replace("required_field_", "");
    const split = splitDocType(remainder);
    const doc = split ? documentLabel(split.doc) : "the document";
    const field = split ? fieldLabel(split.rest) : fieldLabel(remainder);
    return { category: "missing", text: `${doc}: ${field} was not found.` };
  }

  if (reason.startsWith("claim_")) {
    const remainder = reason.replace("claim_", "");
    const split = splitDocType(remainder);
    if (split) {
      const field = fieldLabel(split.rest || remainder);
      const doc = documentLabel(split.doc);
      const onFile = typeof details.claim === "string" ? details.claim : null;
      const onDoc = typeof details.document === "string" ? details.document : null;
      return {
        category: "conflict",
        text: onFile && onDoc
          ? `${field}: the claim record says "${onFile}", but the ${doc} says "${onDoc}" — please confirm which is correct.`
          : `${field} on the ${doc} doesn't match what's on file for this claim — please confirm which is correct.`
      };
    }
  }

  if (reason.startsWith("consistent_")) {
    const match = reason.match(/^consistent_(identity|reported_incident|policy_number|currency)_(.+)_vs_(.+)$/);
    if (match) {
      const [, kind, leftDoc, rightDoc] = match;
      const label = kind === "identity" ? "Name" : kind === "reported_incident" ? "Incident date" : kind === "policy_number" ? "Policy number" : "Currency";
      const leftValue = fieldValueOf(details.left);
      const rightValue = fieldValueOf(details.right);
      if (!leftValue || !rightValue) {
        return { category: "missing", text: `${label}: couldn't be compared between ${documentLabel(leftDoc)} and ${documentLabel(rightDoc)} because one is missing.` };
      }
      return { category: "conflict", text: `${label}: ${documentLabel(leftDoc)} says "${leftValue}", but ${documentLabel(rightDoc)} says "${rightValue}".` };
    }
  }

  if (reason.startsWith("claimed_amount_vs_")) {
    const doc = documentLabel(reason.replace("claimed_amount_vs_", "").replace(/_total$/, ""));
    const leftValue = fieldValueOf(details.left);
    const rightValue = fieldValueOf(details.right);
    if (!leftValue || !rightValue) {
      return { category: "missing", text: `Claimed amount: couldn't be checked against the ${doc} total because one value is missing.` };
    }
    return { category: "conflict", text: `Claimed amount: the claim asks for "${leftValue}", but the ${doc} total is "${rightValue}".` };
  }

  if (reason.startsWith("currency_")) {
    const doc = documentLabel(reason.replace("currency_", ""));
    const expected = typeof details.expected === "string" ? details.expected : "the policy currency";
    const actual = typeof details.actual === "string" && details.actual ? details.actual : "a different currency";
    return { category: "conflict", text: `${doc}: currency is ${actual}, but the policy expects ${expected}.` };
  }

  if (reason.startsWith("valid_amount_")) {
    const remainder = reason.replace("valid_amount_", "");
    const split = splitDocType(remainder);
    const doc = split ? documentLabel(split.doc) : "the document";
    const field = split ? fieldLabel(split.rest) : "Amount";
    const value = typeof details.value === "string" ? details.value : undefined;
    return { category: "other", text: `${doc}: ${field}${value ? ` ("${value}")` : ""} doesn't look like a valid amount.` };
  }

  if (reason.startsWith("valid_date_")) {
    const remainder = reason.replace("valid_date_", "");
    const split = splitDocType(remainder);
    const doc = split ? documentLabel(split.doc) : "the document";
    const field = split ? fieldLabel(split.rest) : "Date";
    const value = typeof details.value === "string" ? details.value : undefined;
    if (details.reason === "invalid_date_format") {
      return { category: "timing", text: `${doc}: ${field}${value ? ` ("${value}")` : ""} isn't in a recognizable date format.` };
    }
    return { category: "timing", text: `${doc}: ${field}${value ? ` ("${value}")` : ""} is outside the policy's allowed date range — please confirm.` };
  }

  if (reason.startsWith("chronology_incident_before_")) {
    const remainder = reason.replace("chronology_incident_before_", "");
    const split = splitDocType(remainder);
    const doc = split ? documentLabel(split.doc) : "the document";
    const field = split ? fieldLabel(split.rest) : "Date";
    return { category: "timing", text: `${doc}: ${field} falls before the reported incident date — please confirm the timeline.` };
  }

  if (/^chronology_.+_before_invoice$/.test(reason)) {
    const remainder = reason.replace(/^chronology_/, "").replace(/_before_invoice$/, "");
    const split = splitDocType(remainder);
    const doc = split ? documentLabel(split.doc) : "the document";
    const field = split ? fieldLabel(split.rest) : "Service date";
    return { category: "timing", text: `${doc}: ${field} falls after its own invoice date — please confirm the timeline.` };
  }

  if (reason === "policy_number_format") {
    return { category: "other", text: "Policy number doesn't match the expected format." };
  }

  if (reason === "required_documents_present") {
    return { category: "missing", text: "Not all required documents have been uploaded yet." };
  }

  if (reason === "risk_review") {
    return { category: "other", text: "This claim was flagged by risk screening and needs a manual look." };
  }

  return { category: "other", text: fieldLabel(reason) };
}

export function groupReviewReasons(reasons: string[], rules: RuleResult[]): ReviewReasonGroup[] {
  const cards = reasons.map((reason) => {
    const rule = rules.find((item) => item.rule_name === reason);
    const details = parseDetails(rule?.details);
    const { category, text } = categorize(reason, details);
    return { key: reason, category, text };
  });

  return CATEGORY_ORDER.map((category) => ({
    category,
    label: CATEGORY_META[category].label,
    tone: CATEGORY_META[category].tone,
    items: cards.filter((card) => card.category === category).map(({ key, text }) => ({ key, text }))
  })).filter((group) => group.items.length > 0);
}
