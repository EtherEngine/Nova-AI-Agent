import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ConnectionStatus } from "@/types";

interface HeaderProps {
  title: string;
  model: string | null;
  status: ConnectionStatus;
  onToggleSidebar: () => void;
}

const STATUS_META: Record<ConnectionStatus, { label: string; dot: string }> = {
  connecting: { label: "Verbinde…", dot: "bg-amber-400" },
  online: { label: "Verbunden", dot: "bg-emerald-400" },
  offline: { label: "Offline", dot: "bg-destructive" },
};

/** Top bar: chat title, configured model, and live API connection status. */
export function Header({ title, model, status, onToggleSidebar }: HeaderProps) {
  const meta = STATUS_META[status];

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggleSidebar}
        className="md:hidden"
        aria-label="Menü umschalten"
      >
        <Menu className="size-5" />
      </Button>

      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold">{title}</h1>
        {model ? (
          <p className="truncate text-xs text-muted-foreground">Modell: {model}</p>
        ) : null}
      </div>

      <div className="ml-auto flex items-center gap-2 rounded-full border border-border px-2.5 py-1">
        <span className={cn("size-2 rounded-full", meta.dot)} aria-hidden />
        <span className="text-xs text-muted-foreground">{meta.label}</span>
      </div>
    </header>
  );
}
