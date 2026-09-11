import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
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
  error,
  onSelectFile,
  onUpload
}: DocumentCardProps) {
  const received = Boolean(document);
  const fileInvalid = selectedFile ? !isAcceptedFile(selectedFile) : false;
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    if (received || busy) return;
    const file = event.dataTransfer.files?.[0];
    if (file) onSelectFile(docType, file);
  }

  const code = docType.split("_").map((part) => part[0]).join("").toUpperCase();

  return (
    <section className={`documentCard${received ? " is-received" : ""}`}>
      <div className="documentCardHeader">
        <span className="documentTypeCode" aria-hidden="true">{code}</span>
        <div className="documentCardHeading">
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        <StatusBadge status={received ? "received" : "missing"} />
      </div>

      {previewUrl ? (
        <div className="documentPreviewFrame">
          <img className="documentPreview" src={previewUrl} alt={`Preview of ${title}`} />
        </div>
      ) : null}

      {received ? (
        <div className="documentFile documentFile--done">
          <span className="documentFileIcon" aria-hidden="true">✓</span>
          <div className="documentFileMeta">
            <strong>{document?.original_filename ?? "Uploaded file"}</strong>
            <span>{formatBytes(document?.file_size)}</span>
          </div>
        </div>
      ) : (
        <div
          className={`documentDropzone${dragActive ? " is-dragging" : ""}${selectedFile ? " has-file" : ""}`}
          onDragOver={(event) => { event.preventDefault(); if (!busy) setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => !busy && inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => { if (!busy && (event.key === "Enter" || event.key === " ")) inputRef.current?.click(); }}
        >
          <input
            ref={inputRef}
            type="file"
            className="documentDropzoneInput"
            accept={ACCEPTED_FILE_TYPES}
            disabled={busy}
            onChange={(event) => onSelectFile(docType, event.target.files?.[0] ?? null)}
          />
          {selectedFile ? (
            <div className="documentFileMeta">
              <strong>{selectedFile.name}</strong>
              <span>{formatBytes(selectedFile.size)} - ready to upload</span>
            </div>
          ) : (
            <div className="documentFileMeta">
              <strong className="documentDropzoneHint">Drop a file or click to browse</strong>
              <span>PDF, JPG, or PNG</span>
            </div>
          )}
          <button
            type="button"
            className="documentUploadButton"
            disabled={!selectedFile || fileInvalid || busy}
            onClick={(event) => { event.stopPropagation(); onUpload(docType); }}
          >
            Upload
          </button>
        </div>
      )}

      {fileInvalid ? <p className="fieldError">Select a PDF, JPG, JPEG, or PNG file.</p> : null}
      {error ? <p className="fieldError">{error}</p> : null}
    </section>
  );
}
