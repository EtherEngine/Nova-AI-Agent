import { ChevronDown, Wrench } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { cn } from "@/lib/utils";
import type { ToolInvocation } from "@/types";

interface ToolCallProps {
  tool: ToolInvocation;
}

/** Collapsible panel visualising a single tool call and its result. */
export function ToolCall({ tool }: ToolCallProps) {
  const [open, setOpen] = useState(false);
  const ok = tool.result.ok;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/60">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-sm transition-colors hover:bg-accent/50"
        aria-expanded={open}
      >
        <Wrench className="size-4 text-primary" />
        <span className="font-medium">Tool verwendet</span>
        <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs">
          {tool.name}()
        </code>
        <span
          className={cn(
            "ml-auto rounded-full px-2 py-0.5 text-xs font-medium",
            ok
              ? "bg-emerald-500/15 text-emerald-400"
              : "bg-destructive/15 text-destructive",
          )}
        >
          {ok ? "Erfolg" : "Fehler"}
        </span>
        <ChevronDown
          className={cn(
            "size-4 text-muted-foreground transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      {open ? (
        <div className="animate-fade-in border-t border-border px-3.5 pb-3.5 pt-1">
          <p className="mb-1 mt-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Argumente
          </p>
          <CodeBlock
            language="json"
            code={JSON.stringify(tool.arguments, null, 2)}
            className="my-0"
          />
          <p className="mb-1 mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Ergebnis
          </p>
          <CodeBlock
            language="json"
            code={JSON.stringify(tool.result, null, 2)}
            className="my-0"
          />
        </div>
      ) : null}
    </div>
  );
}
