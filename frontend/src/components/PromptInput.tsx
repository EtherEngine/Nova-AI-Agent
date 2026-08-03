import { ArrowUp, Square } from "lucide-react";
import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_LENGTH = 4000;
const MAX_HEIGHT_PX = 200;

interface PromptInputProps {
  onSend: (text: string) => void;
  onStop?: () => void;
  disabled?: boolean;
}

/** Auto-growing chat composer. Enter sends, Shift+Enter inserts a newline. */
export function PromptInput({ onSend, onStop, disabled = false }: PromptInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep the textarea height in sync with its content, up to a max.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }, [value, disabled, onSend]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <form onSubmit={handleSubmit} className="mx-auto w-full max-w-3xl">
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-lg transition-colors",
          "focus-within:border-primary/60 focus-within:ring-1 focus-within:ring-primary/40",
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value.slice(0, MAX_LENGTH))}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Schreibe eine Nachricht…"
          disabled={disabled}
          className="scrollbar-slim max-h-[200px] flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
        />
        <Button
          type={disabled ? "button" : "submit"}
          size="icon"
          onClick={disabled ? onStop : undefined}
          disabled={disabled ? !onStop : !canSend}
          className="size-9 shrink-0 rounded-xl"
          aria-label={disabled ? "Antwort stoppen" : "Nachricht senden"}
        >
          {disabled ? (
            <Square className="size-3.5 fill-current" />
          ) : (
            <ArrowUp className="size-4" />
          )}
        </Button>
      </div>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        Enter zum Senden · Shift+Enter für neue Zeile
      </p>
    </form>
  );
}
