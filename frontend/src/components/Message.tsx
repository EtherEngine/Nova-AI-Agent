import { AlertTriangle, Sparkles, User } from "lucide-react";
import { memo } from "react";

import { LoadingIndicator } from "@/components/LoadingIndicator";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ToolCall } from "@/components/ToolCall";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";

interface MessageProps {
  message: ChatMessage;
}

function MessageBase({ message }: MessageProps) {
  const isUser = message.role === "user";
  const isError = message.status === "error";

  return (
    <div className="animate-fade-in">
      <div
        className={cn(
          "flex gap-3.5",
          isUser ? "flex-row-reverse" : "flex-row",
        )}
      >
        <div
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-lg",
            isUser
              ? "bg-secondary text-secondary-foreground"
              : isError
                ? "bg-destructive/15 text-destructive"
                : "bg-primary/15 text-primary",
          )}
          aria-hidden
        >
          {isUser ? (
            <User className="size-4" />
          ) : isError ? (
            <AlertTriangle className="size-4" />
          ) : (
            <Sparkles className="size-4" />
          )}
        </div>

        <div
          className={cn(
            "min-w-0 max-w-[min(46rem,100%)] space-y-3",
            isUser && "flex flex-col items-end",
          )}
        >
          {message.tools && message.tools.length > 0 ? (
            <div className="w-full space-y-2">
              {message.tools.map((tool, index) => (
                <ToolCall key={`${tool.name}-${index}`} tool={tool} />
              ))}
            </div>
          ) : null}

          {isUser ? (
            <div className="whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-secondary px-4 py-2.5 text-[15px] leading-relaxed text-secondary-foreground">
              {message.content}
            </div>
          ) : isError ? (
            <div className="rounded-2xl rounded-tl-sm border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-[15px] leading-relaxed text-destructive">
              {message.content}
            </div>
          ) : message.status === "streaming" && message.content === "" ? (
            <LoadingIndicator className="pt-1.5" label="Nova denkt nach…" />
          ) : (
            <div>
              <MarkdownRenderer content={message.content} />
              {message.status === "streaming" ? (
                <span
                  className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-blink rounded-full bg-primary align-middle"
                  aria-hidden
                />
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const Message = memo(MessageBase);
