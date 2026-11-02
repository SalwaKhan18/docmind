import {
  ArrowUp,
  Check,
  ChevronDown,
  FileText,
  FolderOpen,
  LoaderCircle,
  Menu,
  MessageSquare,
  Moon,
  PanelLeftClose,
  Plus,
  Search,
  Send,
  Sun,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";

import { api } from "./api/client";
import { CitedMarkdown } from "./components/CitedMarkdown";
import { useChatStream } from "./hooks/useChatStream";
import type { Conversation, DebugChunk, DocumentItem, Message, Source } from "./types";

function makeMessage(role: Message["role"], content: string, sources: Source[] = []): Message {
  return {
    id: crypto.randomUUID(),
    conversation_id: "",
    role,
    content,
    sources,
    created_at: new Date().toISOString(),
  };
}

function App() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [debugChunks, setDebugChunks] = useState<DebugChunk[]>([]);
  const [debugOpen, setDebugOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(
    () => localStorage.getItem("docmind-theme") !== "light",
  );
  const [dragging, setDragging] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectionInitialized = useRef(false);
  const { send, stop, isStreaming, error, clearError } = useChatStream();

  const refreshDocuments = useCallback(async () => {
    try {
      const rows = await api.listDocuments();
      setDocuments(rows);
      setSelectedDocs((current) => {
        const valid = current.filter((id) => rows.some((row) => row.id === id));
        if (!selectionInitialized.current) {
          selectionInitialized.current = true;
          return rows.map((row) => row.id);
        }
        return valid;
      });
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not load documents");
    }
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not load conversations");
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
    void refreshConversations();
  }, [refreshDocuments, refreshConversations]);

  useEffect(() => {
    if (!documents.some((document) => document.status === "processing")) return;
    const timer = window.setInterval(() => void refreshDocuments(), 1800);
    return () => window.clearInterval(timer);
  }, [documents, refreshDocuments]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    localStorage.setItem("docmind-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  useEffect(() => {
    if (error) {
      setToast(error);
      clearError();
    }
  }, [error, clearError]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function upload(files: FileList | File[]) {
    const chosen = Array.from(files);
    if (!chosen.length) return;
    setUploading(true);
    try {
      const result = await api.uploadDocuments(chosen);
      setSelectedDocs((current) => [...new Set([...current, ...result.documents.map((doc) => doc.id)])]);
      await refreshDocuments();
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files);
  }

  async function removeDocument(document: DocumentItem) {
    try {
      await api.deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setSelectedDocs((current) => current.filter((id) => id !== document.id));
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not delete the document");
    }
  }

  function newConversation() {
    stop();
    setConversationId(undefined);
    setMessages([]);
    setDebugChunks([]);
    setDraft("");
    setSidebarOpen(false);
  }

  async function openConversation(conversation: Conversation) {
    stop();
    try {
      const rows = await api.getMessages(conversation.id);
      setConversationId(conversation.id);
      setMessages(rows);
      setDebugChunks([]);
      setSidebarOpen(false);
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not open conversation");
    }
  }

  async function removeConversation(conversation: Conversation) {
    try {
      await api.deleteConversation(conversation.id);
      setConversations((current) => current.filter((item) => item.id !== conversation.id));
      if (conversation.id === conversationId) newConversation();
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not delete conversation");
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isStreaming) return;
    if (!documents.length || documents.every((doc) => doc.status !== "ready")) {
      setToast("Add a document and wait for it to finish indexing before asking a question.");
      return;
    }
    if (selectedDocs.length === 0) {
      setToast("Select at least one document to search.");
      return;
    }
    const userMessage = makeMessage("user", question);
    const assistantMessage = makeMessage("assistant", "");
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setDraft("");
    setDebugChunks([]);
    void send(
      { question, conversation_id: conversationId, document_ids: selectedDocs },
      {
        onSources: (sources, debug) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessage.id ? { ...message, sources } : message,
            ),
          );
          setDebugChunks(debug);
        },
        onToken: (token) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessage.id
                ? { ...message, content: message.content + token }
                : message,
            ),
          );
        },
        onDone: (id) => {
          if (id) setConversationId(id);
          void refreshConversations();
        },
      },
    );
  }

  const readyDocuments = documents.filter((document) => document.status === "ready").length;

  return (
    <main className="app-shell">
      {sidebarOpen && <button className="mobile-backdrop" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><Search size={19} strokeWidth={2.5} /></div>
          <div className="brand-name">docmind<span>.</span></div>
          <button className="icon-button sidebar-collapse" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)}>
            <PanelLeftClose size={18} />
          </button>
        </div>

        <button className="new-chat-button" onClick={newConversation}>
          <Plus size={17} /> New conversation <span>⌘ K</span>
        </button>

        <section className="sidebar-section">
          <div className="section-heading">
            <span>YOUR LIBRARY</span>
            <span className="section-count">{documents.length}</span>
          </div>
          <div
            className={`upload-zone ${dragging ? "upload-zone-active" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileInput.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") fileInput.current?.click();
            }}
          >
            {uploading ? <LoaderCircle className="spin" size={19} /> : <Upload size={19} />}
            <span><strong>{uploading ? "Uploading…" : "Drop files to add"}</strong><small>PDF, DOCX, TXT, MD · up to 20 MB</small></span>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md"
              onChange={(event) => event.target.files && void upload(event.target.files)}
              hidden
            />
          </div>
          <div className="document-list">
            {documents.length === 0 ? (
              <div className="sidebar-empty"><FolderOpen size={18} /> Your documents will appear here</div>
            ) : documents.map((document) => (
              <div className="document-row" key={document.id}>
                <input
                  type="checkbox"
                  aria-label={`Search ${document.filename}`}
                  checked={selectedDocs.includes(document.id)}
                  disabled={document.status !== "ready"}
                  onChange={() => setSelectedDocs((current) =>
                    current.includes(document.id)
                      ? current.filter((id) => id !== document.id)
                      : [...current, document.id],
                  )}
                />
                <FileText size={16} className="document-icon" />
                <div className="document-info">
                  <span className="document-name" title={document.filename}>{document.filename}</span>
                  <span className={`document-status status-${document.status}`}>
                    {document.status === "processing" && <LoaderCircle size={11} className="spin" />}
                    {document.status === "ready" && <Check size={11} />}
                    {document.status === "error" ? "Indexing failed" : document.status === "ready" ? `${document.chunk_count} chunks` : "Indexing"}
                  </span>
                  {document.error && <span className="document-error" title={document.error}>{document.error}</span>}
                </div>
                <button className="row-action" aria-label={`Delete ${document.filename}`} onClick={() => void removeDocument(document)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="sidebar-section conversation-section">
          <div className="section-heading"><span>RECENT CHATS</span><ChevronDown size={14} /></div>
          <div className="conversation-list">
            {conversations.length === 0 ? (
              <div className="sidebar-empty"><MessageSquare size={17} /> No conversations yet</div>
            ) : conversations.map((conversation) => (
              <div className={`conversation-row ${conversation.id === conversationId ? "conversation-active" : ""}`} key={conversation.id}>
                <button className="conversation-open" onClick={() => void openConversation(conversation)}>
                  <MessageSquare size={15} /><span>{conversation.title}</span>
                </button>
                <button className="row-action" aria-label={`Delete conversation ${conversation.title}`} onClick={() => void removeConversation(conversation)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <div className="sidebar-footer">
          <div className="status-indicator"><span /> {readyDocuments} indexed {readyDocuments === 1 ? "document" : "documents"}</div>
          <div className="footer-note">Your files stay on this machine.</div>
        </div>
      </aside>

      <section className="chat-panel">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open sidebar" onClick={() => setSidebarOpen(true)}><Menu size={19} /></button>
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-divider">/</span><strong>{conversationId ? conversations.find((item) => item.id === conversationId)?.title ?? "Conversation" : "New conversation"}</strong></div>
          <div className="topbar-actions">
            <span className="privacy-label"><span /> Private workspace</span>
            <button className="theme-toggle" aria-label="Toggle color theme" onClick={() => setDarkMode((value) => !value)}>
              {darkMode ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <div className="avatar">D</div>
          </div>
        </header>

        <div className={`conversation-content ${messages.length ? "conversation-content-active" : ""}`}>
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-eyebrow"><span className="sparkle">✳</span> YOUR DOCUMENTS, IN CONTEXT</div>
              <h1>Answers that know<br /><span>where they came from.</span></h1>
              <p>Ask a question across your documents. DocMind finds the relevant passages and cites every answer back to its source.</p>
              <div className="welcome-cards">
                <button onClick={() => setDraft("What are the key points in my documents?")}><span className="suggestion-icon mint-icon"><FileText size={17} /></span><span><strong>Find the key points</strong><small>Get a clear summary of your files</small></span><ArrowUp size={15} /></button>
                <button onClick={() => setDraft("Compare the main ideas across my documents.")}><span className="suggestion-icon violet-icon"><Search size={17} /></span><span><strong>Compare documents</strong><small>Surface differences and connections</small></span><ArrowUp size={15} /></button>
                <button onClick={() => setDraft("What should I know before getting started?")}><span className="suggestion-icon amber-icon"><MessageSquare size={17} /></span><span><strong>Ask a question</strong><small>Get an answer with page citations</small></span><ArrowUp size={15} /></button>
              </div>
              {documents.length === 0 && <div className="welcome-hint"><Upload size={15} /> Start by adding a document in your library</div>}
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message, index) => (
                <article className={`message ${message.role === "user" ? "message-user" : "message-assistant"}`} key={message.id}>
                  {message.role === "assistant" && <div className="assistant-avatar"><Search size={15} /></div>}
                  <div className="message-body">
                    <div className="message-label">{message.role === "user" ? "You" : "DocMind"}{message.role === "assistant" && message.sources.length > 0 && <span>{message.sources.length} sources</span>}</div>
                    <div className="message-content">
                      {message.role === "assistant" ? (
                        message.content ? <CitedMarkdown content={message.content} sources={message.sources} onCitation={setActiveSource} /> :
                          isStreaming && index === messages.length - 1 ? <span className="typing-indicator"><i /><i /><i /></span> : <span className="muted-answer">No response generated.</span>
                      ) : <p>{message.content}</p>}
                    </div>
                  </div>
                </article>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="composer-wrap">
          {debugChunks.length > 0 && (
            <div className="debug-toggle-row">
              <button className={`debug-toggle ${debugOpen ? "debug-toggle-active" : ""}`} onClick={() => setDebugOpen((value) => !value)}>
                <Search size={13} /> Retrieval debug <span>{debugChunks.length}</span>
              </button>
            </div>
          )}
          {debugOpen && (
            <div className="debug-panel">
              <div className="debug-panel-title">Retrieved chunks <button onClick={() => setDebugOpen(false)} aria-label="Close retrieval debug"><X size={14} /></button></div>
              {debugChunks.map((chunk, index) => (
                <div className="debug-chunk" key={`${chunk.id}-${index}`}>
                  <div><strong>{chunk.filename}</strong><span>p. {chunk.page}</span></div>
                  <p>{chunk.snippet}</p>
                  <small>Vector {formatScore(chunk.vector_score)} · BM25 {formatScore(chunk.bm25_score)} · Rerank {formatScore(chunk.rerank_score)}</small>
                </div>
              ))}
            </div>
          )}
          <form className="composer" onSubmit={submit}>
            <textarea
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={documents.length ? "Ask anything about your documents…" : "Add a document to start chatting…"}
              aria-label="Ask your documents"
            />
            <div className="composer-controls">
              <span><span className="selection-dot" /> Searching {selectedDocs.length} {selectedDocs.length === 1 ? "source" : "sources"}</span>
              {isStreaming ? (
                <button className="stop-button" type="button" onClick={stop}><span /> Stop generating</button>
              ) : (
                <button className="send-button" type="submit" disabled={!draft.trim()} aria-label="Send message"><Send size={15} /></button>
              )}
            </div>
          </form>
          <div className="composer-disclaimer">DocMind answers from your files. Always check the cited source.</div>
        </div>
      </section>

      {activeSource && (
        <div className="drawer-backdrop" onClick={() => setActiveSource(null)} role="presentation">
          <aside className="source-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-header">
              <div><span className="drawer-kicker">CITED SOURCE</span><h2>Source passage</h2></div>
              <button className="icon-button" onClick={() => setActiveSource(null)} aria-label="Close source drawer"><X size={18} /></button>
            </div>
            <div className="source-file-card">
              <div className="file-badge"><FileText size={18} /></div>
              <div><strong>{activeSource.filename}</strong><span>Page {activeSource.page}</span></div>
            </div>
            <div className="source-snippet-label">RETRIEVED EXCERPT</div>
            <blockquote>{activeSource.snippet}</blockquote>
            <div className="source-scores">
              <span>Vector similarity <strong>{formatScore(activeSource.vector_score)}</strong></span>
              <span>BM25 relevance <strong>{formatScore(activeSource.bm25_score)}</strong></span>
              <span>Reranker score <strong>{formatScore(activeSource.rerank_score)}</strong></span>
            </div>
          </aside>
        </div>
      )}
      {toast && <div className="toast" role="alert"><span className="toast-mark">!</span>{toast}<button onClick={() => setToast(null)} aria-label="Dismiss notification"><X size={15} /></button></div>}
    </main>
  );
}

function formatScore(score: number | null): string {
  return score === null ? "—" : score.toFixed(3);
}

export default App;
