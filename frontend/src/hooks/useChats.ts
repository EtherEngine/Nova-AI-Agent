import { useCallback, useEffect, useState } from "react";

import { api } from "@/services/api";
import type { ChatSummary } from "@/types";

export interface UseChats {
  chats: ChatSummary[];
  /** Whether the backend has a database configured (false → history disabled). */
  available: boolean;
  refresh: () => Promise<void>;
  create: (title?: string) => Promise<ChatSummary | null>;
  rename: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  archive: (id: string) => Promise<void>;
}

/**
 * Manages the persisted chat list. Degrades gracefully when the backend has no
 * database (HTTP 503): the list stays empty and {@link UseChats.available} is
 * false, so the UI can hide history without surfacing errors.
 */
export function useChats(): UseChats {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [available, setAvailable] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setChats(await api.listChats());
      setAvailable(true);
    } catch {
      // Any failure (503 no DB, network) → hide history, keep UI stable.
      setAvailable(false);
      setChats([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = useCallback(
    async (title?: string) => {
      try {
        const chat = await api.createChat(title);
        await refresh();
        return chat;
      } catch {
        return null;
      }
    },
    [refresh],
  );

  const rename = useCallback(
    async (id: string, title: string) => {
      await api.renameChat(id, title);
      await refresh();
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await api.deleteChat(id);
      await refresh();
    },
    [refresh],
  );

  const archive = useCallback(
    async (id: string) => {
      await api.setArchived(id, true);
      await refresh();
    },
    [refresh],
  );

  return { chats, available, refresh, create, rename, remove, archive };
}
