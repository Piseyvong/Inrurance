/**
 * Supported claim types and their human-readable labels.
 *
 * The backend accepts a single outpatient claim type today. Keeping the value
 * -> label mapping in one module means the form dropdown, validation, and the
 * create payload all share the same values instead of scattering raw strings
 * across components.
 */

export const CLAIM_TYPES = [
  { value: "medical", label: "Medical claim" },
  { value: "motor", label: "Motor claim" },
  { value: "life", label: "Life claim" },
  { value: "property", label: "Property claim" },
  { value: "travel", label: "Travel claim" },
  { value: "other", label: "Other insurance claim" }
] as const;

export type ClaimTypeValue = (typeof CLAIM_TYPES)[number]["value"];

export function claimTypeLabel(value: string): string {
  return CLAIM_TYPES.find((item) => item.value === value)?.label ?? value;
}
