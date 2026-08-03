import type {
  ChatDetail,
  ChatResponse,
  ChatSummary,
  DocumentRead,
  HealthResponse,
  ToolInvocation,
} from "@/types";

const API_URL: string = (
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

// Versioned API base; the backend also keeps legacy unversioned aliases.
const API_BASE = `${API_URL}/api/v1`;

const DEFAULT_TIMEOUT_MS = 60_000;

/** Error carrying a user-safe message plus an optional HTTP status. */
export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Zeitüberschreitung bei der Anfrage.");
    }
    throw new ApiError("Verbindung zum Server nicht möglich.");
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw new ApiError(await extractErrorDetail(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Ignore non-JSON error bodies and fall back to a status-based message.
  }
  if (response.status === 429) {
    return "Der KI-Dienst ist derzeit ausgelastet. Bitte später erneut versuchen.";
  }
  return `Unerwarteter Serverfehler (${response.status}).`;
}

export const api = {
  /** Fetch backend health, including the configured model name. */
  health(signal?: AbortSignal): Promise<HealthResponse> {
    return request<HealthResponse>("/health", { method: "GET", signal, timeoutMs: 8_000 });
  },

  /** Send a chat message and receive the final answer plus tool usage. */
  chat(message: string, chatId?: string): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, chat_id: chatId ?? null }),
    });
  },

  /** Stream a chat response via Server-Sent Events. */
  chatStream(message: string, handlers: StreamHandlers): Promise<ChatResponse> {
    return streamChat(message, handlers);
  },

  /** List chats (most recently updated first). Requires a database. */
  listChats(includeArchived = false): Promise<ChatSummary[]> {
    const query = includeArchived ? "?include_archived=true" : "";
    return request<ChatSummary[]>(`/chats${query}`, { method: "GET" });
  },

  createChat(title = "Neuer Chat"): Promise<ChatSummary> {
    return request<ChatSummary>("/chats", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },

  getChat(id: string): Promise<ChatDetail> {
    return request<ChatDetail>(`/chats/${id}`, { method: "GET" });
  },

  renameChat(id: string, title: string): Promise<ChatSummary> {
    return request<ChatSummary>(`/chats/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  },

  setArchived(id: string, archived: boolean): Promise<ChatSummary> {
    return request<ChatSummary>(`/chats/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ archived }),
    });
  },

  deleteChat(id: string): Promise<void> {
    return request<void>(`/chats/${id}`, { method: "DELETE" });
  },

  /** List uploaded documents. Requires a database. */
  listDocuments(): Promise<DocumentRead[]> {
    return request<DocumentRead[]>("/documents", { method: "GET" });
  },

  deleteDocument(id: string): Promise<void> {
    return request<void>(`/documents/${id}`, { method: "DELETE" });
  },

  /** Upload a document with progress reporting (XHR for upload events). */
  uploadDocument(
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<DocumentRead> {
    return new Promise<DocumentRead>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/documents`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText) as DocumentRead);
        } else {
          reject(new ApiError(parseXhrDetail(xhr), xhr.status));
        }
      };
      xhr.onerror = () =>
        reject(new ApiError("Verbindung zum Server nicht möglich."));
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    });
  },
} as const;

function parseXhrDetail(xhr: XMLHttpRequest): string {
  try {
    const body = JSON.parse(xhr.responseText) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Non-JSON error body.
  }
  if (xhr.status === 503) return "Dokumente sind ohne Datenbank nicht verfügbar.";
  return `Upload fehlgeschlagen (${xhr.status}).`;
}

export interface StreamHandlers {
  onToken: (delta: string) => void;
  onTool: (tool: ToolInvocation) => void;
  chatId?: string;
  signal?: AbortSignal;
}

interface SseFrame {
  event: string;
  data: unknown;
}

function parseFrame(raw: string): SseFrame | null {
  let event = "";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!event) return null;
  try {
    return { event, data: data ? JSON.parse(data) : {} };
  } catch {
    return null;
  }
}

async function streamChat(
  message: string,
  { onToken, onTool, chatId, signal }: StreamHandlers,
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, chat_id: chatId ?? null }),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Anfrage abgebrochen.");
    }
    throw new ApiError("Verbindung zum Server nicht möglich.");
  }

  if (!response.ok || !response.body) {
    throw new ApiError(await extractErrorDetail(response), response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const result: ChatResponse = { answer: "", tools: [] };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawFrame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const frame = parseFrame(rawFrame);
      if (!frame) continue;

      if (frame.event === "token") {
        onToken((frame.data as { delta: string }).delta);
      } else if (frame.event === "tool") {
        onTool(frame.data as ToolInvocation);
      } else if (frame.event === "done") {
        Object.assign(result, frame.data as ChatResponse);
      } else if (frame.event === "error") {
        throw new ApiError((frame.data as { detail: string }).detail);
      }
    }
  }

  return result;
}

export { API_URL, API_BASE };
