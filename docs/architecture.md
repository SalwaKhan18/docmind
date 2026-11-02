# DocMind architecture

```mermaid
flowchart LR
  U[Browser / React + TypeScript] -->|multipart upload, JSON, SSE| A[FastAPI]
  A --> D[SQLite: documents, conversations, messages]
  A --> I[Ingestion service]
  I --> P[PDF / DOCX / TXT / Markdown parsers]
  P --> C[Page-aware chunking]
  C --> E[Local sentence-transformer embeddings]
  E --> V[(Persistent ChromaDB)]
  C --> B[(Persisted BM25 corpus)]
  A --> R[Hybrid retriever]
  V --> R
  B --> R
  R --> F[Reciprocal-rank fusion]
  F --> X[Cross-encoder reranker]
  X --> G[Grounded RAG pipeline]
  G --> L[Groq / OpenAI / Ollama provider]
  L -->|sources, streamed tokens| U
```

## Request lifecycle

1. The upload endpoint validates supported extensions and a 20 MB per-file limit, persists
   each original file, and schedules ingestion in a background task.
2. The ingestion service extracts page text, splits at paragraph and sentence boundaries,
   computes normalized local embeddings, and stores chunks in ChromaDB and the JSON-backed
   BM25 corpus. SQLite tracks the upload and its status.
3. Chat history is used to rewrite a follow-up question into a standalone query when needed.
   Vector and BM25 rankings are combined with reciprocal-rank fusion (`k=60`), then the
   cross-encoder reranks the candidates.
4. The stream begins with retrieved source metadata, followed by answer token events and a
   completion event. The system prompt treats document text as untrusted evidence, not
   instructions, and requires grounded inline citations.

The local `data/` directory contains the SQLite database, Chroma persistence, keyword index,
and original uploads. It is intentionally excluded from version control.
