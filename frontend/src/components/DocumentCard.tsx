import { useEffect, useState } from "react";
import type { DocumentRecord, DocumentType } from "../types/api";
import { getDocumentPreview } from "../api/documents";
import { ACCEPTED_FILE_TYPES, formatBytes, isAcceptedFile } from "../utils/documents";
import { StatusBadge } from "./StatusBadge";

interface DocumentCardProps {
  docType: DocumentType;
  title: string;
  description: string;
  document?: DocumentRecord;
  selectedFile?: File;
  busy?: boolean;
  processing?: boolean;
  error?: string;
  onSelectFile: (docType: DocumentType, file: File | null) => void;
  onUpload: (docType: DocumentType) => void;
}

/**
 * Required document intake card. It blocks duplicate upload attempts in the UI
 * because the backend intentionally has no replacement behavior yet.
 */
export function DocumentCard({
  docType,
  title,
  description,
  document,
  selectedFile,
  busy,
  processing,
  error,
  onSelectFile,
  onUpload
}: DocumentCardProps) {
  const received = Boolean(document);
  const fileInvalid = selectedFile ? !isAcceptedFile(selectedFile) : false;
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!document?.mime_type?.startsWith("image/")) return;
    let active = true;
    let url: string | null = null;
    getDocumentPreview(document.id).then((nextUrl) => {
      url = nextUrl;
      if (active) setPreviewUrl(nextUrl);
      else URL.revokeObjectURL(nextUrl);
    }).catch(() => setPreviewUrl(null));
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [document?.id, document?.mime_type]);

  return (
    <section className="documentCard">
      <div className="documentCardHeader">
        <div>
          <span className="documentTypeCode">{docType.split("_").map((part) => part[0]).join("").toUpperCase()}</span>
        </div>
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        <StatusBadge status={received ? "received" : "missing"} />
      </div>
      <div className="documentMeta">
        {document ? <span>{document.original_filename ?? "Uploaded file"} - {formatBytes(document.file_size)}</span> : null}
        {selectedFile ? <span>Selected: {selectedFile.name} - {formatBytes(selectedFile.size)}</span> : null}
      </div>
      {previewUrl ? <img className="documentPreview" src={previewUrl} alt={`Preview of ${title}`} /> : null}
      {!received ? (
        <div className="uploadRow">
          <label>
            Select PDF or Image
            <input
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              onChange={(event) => onSelectFile(docType, event.target.files?.[0] ?? null)}
            />
          </label>
          <button type="button" disabled={!selectedFile || fileInvalid || busy} onClick={() => onUpload(docType)}>
            Upload
          </button>
        </div>
      ) : <p className="sectionNote">{processing ? "Processing documents…" : "Received. Processing starts automatically when all required documents are uploaded."}</p>}
      <div className="statusGrid">
        <span>Processing</span>
        <StatusBadge status={processing ? "processing" : received ? "queued" : "not started"} />
        <span>Extraction</span>
        <StatusBadge status={processing ? "processing" : "not started"} />
      </div>
      {fileInvalid ? <p className="fieldError">Select a PDF, JPG, JPEG, or PNG file.</p> : null}
      {error ? <p className="fieldError">{error}</p> : null}
    </section>
  );
}
