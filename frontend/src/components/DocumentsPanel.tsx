import { FileText, Loader2, Trash2, Upload, X } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { useDocuments } from "@/hooks/useDocuments";
import { cn } from "@/lib/utils";

interface DocumentsPanelProps {
  open: boolean;
  onClose: () => void;
}

const ACCEPT = ".pdf,.md,.markdown,.txt";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Modal panel for uploading (drag & drop) and managing RAG documents. */
export function DocumentsPanel({ open, onClose }: DocumentsPanelProps) {
  const { documents, available, uploading, progress, error, upload, remove } =
    useDocuments(open);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      void upload(files[0]);
    },
    [upload],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      handleFiles(event.dataTransfer.files);
    },
    [handleFiles],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} aria-hidden />

      <div className="animate-fade-in relative z-10 flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <FileText className="size-4 text-primary" />
            Dokumente (RAG)
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Schließen"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="scrollbar-slim flex-1 overflow-y-auto p-5">
          {!available ? (
            <p className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
              Dokumente sind ohne konfigurierte Datenbank nicht verfügbar.
            </p>
          ) : (
            <>
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
                  dragging
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50 hover:bg-accent/40",
                )}
              >
                <Upload className="size-6 text-muted-foreground" />
                <p className="text-sm font-medium">
                  Datei hierher ziehen oder klicken
                </p>
                <p className="text-xs text-muted-foreground">
                  PDF, Markdown oder TXT
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT}
                  className="hidden"
                  onChange={(event) => handleFiles(event.target.files)}
                />
              </div>

              {uploading ? (
                <div className="mt-4">
                  <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" />
                    Wird hochgeladen und eingebettet… {progress}%
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              ) : null}

              {error ? (
                <p className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </p>
              ) : null}

              <ul className="mt-5 flex flex-col gap-2">
                {documents.length === 0 ? (
                  <li className="text-sm text-muted-foreground">
                    Noch keine Dokumente hochgeladen.
                  </li>
                ) : (
                  documents.map((doc) => (
                    <li
                      key={doc.id}
                      className="flex items-center gap-3 rounded-lg border border-border px-3 py-2"
                    >
                      <FileText className="size-4 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm">{doc.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatSize(doc.size_bytes)} · {doc.chunk_count} Chunks
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void remove(doc.id)}
                        aria-label="Dokument löschen"
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-destructive"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </>
          )}
        </div>

        <div className="border-t border-border px-5 py-3">
          <Button variant="secondary" className="w-full" onClick={onClose}>
            Fertig
          </Button>
        </div>
      </div>
    </div>
  );
}
