import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "@/services/api";
import type { DocumentRead } from "@/types";

export interface UseDocuments {
  documents: DocumentRead[];
  available: boolean;
  uploading: boolean;
  progress: number;
  error: string | null;
  upload: (file: File) => Promise<void>;
  remove: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
}

/** Manages uploaded RAG documents; degrades gracefully without a database. */
export function useDocuments(enabled: boolean): UseDocuments {
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [available, setAvailable] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await api.listDocuments());
      setAvailable(true);
    } catch {
      setAvailable(false);
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    if (enabled) void refresh();
  }, [enabled, refresh]);

  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      setProgress(0);
      setError(null);
      try {
        await api.uploadDocument(file, setProgress);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
      } finally {
        setUploading(false);
        setProgress(0);
      }
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      try {
        await api.deleteDocument(id);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Löschen fehlgeschlagen.");
      }
    },
    [refresh],
  );

  return { documents, available, uploading, progress, error, upload, remove, refresh };
}
