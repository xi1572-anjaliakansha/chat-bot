"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { CHAT_URL } from "@/lib/urls";

type Role = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
};

function useDocSession() {
  const searchParams = useSearchParams();
  const docIdFromQuery = searchParams.get("docId");
  const docNameFromQuery = searchParams.get("doc");
  const [docId, setDocId] = useState<string | null>(null);
  const [docName, setDocName] = useState<string | null>(null);

  useEffect(() => {
    if (docIdFromQuery) {
      setDocId(docIdFromQuery);
    } else if (typeof window !== "undefined") {
      const storedId = sessionStorage.getItem("lastUploadedDocId");
      if (storedId) setDocId(storedId);
    }

    if (docNameFromQuery) {
      setDocName(docNameFromQuery);
    } else if (typeof window !== "undefined") {
      const storedName = sessionStorage.getItem("lastUploadedFile");
      if (storedName) setDocName(storedName);
    }
  }, [docIdFromQuery, docNameFromQuery]);

  return { docId, docName };
}

export function ChatClient() {
  const { docId, docName } = useDocSession();
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      content:
        docName && docId
          ? `You uploaded “${docName}”. Ask me anything about it.`
          : docName
            ? `You uploaded “${docName}”, but no document session was found. Go back and upload again.`
            : "Upload a document from the home page, then ask questions about it here.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!docName) return;
    setMessages((prev) => {
      if (prev[0]?.id !== "welcome") return prev;
      const content =
        docId && docName
          ? `You uploaded “${docName}”. Ask me anything about it.`
          : docName
            ? `You uploaded “${docName}”, but no document session was found. Go back and upload again.`
            : prev[0].content;
      return [{ id: "welcome", role: "assistant", content }, ...prev.slice(1)];
    });
  }, [docName, docId]);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, sending]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending || !docId) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    setInput("");
    setMessages((m) => [...m, userMsg]);
    setSending(true);

    try {
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, docId, docName }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        reply?: string;
        error?: string;
      };
      if (!res.ok) {
        throw new Error(data.error || "Request failed");
      }
      const reply =
        typeof data.reply === "string"
          ? data.reply
          : "No reply from server.";
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "assistant", content: reply },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            e instanceof Error
              ? `Error: ${e.message}`
              : "Something went wrong.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }, [input, sending, docId, docName]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="flex min-h-[100dvh] flex-col bg-[var(--page-bg)]">
      <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link
            href="/"
            className="text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            ← Back
          </Link>
          <h1 className="truncate text-center text-sm font-semibold text-[var(--text-primary)] sm:text-base">
            Chat
          </h1>
          <span className="w-14" aria-hidden />
        </div>
        {docName || docId ? (
          <p className="mx-auto max-w-3xl truncate px-4 pb-2 text-center text-xs text-[var(--text-muted)] sm:px-6">
            {docName ? <>Document: {docName}</> : null}
            {!docId && docName ? (
              <span className="block text-amber-700 dark:text-amber-400">
                Session expired — upload again from home.
              </span>
            ) : null}
          </p>
        ) : null}
      </header>

      <div
        ref={listRef}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 overflow-y-auto px-4 py-6 sm:px-6"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                m.role === "user"
                  ? "bg-[var(--accent)] text-white"
                  : "border border-[var(--border)] bg-[var(--surface)] text-[var(--text-primary)]"
              }`}
            >
              <p className="whitespace-pre-wrap break-words">{m.content}</p>
            </div>
          </div>
        ))}
        {sending ? (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--text-muted)]">
              Thinking…
            </div>
          </div>
        ) : null}
      </div>

      <div className="sticky bottom-0 border-t border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
        <div className="mx-auto flex max-w-3xl gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message… (Enter to send, Shift+Enter for newline)"
            rows={2}
            disabled={sending}
            className="min-h-[44px] flex-1 resize-y rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-ring)] disabled:opacity-60"
            aria-label="Message"
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={sending || !input.trim() || !docId}
            className="shrink-0 self-end rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] disabled:pointer-events-none disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
