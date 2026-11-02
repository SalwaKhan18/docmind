export interface DocumentItem {
  id: string;
  filename: string;
  status: "processing" | "ready" | "error";
  chunk_count: number;
  error: string | null;
  created_at: string;
}

export interface Source {
  id: string;
  filename: string;
  page: number;
  snippet: string;
  vector_score: number | null;
  bm25_score: number | null;
  rrf_score: number | null;
  rerank_score: number | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  created_at: string;
}

export interface DebugChunk extends Source {}

export interface ChatRequest {
  question: string;
  conversation_id?: string;
  document_ids: string[];
}
