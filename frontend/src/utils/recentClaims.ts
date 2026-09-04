import type { Claim } from "../types/api";

const STORAGE_KEY = "recentClaims";
const MAX_RECENT_CLAIMS = 8;

export interface RecentClaimRecord {
  id: number;
  claimant_name: string | null;
  policy_number: string | null;
  incident_date: string | null;
  claimed_amount: string | number | null;
  status: string;
  created_at: string | null;
  updated_at: string;
}

/**
 * The backend has no claim-listing endpoint, so the dashboard activity table
 * is backed by a small browser-side log of claims created or opened in this
 * session. Records are written from real API responses only, never fabricated.
 */
export function loadRecentClaims(): RecentClaimRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (item): item is RecentClaimRecord =>
          item !== null && typeof item === "object" && typeof (item as { id?: unknown }).id === "number"
      )
      .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  } catch {
    return [];
  }
}

export function saveRecentClaim(claim: Claim): RecentClaimRecord[] {
  const record: RecentClaimRecord = {
    id: claim.id,
    claimant_name: claim.claimant_name,
    policy_number: claim.policy_number,
    incident_date: claim.incident_date,
    claimed_amount: claim.claimed_amount,
    status: claim.status,
    created_at: claim.created_at,
    updated_at: new Date().toISOString()
  };
  const next = [record, ...loadRecentClaims().filter((item) => item.id !== claim.id)].slice(0, MAX_RECENT_CLAIMS);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage may be unavailable (private mode); the app still works without
    // the recent-claims log.
  }
  return next;
}
