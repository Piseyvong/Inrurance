import type { DocumentType } from "../types/api";
import { ACCEPTED_FILE_TYPES, isAcceptedFile } from "../utils/documents";
import { FileTextIcon } from "./icons";
import { StatusBadge } from "./StatusBadge";

interface DocumentRequirementRowProps {
  docType: DocumentType;
  title: string;
  purpose: string;
  busy: boolean;
  disabled?: boolean;
  uploadStatus: string;
  uploadError?: string;
  selectedFile?: File;
  onSelectFile: (docType: DocumentType, file: File | null) => void;
  onUpload: (docType: DocumentType) => void;
}

/**
 * Compact required-document row for the create-claim flow. It deliberately
 * shows only upload state (not OCR or extraction results), which belong to the
 * claim workspace after the claim is created.
 */
export function DocumentRequirementRow({
  docType,
  title,
  purpose,
  busy,
  disabled,
  uploadStatus,
  uploadError,
  selectedFile,
  onSelectFile,
  onUpload
}: DocumentRequirementRowProps) {
  const fileInvalid = selectedFile ? !isAcceptedFile(selectedFile) : false;

  return (
    <section className="docRequirementRow" aria-label={title}>
      <div className="docRequirementInfo">
        <span className="docReqIcon" aria-hidden="true">
          <FileTextIcon size={16} />
        </span>
        <div>
          <h3>{title}</h3>
          <p>{purpose}</p>
        </div>
      </div>
      <StatusBadge status="required" />
      <div className="docUpload">
        <label className="filePick">
          <span>{selectedFile ? selectedFile.name : "Select PDF or Image"}</span>
          <input
            className="srOnly"
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            aria-label={`Select ${title}`}
            onChange={(event) => onSelectFile(docType, event.target.files?.[0] ?? null)}
          />
        </label>
        <button
          type="button"
          className="secondaryButton"
          disabled={!selectedFile || fileInvalid || busy || disabled}
          onClick={() => onUpload(docType)}
        >
          {busy ? "Uploading..." : "Upload"}
        </button>
      </div>
      <StatusBadge status={uploadStatus} />
      {fileInvalid || uploadError ? (
        <p className="fieldError">
          {fileInvalid ? "Select a PDF, JPG, JPEG, or PNG file." : uploadError}
        </p>
      ) : null}
    </section>
  );
}
