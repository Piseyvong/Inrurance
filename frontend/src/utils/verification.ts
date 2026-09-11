import type { ExtractedField, RuleResult } from "../types/api";

/**
 * Group extracted fields by document id because the backend returns a flat
 * evidence list and the officer UI needs to read evidence source-by-source.
 */
export function groupFieldsByDocument(fields: ExtractedField[]): Map<number, ExtractedField[]> {
  const grouped = new Map<number, ExtractedField[]>();
  for (const field of fields) {
    const existing = grouped.get(field.document_id) ?? [];
    existing.push(field);
    grouped.set(field.document_id, existing);
  }
  return grouped;
}

/**
 * The rules engine names cross-document consistency checks "consistent_*"
 * (identity, incident date, policy number, currency) and "claimed_amount_vs_*"
 * (claimed amount vs. an invoice/receipt total); "policy_number_format" is a
 * standalone format check. Everything else (OCR quality, required fields,
 * per-field date/amount validity) belongs on the per-document tabs instead.
 */
export function comparisonRules(rules: RuleResult[]): RuleResult[] {
  return rules.filter(
    (rule) =>
      rule.rule_name.startsWith("consistent_") ||
      rule.rule_name.startsWith("claimed_amount_vs_") ||
      rule.rule_name.startsWith("currency_") ||
      rule.rule_name === "policy_number_format"
  );
}

export function hasHumanReviewReasons(reasons: string[]): boolean {
  return reasons.length > 0;
}

function valueOf(side: any): string {
  return side?.field_value ?? side?.normalized_value ?? side?.value ?? "";
}

/**
 * Turn a rule's JSON detail payload into a short, human-readable label so UI
 * users never see raw `{...}` dumps. Unknown shapes fall back to an empty
 * string (the caller then shows just the rule name and its outcome badge).
 */
export function verificationRuleDetail(rule: RuleResult): string {
  let detail: any = rule.details;
  if (typeof detail === "string") {
    try { detail = JSON.parse(detail); } catch { return ""; }
  }
  if (!detail || typeof detail !== "object") return "";
  if (detail.expected !== undefined && detail.actual !== undefined) return `${detail.expected} → ${detail.actual}`;
  if (detail.left && detail.right) return `${valueOf(detail.left)} → ${valueOf(detail.right)}`;
  if (detail.claim !== undefined && detail.document !== undefined) return `${detail.claim} → ${detail.document}`;
  if (detail.value !== undefined && detail.value !== null && detail.value !== "") return String(detail.value);
  return "";
}
