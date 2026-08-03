import { cn } from "@/lib/utils";

interface LoadingIndicatorProps {
  className?: string;
  label?: string;
}

/** Three-dot "typing" indicator shown while the agent is thinking. */
export function LoadingIndicator({ className, label }: LoadingIndicatorProps) {
  return (
    <div className={cn("flex items-center gap-2 text-muted-foreground", className)}>
      <span className="flex gap-1" aria-hidden>
        <span className="h-2 w-2 animate-blink rounded-full bg-current [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-blink rounded-full bg-current [animation-delay:200ms]" />
        <span className="h-2 w-2 animate-blink rounded-full bg-current [animation-delay:400ms]" />
      </span>
      {label ? <span className="text-sm">{label}</span> : null}
    </div>
  );
}
