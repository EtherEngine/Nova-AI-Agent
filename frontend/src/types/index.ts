/** Shared domain types mirroring the FastAPI backend contract. */

/** Result envelope returned by a backend tool. */
export interface ToolResult {
  ok: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

/** A single tool invocation performed by the agent during a turn. */
export interface ToolInvocation {
  name: string;
  arguments: Record<string, unknown>;
  result: ToolResult;
}

/** Response body of `POST /chat`. */
export interface ChatResponse {
  answer: string;
  tools: ToolInvocation[];
}

/** Response body of `GET /health`. */
export interface HealthResponse {
  status: string;
  model: string;
}

/** Roles used within the local conversation state. */
export type MessageRole = "user" | "assistant";

/**
 * Lifecycle status of a message. `streaming` is not produced yet but is part
 * of the contract so streaming can be added without touching consumers.
 */
export type MessageStatus = "complete" | "streaming" | "error";

/** A message rendered in the chat window. */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  tools?: ToolInvocation[];
  status: MessageStatus;
  createdAt: number;
}

/** Connection state of the backend API. */
export type ConnectionStatus = "connecting" | "online" | "offline";

// --- Persisted chat history ---------------------------------------------------

/** A chat list item (no messages). */
export interface ChatSummary {
  id: string;
  title: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

/** A persisted message including its tool invocations. */
export interface PersistedMessage {
  id: string;
  role: MessageRole;
  content: string;
  sequence: number;
  created_at: string;
  tools: ToolInvocation[];
}

/** A chat together with its ordered messages. */
export interface ChatDetail extends ChatSummary {
  messages: PersistedMessage[];
}

// --- Documents / RAG ----------------------------------------------------------

/** Metadata for an uploaded, embedded document. */
export interface DocumentRead {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  chunk_count: number;
  created_at: string;
}
