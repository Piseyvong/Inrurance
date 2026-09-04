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

export function comparisonRules(rules: RuleResult[]): RuleResult[] {
  return rules.filter((rule) =>
    [
      "name_claim_form_vs_medical_report",
      "name_claim_form_vs_receipt",
      "date_claim_form_vs_medical_report",
      "date_claim_form_vs_receipt",
      "amount_claim_form_vs_receipt",
      "policy_number_format"
    ].includes(rule.rule_name)
  );
}

export function hasHumanReviewReasons(reasons: string[]): boolean {
  return reasons.length > 0;
}
