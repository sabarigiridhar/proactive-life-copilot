"use client";

import {
  AlertCircle,
  Bot,
  CheckCircle2,
  MessageSquareText,
  Plus,
  RefreshCw,
  User,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  type ConversationMessage,
  type ConversationSummary,
  cancelDraft,
  confirmDraft,
  type DailyLogDraft,
  getConversation,
  getConversations,
  streamMessage,
} from "@/lib/api/client";
import { ChatComposer } from "./chat-composer";
import { DraftEditor } from "./draft-editor";

const ACTIVE_THREAD_KEY = "life-copilot.active-thread";

type CaptureSource = "text" | "voice" | "image" | "mixed";
type MessageMetadata = Record<string, unknown>;
type UiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  metadata?: MessageMetadata | null;
  streaming?: boolean;
};

function toUiMessage(message: ConversationMessage): UiMessage {
  return {
    id: String(message.id),
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    metadata: message.metadata as MessageMetadata | null | undefined,
  };
}

function pendingDraft(messages: UiMessage[]): DailyLogDraft | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const metadata = messages[index]?.metadata;
    if (metadata?.event === "confirmed_records" || metadata?.event === "draft_cancelled")
      return null;
    if (metadata?.draft && typeof metadata.draft === "object") {
      return metadata.draft as DailyLogDraft;
    }
  }
  return null;
}

function shortDate(value: string): string {
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

export function ChatWorkspace() {
  const [threads, setThreads] = useState<ConversationSummary[]>([]);
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [composer, setComposer] = useState("");
  const [source, setSource] = useState<CaptureSource>("text");
  const [draft, setDraft] = useState<DailyLogDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [lastFailed, setLastFailed] = useState<{ text: string; source: CaptureSource } | null>(
    null,
  );
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    const start = async () => {
      const result = await getConversations();
      if (cancelled) return;
      if (!result.ok) {
        setError(result.message);
        setLoading(false);
        return;
      }
      setThreads(result.data);
      const remembered = window.localStorage.getItem(ACTIVE_THREAD_KEY);
      const selected = result.data.some((item) => item.id === remembered)
        ? remembered
        : (result.data[0]?.id ?? null);
      if (selected) {
        const detail = await getConversation(selected);
        if (!cancelled && detail.ok) {
          const nextMessages = (detail.data.messages ?? []).map(toUiMessage);
          setActiveThread(selected);
          setMessages(nextMessages);
          setDraft(pendingDraft(nextMessages));
        } else if (!cancelled && !detail.ok) {
          setError(detail.message);
        }
      }
      if (!cancelled) setLoading(false);
    };
    void start();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (messages.length > 0 || draft) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [messages.length, draft]);

  const refreshThreads = async () => {
    const result = await getConversations();
    if (result.ok) setThreads(result.data);
  };

  const selectThread = async (threadId: string) => {
    if (busy || threadId === activeThread) return;
    setLoading(true);
    setError(null);
    setSavedNotice(null);
    const result = await getConversation(threadId);
    if (result.ok) {
      const nextMessages = (result.data.messages ?? []).map(toUiMessage);
      setActiveThread(threadId);
      setMessages(nextMessages);
      setDraft(pendingDraft(nextMessages));
      window.localStorage.setItem(ACTIVE_THREAD_KEY, threadId);
    } else {
      setError(result.message);
    }
    setLoading(false);
  };

  const newConversation = () => {
    if (busy) return;
    setActiveThread(null);
    setMessages([]);
    setDraft(null);
    setError(null);
    setSavedNotice(null);
    setComposer("");
    setSource("text");
    window.localStorage.removeItem(ACTIVE_THREAD_KEY);
  };

  const send = async (text = composer, captureSource = source) => {
    const message = text.trim();
    if (!message || busy) return;
    const stamp = Date.now();
    const userId = `local-user-${stamp}`;
    const assistantId = `local-assistant-${stamp}`;
    setBusy(true);
    setError(null);
    setSavedNotice(null);
    setLastFailed(null);
    setComposer("");
    setSource("text");
    setMessages((current) => [
      ...current,
      {
        id: userId,
        role: "user",
        content: message,
        createdAt: new Date().toISOString(),
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
        streaming: true,
      },
    ]);

    try {
      const result = await streamMessage(
        {
          thread_id: activeThread,
          message,
          source: captureSource,
        },
        {
          onStatus: () => setStatus("Thinking through your records…"),
          onDelta: (delta) =>
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId ? { ...item, content: item.content + delta } : item,
              ),
            ),
        },
      );
      const metadata: MessageMetadata = {
        response_type: result.response_type,
        draft: result.draft,
        evidence: result.evidence,
        date_range: result.date_range,
        confidence: result.confidence,
      };
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? { ...item, content: result.assistant_text, metadata, streaming: false }
            : item,
        ),
      );
      setDraft(result.draft ?? null);
      setActiveThread(result.thread_id);
      window.localStorage.setItem(ACTIVE_THREAD_KEY, result.thread_id);
      await refreshThreads();
    } catch (sendError) {
      setMessages((current) =>
        current.filter((item) => item.id !== userId && item.id !== assistantId),
      );
      setComposer(message);
      setSource(captureSource);
      setLastFailed({ text: message, source: captureSource });
      setError(sendError instanceof Error ? sendError.message : "The message could not be sent.");
    } finally {
      setBusy(false);
      setStatus("");
    }
  };

  const saveDraft = async (editedDraft: DailyLogDraft) => {
    if (!activeThread) {
      setDraftError("The conversation ID is missing. Send the message again before confirming.");
      return;
    }
    setConfirming(true);
    setDraftError(null);
    const result = await confirmDraft(activeThread, editedDraft);
    if (result.ok) {
      setDraft(null);
      setMessages((current) => [
        ...current,
        {
          id: `confirmation-${Date.now()}`,
          role: "assistant",
          content: result.data.assistant_text,
          createdAt: new Date().toISOString(),
          metadata: { event: "confirmed_records" },
        },
      ]);
      setSavedNotice(result.data.assistant_text);
      await refreshThreads();
    } else {
      setDraftError(result.message);
    }
    setConfirming(false);
  };

  const cancelPendingDraft = async () => {
    if (!activeThread) {
      setDraft(null);
      return;
    }
    setConfirming(true);
    setDraftError(null);
    const result = await cancelDraft(activeThread);
    if (result.ok) {
      setDraft(null);
      setMessages((current) => [
        ...current,
        {
          id: `cancellation-${Date.now()}`,
          role: "assistant",
          content: result.data.assistant_text,
          createdAt: new Date().toISOString(),
          metadata: { event: "draft_cancelled" },
        },
      ]);
      await refreshThreads();
    } else {
      setDraftError(result.message);
    }
    setConfirming(false);
  };

  return (
    <div className="chat-page">
      <aside className="thread-panel" aria-label="Conversations">
        <div className="thread-panel-heading">
          <div>
            <p className="eyebrow">History</p>
            <h1>Copilot</h1>
          </div>
          <button
            className="new-thread-button"
            type="button"
            onClick={newConversation}
            disabled={busy}
          >
            <Plus size={16} aria-hidden="true" /> New
          </button>
        </div>
        <ul className="thread-list">
          {threads.length === 0 ? (
            <li className="thread-empty">
              Your conversations will appear here after your first message.
            </li>
          ) : (
            threads.map((thread) => (
              <li key={thread.id}>
                <button
                  className="thread-item"
                  type="button"
                  aria-current={thread.id === activeThread ? "true" : undefined}
                  onClick={() => void selectThread(thread.id)}
                >
                  <span>{thread.title}</span>
                  <small>
                    {shortDate(thread.updated_at)} · {thread.message_count} messages
                  </small>
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>

      <section className="conversation-panel" aria-labelledby="conversation-title">
        <header className="conversation-heading">
          <div>
            <p className="eyebrow">Private workspace</p>
            <h2 id="conversation-title">
              {activeThread
                ? (threads.find((item) => item.id === activeThread)?.title ?? "Conversation")
                : "New conversation"}
            </h2>
          </div>
          <span className="stream-badge">
            <span aria-hidden="true" /> Live responses
          </span>
        </header>

        {error && (
          <div className="chat-alert" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
            {lastFailed && (
              <button type="button" onClick={() => void send(lastFailed.text, lastFailed.source)}>
                <RefreshCw size={14} aria-hidden="true" /> Retry
              </button>
            )}
          </div>
        )}
        {savedNotice && (
          <div className="chat-success" role="status">
            <CheckCircle2 size={18} aria-hidden="true" /> {savedNotice}
          </div>
        )}
        <div className="sr-only" aria-live="polite">
          {status}
        </div>

        <div className="message-view" aria-busy={loading || busy}>
          {loading ? (
            <div className="chat-welcome">
              <RefreshCw className="spinner" aria-hidden="true" /> Loading conversation…
            </div>
          ) : messages.length === 0 ? (
            <div className="chat-welcome">
              <span className="welcome-icon">
                <MessageSquareText size={26} aria-hidden="true" />
              </span>
              <h3>Capture naturally.</h3>
              <p>
                Tell me what happened today, upload a receipt, record a note, or ask a question
                about your records.
              </p>
              <div className="prompt-grid">
                <button
                  type="button"
                  onClick={() => setComposer("I slept 8 hours and went for a 30 minute run.")}
                >
                  Log health
                </button>
                <button
                  type="button"
                  onClick={() => setComposer("I spent 450 INR on groceries at the market.")}
                >
                  Log spending
                </button>
                <button type="button" onClick={() => setComposer("What did I spend this week?")}>
                  Ask a question
                </button>
              </div>
            </div>
          ) : (
            <ol className="message-list" aria-label="Conversation messages">
              {messages.map((message) => {
                const evidence = Array.isArray(message.metadata?.evidence)
                  ? message.metadata.evidence
                  : [];
                return (
                  <li className={`message-row message-${message.role}`} key={message.id}>
                    <span className="message-avatar" aria-hidden="true">
                      {message.role === "assistant" ? <Bot size={16} /> : <User size={16} />}
                    </span>
                    <div className="message-content">
                      <div className="message-meta">
                        <strong>{message.role === "assistant" ? "Life Copilot" : "You"}</strong>
                        <time dateTime={message.createdAt}>{shortDate(message.createdAt)}</time>
                      </div>
                      <p>{message.content || (message.streaming ? "Thinking…" : "")}</p>
                      {evidence.length > 0 && (
                        <details className="evidence-panel">
                          <summary>
                            {evidence.length} supporting record{evidence.length === 1 ? "" : "s"}
                          </summary>
                          <pre>{JSON.stringify(evidence, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
          <div ref={endRef} />
        </div>

        {draft && (
          <DraftEditor
            draft={draft}
            busy={confirming}
            error={draftError}
            onConfirm={(editedDraft) => void saveDraft(editedDraft)}
            onCancel={() => void cancelPendingDraft()}
          />
        )}

        <ChatComposer
          value={composer}
          source={source}
          busy={busy || confirming}
          onChange={setComposer}
          onSourceChange={setSource}
          onSubmit={() => void send()}
        />
      </section>
    </div>
  );
}
