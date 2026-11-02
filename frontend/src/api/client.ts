import type { ChatRequest, Conversation, DocumentItem, Message, Source } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string; error?: string };
      message = body.detail ?? body.error ?? message;
    } catch {
      // Keep the HTTP status message when the server did not return JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listDocuments: () => request<DocumentItem[]>("/documents"),
  uploadDocuments(files: File[]) {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    return request<{ documents: DocumentItem[] }>("/documents", { method: "POST", body });
  },
  deleteDocument: (id: string) =>
    request<void>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  listConversations: () => request<Conversation[]>("/conversations"),
  getMessages: (id: string) =>
    request<Message[]>(`/conversations/${encodeURIComponent(id)}/messages`),
  deleteConversation: (id: string) =>
    request<void>(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

export interface StreamCallbacks {
  onSources: (sources: Source[], debug: Source[]) => void;
  onToken: (text: string) => void;
  onDone: (conversationId: string) => void;
}

export async function streamChat(
  payload: ChatRequest,
  callbacks: StreamCallbacks,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string; error?: string };
      message = body.detail ?? body.error ?? message;
    } catch {
      // Keep the HTTP status message when the server did not return JSON.
    }
    throw new Error(message);
  }
  if (!response.body) throw new Error("The server did not provide a streaming response");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (block: string) => {
    let event = "message";
    let data = "";
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) return;
    const parsed = JSON.parse(data) as {
      sources?: Source[];
      debug?: Source[];
      text?: string;
      conversation_id?: string;
      message?: string;
    };
    if (event === "sources") callbacks.onSources(parsed.sources ?? [], parsed.debug ?? []);
    if (event === "token") callbacks.onToken(parsed.text ?? "");
    if (event === "done") callbacks.onDone(parsed.conversation_id ?? "");
    if (event === "error") throw new Error(parsed.message ?? "The answer could not be generated");
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) dispatch(block);
      if (done) break;
    }
    if (buffer.trim()) dispatch(buffer);
  } finally {
    reader.releaseLock();
  }
}
