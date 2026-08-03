import { useEffect, useRef } from "react";

import { Message } from "@/components/Message";
import { Welcome } from "@/components/Welcome";
import type { ChatMessage } from "@/types";

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSelectPrompt: (prompt: string) => void;
}

/** Scrollable conversation area; shows the welcome hero when empty. */
export function ChatWindow({ messages, isLoading, onSelectPrompt }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="h-full">
        <Welcome onSelectPrompt={onSelectPrompt} />
      </div>
    );
  }

  return (
    <div className="scrollbar-slim h-full overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-7 px-4 py-8">
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
