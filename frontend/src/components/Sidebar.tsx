import { Archive, FileText, MessageSquare, Pencil, Plus, Settings, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

import { NovaLogo } from "@/components/NovaLogo";
import { Button } from "@/components/ui/button";
import { AGENT } from "@/config/agent";
import { cn } from "@/lib/utils";
import type { ChatSummary } from "@/types";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  chats: ChatSummary[];
  historyAvailable: boolean;
  activeChatId: string | null;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onRenameChat: (id: string, title: string) => void;
  onDeleteChat: (id: string) => void;
  onArchiveChat: (id: string) => void;
  onOpenDocuments: () => void;
}

/**
 * Left navigation with the persisted chat list. When the backend has no
 * database (history unavailable) a prepared placeholder is shown instead.
 */
export function Sidebar({
  open,
  onClose,
  chats,
  historyAvailable,
  activeChatId,
  onNewChat,
  onSelectChat,
  onRenameChat,
  onDeleteChat,
  onArchiveChat,
  onOpenDocuments,
}: SidebarProps) {
  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-20 bg-black/50 transition-opacity md:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-border bg-card transition-transform md:static md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Brand */}
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
          <NovaLogo className="size-8" />
          <div className="leading-tight">
            <p className="text-sm font-semibold">{AGENT.name}</p>
            <p className="text-xs text-muted-foreground">AI Agent</p>
          </div>
        </div>

        <div className="p-3">
          <Button onClick={onNewChat} className="w-full justify-start" variant="secondary">
            <Plus className="size-4" />
            Neuer Chat
          </Button>
        </div>

        <div className="scrollbar-slim flex-1 overflow-y-auto px-3">
          <p className="px-1 pb-2 pt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Verlauf
          </p>

          {historyAvailable && chats.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {chats.map((chat) => (
                <li key={chat.id}>
                  <div
                    className={cn(
                      "group flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors",
                      chat.id === activeChatId ? "bg-accent" : "hover:bg-accent/60",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectChat(chat.id)}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    >
                      <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                      <span className="truncate">{chat.title}</span>
                    </button>
                    <div className="flex shrink-0 items-center opacity-0 transition-opacity group-hover:opacity-100">
                      <IconAction
                        label="Umbenennen"
                        onClick={() => {
                          const title = window.prompt("Neuer Titel", chat.title);
                          if (title && title.trim()) onRenameChat(chat.id, title.trim());
                        }}
                      >
                        <Pencil className="size-3.5" />
                      </IconAction>
                      <IconAction label="Archivieren" onClick={() => onArchiveChat(chat.id)}>
                        <Archive className="size-3.5" />
                      </IconAction>
                      <IconAction
                        label="Löschen"
                        onClick={() => {
                          if (window.confirm(`Chat „${chat.title}" löschen?`)) {
                            onDeleteChat(chat.id);
                          }
                        }}
                      >
                        <Trash2 className="size-3.5" />
                      </IconAction>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-2.5 py-4 text-xs text-muted-foreground">
              {historyAvailable
                ? "Noch keine Chats. Starte einen neuen Chat."
                : "Chat-Verlauf ist inaktiv (keine Datenbank konfiguriert)."}
            </p>
          )}
        </div>

        {/* Settings (prepared) */}
        <div className="border-t border-border p-3">
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={onOpenDocuments}
          >
            <FileText className="size-4" />
            Dokumente
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start text-muted-foreground"
            disabled
          >
            <Settings className="size-4" />
            Einstellungen
          </Button>
        </div>
      </aside>
    </>
  );
}

interface IconActionProps {
  label: string;
  onClick: () => void;
  children: ReactNode;
}

function IconAction({ label, onClick, children }: IconActionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
    >
      {children}
    </button>
  );
}
