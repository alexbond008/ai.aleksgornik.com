"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { streamChat, type Message } from "@/lib/api";

interface Props {
  token: string;
  userName: string;
}

const STARTERS = [
  "Should I do EE or CS — what's the actual difference?",
  "How do I land my first engineering internship with no experience?",
  "I'm struggling with maths in first year. Am I cooked?",
  "What would you do differently if you started your degree again?",
];

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full"
          style={{
            background: "var(--gold)",
            opacity: 0.6,
            animation: `blink 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

function MessageBubble({ msg, isLast }: { msg: Message; isLast: boolean }) {
  const isUser = msg.role === "user";

  if (isUser) {
    return (
      <div className={`flex justify-end ${isLast ? "msg-in" : ""}`}>
        <div
          className="max-w-[75%] rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed"
          style={{
            background: "var(--surface-3)",
            border: "1px solid var(--border-hi)",
            color: "var(--fg)",
          }}
        >
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 ${isLast ? "msg-in" : ""}`}>
      {/* Avatar */}
      <div className="flex-shrink-0 mt-1">
        <div
          className="h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold"
          style={{
            background: "linear-gradient(135deg, rgba(201,168,76,0.15), rgba(201,168,76,0.05))",
            border: "1px solid rgba(201,168,76,0.25)",
            color: "var(--gold)",
            boxShadow: "0 0 10px rgba(201,168,76,0.12)",
          }}
        >
          A
        </div>
      </div>
      <div
        className="flex-1 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap"
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          color: "var(--fg)",
        }}
      >
        {msg.content}
      </div>
    </div>
  );
}

export function ChatPage({ token, userName }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<boolean>(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || streaming) return;
      setError("");

      const userMsg: Message = { role: "user", content: text.trim() };
      const nextMessages = [...messages, userMsg];
      setMessages(nextMessages);
      setInput("");
      setStreaming(true);
      abortRef.current = false;

      // placeholder assistant message
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      try {
        for await (const event of streamChat(token, nextMessages)) {
          if (abortRef.current) break;
          if (event.type === "remaining") {
            setRemaining(event.value);
          } else if (event.type === "text") {
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy[copy.length - 1];
              if (last.role === "assistant") {
                copy[copy.length - 1] = { ...last, content: last.content + event.value };
              }
              return copy;
            });
          } else if (event.type === "done") {
            break;
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Something went wrong";
        setError(msg);
        // Remove empty placeholder if we errored immediately
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last.role === "assistant" && !last.content) return prev.slice(0, -1);
          return prev;
        });
      } finally {
        setStreaming(false);
        setTimeout(() => inputRef.current?.focus(), 50);
      }
    },
    [messages, streaming, token]
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--bg)" }}>

      {/* ── Top bar ── */}
      <header
        className="flex-shrink-0 flex items-center justify-between px-6 py-3.5"
        style={{
          background: "rgba(6,6,8,0.85)",
          backdropFilter: "blur(20px)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-xl flex items-center justify-center text-sm font-bold"
            style={{
              background: "linear-gradient(135deg, rgba(201,168,76,0.18), rgba(201,168,76,0.06))",
              border: "1px solid rgba(201,168,76,0.22)",
              color: "var(--gold)",
              boxShadow: "0 0 14px rgba(201,168,76,0.12)",
            }}
          >
            A
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold" style={{ color: "var(--fg)" }}>AI Aleks</span>
            <span className="text-xs" style={{ color: "var(--fg-muted)" }}>Trained on 87+ videos</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {remaining !== null && (
            <div
              className="flex items-center gap-1.5 rounded-full px-3 py-1"
              style={{
                background: remaining <= 2 ? "rgba(220,60,60,0.1)" : "rgba(201,168,76,0.07)",
                border: `1px solid ${remaining <= 2 ? "rgba(220,60,60,0.25)" : "rgba(201,168,76,0.15)"}`,
              }}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: remaining <= 2 ? "#dc3c3c" : "var(--gold)" }}
              />
              <span
                className="text-xs font-medium"
                style={{ color: remaining <= 2 ? "#f87171" : "var(--gold)" }}
              >
                {remaining} left today
              </span>
            </div>
          )}
          <a
            href="https://youtube.com/@aleksgornik"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs transition-colors hover:text-[var(--gold)]"
            style={{ color: "var(--fg-muted)" }}
          >
            YouTube ↗
          </a>
        </div>
      </header>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-6 flex flex-col gap-4 min-h-full">

          {isEmpty ? (
            /* ── Empty state ── */
            <div className="flex flex-col items-center justify-center flex-1 gap-8 py-16">
              {/* Ambient glow behind avatar */}
              <div className="relative flex items-center justify-center">
                <div
                  className="absolute h-28 w-28 rounded-full"
                  style={{
                    background: "radial-gradient(circle, rgba(201,168,76,0.18) 0%, transparent 70%)",
                    animation: "orb-float 4s ease-in-out infinite",
                  }}
                />
                <div
                  className="relative h-16 w-16 rounded-2xl flex items-center justify-center text-2xl font-bold"
                  style={{
                    background: "linear-gradient(135deg, rgba(201,168,76,0.15), rgba(201,168,76,0.05))",
                    border: "1px solid rgba(201,168,76,0.25)",
                    color: "var(--gold)",
                    boxShadow: "0 0 30px rgba(201,168,76,0.15)",
                  }}
                >
                  A
                </div>
              </div>

              <div className="text-center flex flex-col gap-2">
                <h2 className="text-xl font-semibold" style={{ color: "var(--fg)" }}>
                  Hey{userName ? `, ${userName.split(" ")[0]}` : ""}! I&apos;m AI Aleks.
                </h2>
                <p className="text-sm max-w-sm" style={{ color: "var(--fg-muted)" }}>
                  Ask me anything Aleks has covered — engineering degrees, internships, career strategy, or
                  what he&apos;d actually do differently.
                </p>
              </div>

              {/* Starter questions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg">
                {STARTERS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    disabled={streaming}
                    className="text-left rounded-xl px-4 py-3 text-xs leading-relaxed transition-all duration-200 group"
                    style={{
                      background: "var(--surface-1)",
                      border: "1px solid var(--border-hi)",
                      color: "var(--fg-muted)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(201,168,76,0.25)";
                      (e.currentTarget as HTMLButtonElement).style.color = "var(--fg)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-hi)";
                      (e.currentTarget as HTMLButtonElement).style.color = "var(--fg-muted)";
                    }}
                  >
                    <span
                      className="block text-[10px] font-semibold tracking-widest uppercase mb-1.5"
                      style={{ color: "var(--gold)", opacity: 0.7 }}
                    >
                      Ask →
                    </span>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* ── Message list ── */
            <>
              {messages.map((msg, i) => {
                const isLast = i === messages.length - 1;
                const isStreamingPlaceholder = isLast && msg.role === "assistant" && streaming && !msg.content;
                if (isStreamingPlaceholder) {
                  return (
                    <div key={i} className="flex gap-3 msg-in">
                      <div className="flex-shrink-0 mt-1">
                        <div
                          className="h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold"
                          style={{
                            background: "linear-gradient(135deg, rgba(201,168,76,0.15), rgba(201,168,76,0.05))",
                            border: "1px solid rgba(201,168,76,0.25)",
                            color: "var(--gold)",
                          }}
                        >
                          A
                        </div>
                      </div>
                      <div
                        className="rounded-2xl rounded-tl-sm px-4 py-3"
                        style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
                      >
                        <TypingDots />
                      </div>
                    </div>
                  );
                }
                return <MessageBubble key={i} msg={msg} isLast={isLast && !streaming} />;
              })}
            </>
          )}

          {error && (
            <div
              className="text-sm text-center py-2 rounded-lg"
              style={{ color: "#f87171", background: "rgba(220,60,60,0.07)", border: "1px solid rgba(220,60,60,0.15)" }}
            >
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input bar ── */}
      <div
        className="flex-shrink-0"
        style={{
          background: "rgba(6,6,8,0.92)",
          backdropFilter: "blur(24px)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div
            className="flex items-end gap-3 rounded-2xl px-4 py-3 transition-all"
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border-hi)",
            }}
            onFocus={() => {
              // handled by CSS .input-gold
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Aleks anything..."
              rows={1}
              disabled={streaming}
              className="flex-1 resize-none bg-transparent text-sm leading-relaxed focus:outline-none disabled:opacity-50"
              style={{
                color: "var(--fg)",
                caretColor: "var(--gold)",
                maxHeight: "120px",
                minHeight: "24px",
                overflowY: "auto",
              }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "24px";
                el.style.height = Math.min(el.scrollHeight, 120) + "px";
              }}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || streaming}
              className="flex-shrink-0 h-8 w-8 rounded-xl flex items-center justify-center transition-all duration-200 disabled:opacity-30"
              style={{
                background: input.trim() && !streaming ? "var(--gold)" : "var(--surface-3)",
                color: input.trim() && !streaming ? "#000" : "var(--fg-muted)",
              }}
              aria-label="Send"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L13 7L7 13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M1 7H13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          <p className="text-center text-xs mt-2" style={{ color: "var(--fg-subtle)" }}>
            Shift+Enter for new line · Enter to send · AI can make mistakes
          </p>
        </div>
      </div>

    </div>
  );
}
