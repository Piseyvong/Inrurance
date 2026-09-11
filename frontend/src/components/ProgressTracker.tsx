import { Fragment, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import type { ClaimWithDocuments, VerificationReport } from "../types/api";
import { ArrowRightIcon, CheckIcon } from "./icons";

// Collapsed from the underlying technical stages (policy match, OCR, rule
// checks, decision) into plain-language phases a customer actually cares
// about: did my upload go through, is it being checked, what's the result.
const steps = ["Upload", "Processing", "Result"];

const STEP_DESTINATION: Record<string, "documents" | "verification"> = {
  "Upload": "documents",
  "Processing": "verification",
  "Result": "verification"
};

interface ProgressTrackerProps {
  claim?: ClaimWithDocuments | null;
  verification?: VerificationReport | null;
  /**
   * Overrides the pathname-based "current" step. The documents page runs
   * automatic post-upload processing inline (without navigating to
   * /verification), so it passes "Processing" here while that's happening —
   * otherwise the tracker would stay stuck on "Upload" the whole time.
   */
  phase?: "Upload" | "Processing" | "Result";
  /** 0-100. Shown next to the Processing step while it's the current one. */
  progress?: number;
}

export function ProgressTracker({ claim, verification, phase, progress }: ProgressTrackerProps) {
  const { pathname } = useLocation();
  const currentRef = useRef<HTMLLIElement>(null);
  const approved = claim?.status === "auto_approved" || verification?.claim_status === "auto_approved";
  const processingDone = approved || Boolean(verification?.rule_results.length);
  const resultDone = Boolean(
    approved || (verification?.claim_status &&
    !["intake", "submitted", "waiting_for_documents"].includes(verification.claim_status))
  );
  const complete = {
    "Upload": Boolean(claim?.document_completeness?.is_complete),
    "Processing": processingDone,
    "Result": resultDone
  };
  const current = phase ?? (pathname.endsWith("/verification")
    ? (resultDone ? "Result" : "Processing")
    : pathname.endsWith("/documents") ? "Upload" : null);

  useEffect(() => {
    if (window.matchMedia("(max-width:720px)").matches) {
      currentRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [current]);

  return (
    <ol className="progressTracker" aria-label="Claim Progress">
      {steps.map((step) => {
        const done = complete[step as keyof typeof complete];
        const active = step === current;
        const content = (
          <>
            <span className={`stepMarker${done ? " withCheck" : ""}`}>{done ? <CheckIcon size={11} /> : <span aria-hidden="true" />}</span>
            {step}
            {step === "Processing" && active && typeof progress === "number" ? <small className="progressTrackerPercent">{Math.round(progress)}%</small> : null}
          </>
        );
        if (!claim?.id) return <li key={step} ref={active ? currentRef : undefined} className={`${done ? "done " : ""}${active ? "current" : ""}`}>{content}</li>;
        const destination = STEP_DESTINATION[step] === "documents" ? `/claims/${claim.id}/documents` : `/claims/${claim.id}/verification`;
        return (
          <Fragment key={step}>
            {step !== "Upload" ? <li className="trackerArrow" aria-hidden="true"><ArrowRightIcon size={15} /></li> : null}
            <li ref={active ? currentRef : undefined} className={`${done ? "done " : ""}${active ? "current" : ""}`}>
              <Link to={destination} className="progressTrackerLink">{content}</Link>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
