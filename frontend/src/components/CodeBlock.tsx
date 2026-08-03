import hljs from "highlight.js/lib/common";
import { Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";

interface CodeBlockProps {
  code: string;
  language?: string;
  className?: string;
}

/** A fenced code block with a language label and a copy-to-clipboard button. */
export function CodeBlock({ code, language, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const highlighted = useMemo(() => {
    if (language && hljs.getLanguage(language)) {
      return hljs.highlight(code, { language }).value;
    }
    return hljs.highlightAuto(code).value;
  }, [code, language]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard may be unavailable (e.g. insecure context); ignore silently.
    }
  };

  return (
    <div
      className={cn(
        "group my-4 overflow-hidden rounded-xl border border-border bg-[#0d0d12]",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border/60 bg-white/[0.02] px-4 py-1.5">
        <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
          {language || "text"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
          aria-label="Code kopieren"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Kopiert" : "Kopieren"}
        </button>
      </div>
      <pre className="scrollbar-slim overflow-x-auto p-4 text-[13px] leading-relaxed">
        <code
          className="hljs bg-transparent font-mono"
          // Highlighted HTML produced locally by highlight.js from trusted text.
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      </pre>
    </div>
  );
}
