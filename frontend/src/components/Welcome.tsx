import { ArrowUpRight } from "lucide-react";

import { NovaLogo } from "@/components/NovaLogo";
import { AGENT, EXAMPLE_PROMPTS } from "@/config/agent";

interface WelcomeProps {
  onSelectPrompt: (prompt: string) => void;
}

/** First-run hero shown while the conversation is empty. */
export function Welcome({ onSelectPrompt }: WelcomeProps) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-4 text-center">
      <NovaLogo className="mb-5 size-16 animate-fade-in rounded-2xl shadow-lg shadow-primary/20" />
      <h2 className="animate-fade-in text-3xl font-semibold tracking-tight">
        {AGENT.name}
      </h2>
      <p className="mt-1 animate-fade-in text-sm font-medium text-primary">
        {AGENT.tagline}
      </p>
      <p className="mt-3 max-w-md animate-fade-in text-[15px] leading-relaxed text-muted-foreground">
        {AGENT.description}
      </p>

      <div className="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {EXAMPLE_PROMPTS.map((example) => (
          <button
            key={example.prompt}
            type="button"
            onClick={() => onSelectPrompt(example.prompt)}
            className="group flex items-start justify-between gap-3 rounded-xl border border-border bg-card/60 p-4 text-left transition-colors hover:border-primary/50 hover:bg-accent/50"
          >
            <span>
              <span className="block text-sm font-medium">{example.title}</span>
              <span className="mt-0.5 block text-sm text-muted-foreground">
                {example.prompt}
              </span>
            </span>
            <ArrowUpRight className="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
          </button>
        ))}
      </div>
    </div>
  );
}
