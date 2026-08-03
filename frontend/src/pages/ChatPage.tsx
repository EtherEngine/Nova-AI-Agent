import { useCallback, useMemo, useState } from "react";

import { ChatWindow } from "@/components/ChatWindow";
import { DocumentsPanel } from "@/components/DocumentsPanel";
import { Header } from "@/components/Header";
import { PromptInput } from "@/components/PromptInput";
import { Sidebar } from "@/components/Sidebar";
import { useChat } from "@/hooks/useChat";
import { useChats } from "@/hooks/useChats";
import { useHealth } from "@/hooks/useHealth";
import { api } from "@/services/api";
import type { ChatMessage, PersistedMessage } from "@/types";

function toChatMessage(message: PersistedMessage): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    tools: message.tools,
    status: "complete",
    createdAt: Date.parse(message.created_at) || Date.now(),
  };
}

/** Main application page: composes the full chat experience. */
export function ChatPage() {
  const { messages, isLoading, sendMessage, hydrate, stop, reset } = useChat();
  const { chats, available, create, rename, remove, archive, refresh } = useChats();
  const { status, model } = useHealth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [documentsOpen, setDocumentsOpen] = useState(false);

  const title = useMemo(() => {
    const firstUser = messages.find((message) => message.role === "user");
    if (!firstUser) return "Neuer Chat";
    return firstUser.content.length > 48
      ? `${firstUser.content.slice(0, 48)}…`
      : firstUser.content;
  }, [messages]);

  const handleNewChat = useCallback(() => {
    setActiveChatId(null);
    reset();
    setSidebarOpen(false);
  }, [reset]);

  const handleSelectChat = useCallback(
    async (id: string) => {
      try {
        const detail = await api.getChat(id);
        setActiveChatId(id);
        hydrate(detail.messages.map(toChatMessage));
        setSidebarOpen(false);
      } catch {
        // Ignore load errors; keep the current view.
      }
    },
    [hydrate],
  );

  const handleSend = useCallback(
    async (text: string) => {
      setSidebarOpen(false);
      let chatId = activeChatId;
      // Start a persisted chat lazily on the first message when a DB exists.
      if (available && !chatId) {
        const chat = await create();
        if (chat) {
          chatId = chat.id;
          setActiveChatId(chat.id);
        }
      }
      await sendMessage(text, chatId ?? undefined);
      if (available) void refresh();
    },
    [activeChatId, available, create, refresh, sendMessage],
  );

  const onSend = useCallback((text: string) => void handleSend(text), [handleSend]);

  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        chats={chats}
        historyAvailable={available}
        activeChatId={activeChatId}
        onNewChat={handleNewChat}
        onSelectChat={(id) => void handleSelectChat(id)}
        onRenameChat={(id, newTitle) => void rename(id, newTitle)}
        onDeleteChat={(id) => {
          if (id === activeChatId) handleNewChat();
          void remove(id);
        }}
        onArchiveChat={(id) => {
          if (id === activeChatId) handleNewChat();
          void archive(id);
        }}
        onOpenDocuments={() => {
          setSidebarOpen(false);
          setDocumentsOpen(true);
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          title={title}
          model={model}
          status={status}
          onToggleSidebar={() => setSidebarOpen((value) => !value)}
        />

        <main className="min-h-0 flex-1">
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            onSelectPrompt={onSend}
          />
        </main>

        <div className="shrink-0 border-t border-border bg-background/80 px-4 py-4 backdrop-blur">
          <PromptInput onSend={onSend} onStop={stop} disabled={isLoading} />
        </div>
      </div>

      <DocumentsPanel open={documentsOpen} onClose={() => setDocumentsOpen(false)} />
    </div>
  );
}
