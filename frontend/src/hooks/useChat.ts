import { useCallback, useRef, useState } from "react";

import { ApiError, api } from "@/services/api";
import type { ChatMessage } from "@/types";

/** Create a reasonably unique message id (crypto when available). */
function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function makeMessage(
  role: ChatMessage["role"],
  content: string,
  extra: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    id: createId(),
    role,
    content,
    status: "complete",
    createdAt: Date.now(),
    ...extra,
  };
}

export interface UseChat {
  messages: ChatMessage[];
  isLoading: boolean;
  sendMessage: (text: string, chatId?: string) => Promise<void>;
  hydrate: (messages: ChatMessage[]) => void;
  stop: () => void;
  reset: () => void;
}

/**
 * Owns the conversation state for a single chat. Responses are streamed token
 * by token; the assistant message is updated in place. A running response can
 * be aborted via {@link UseChat.stop}.
 */
export function useChat(): UseChat {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const inFlight = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);

  const patch = useCallback(
    (id: string, update: (message: ChatMessage) => ChatMessage) => {
      setMessages((prev) =>
        prev.map((message) => (message.id === id ? update(message) : message)),
      );
    },
    [],
  );

  const sendMessage = useCallback(
    async (text: string, chatId?: string) => {
      const trimmed = text.trim();
      if (!trimmed || inFlight.current) {
        return;
      }

      inFlight.current = true;
      setIsLoading(true);

      const controller = new AbortController();
      controllerRef.current = controller;

      const assistant = makeMessage("assistant", "", {
        status: "streaming",
        tools: [],
      });
      setMessages((prev) => [...prev, makeMessage("user", trimmed), assistant]);

      try {
        await api.chatStream(trimmed, {
          chatId,
          signal: controller.signal,
          onToken: (delta) =>
            patch(assistant.id, (message) => ({
              ...message,
              content: message.content + delta,
            })),
          onTool: (tool) =>
            patch(assistant.id, (message) => ({
              ...message,
              tools: [...(message.tools ?? []), tool],
            })),
        });
        patch(assistant.id, (message) => ({ ...message, status: "complete" }));
      } catch (error) {
        if (controller.signal.aborted) {
          // User stopped the stream: keep partial output, mark complete.
          patch(assistant.id, (message) => ({ ...message, status: "complete" }));
        } else {
          const detail =
            error instanceof ApiError
              ? error.message
              : "Ein unerwarteter Fehler ist aufgetreten.";
          patch(assistant.id, (message) => ({
            ...message,
            status: "error",
            content: detail,
          }));
        }
      } finally {
        controllerRef.current = null;
        inFlight.current = false;
        setIsLoading(false);
      }
    },
    [patch],
  );

  const stop = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  const hydrate = useCallback((next: ChatMessage[]) => {
    if (inFlight.current) {
      return;
    }
    setMessages(next);
  }, []);

  const reset = useCallback(() => {
    if (inFlight.current) {
      return;
    }
    setMessages([]);
  }, []);

  return { messages, isLoading, sendMessage, hydrate, stop, reset };
}
