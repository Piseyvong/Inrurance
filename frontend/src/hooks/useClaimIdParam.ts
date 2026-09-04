import { useParams } from "react-router-dom";

/**
 * Reads the route claim id once and normalises invalid values to null so pages
 * can show user-friendly messages instead of throwing render-time errors.
 */
export function useClaimIdParam(): number | null {
  const { claimId } = useParams();
  if (!claimId) return null;
  const parsed = Number(claimId);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}
