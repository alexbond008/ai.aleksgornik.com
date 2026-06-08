"use client";

import { useState, useRef, useEffect } from "react";
import { register } from "@/lib/api";

interface Props {
  onSuccess: (token: string, name: string) => void;
}

const SUGGESTED = [
  "How do I break into data science with no experience?",
  "What's the best way to find internships as an EE student?",
  "Is a master's degree worth it in 2025?",
  "How did you go from EE to software engineering?",
];

export function GatePage({ onSuccess }: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [typedQ, setTypedQ] = useState("");
  const [qIndex, setQIndex] = useState(0);
  const nameRef = useRef<HTMLInputElement>(null);

  // Typewriter cycling through suggested questions
  useEffect(() => {
    const q = SUGGESTED[qIndex];
    let i = 0;
    setTypedQ("");
    const interval = setInterval(() => {
      i++;
      setTypedQ(q.slice(0, i));
      if (i >= q.length) {
        clearInterval(interval);
        setTimeout(() => {
          // erase
          let j = q.length;
          const erase = setInterval(() => {
            j--;
            setTypedQ(q.slice(0, j));
            if (j <= 0) {
              clearInterval(erase);
              setQIndex((prev) => (prev + 1) % SUGGESTED.length);
            }
          }, 18);
        }, 2400);
      }
    }, 36);
    return () => clearInterval(interval);
  }, [qIndex]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !email.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await register(name.trim(), email.trim());
      onSuccess(res.token, name.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center justify-center overflow-hidden">

      {/* ── Ambient orbs ── */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background: [
            "radial-gradient(ellipse 80% 70% at 50% 45%, rgba(9,60,180,0.13) 0%, transparent 65%)",
            "radial-gradient(ellipse 45% 55% at 15% 70%, rgba(201,168,76,0.07) 0%, transparent 60%)",
            "radial-gradient(ellipse 50% 40% at 85% 20%, rgba(201,168,76,0.05) 0%, transparent 55%)",
          ].join(", "),
        }}
      />

      {/* ── Grid ── */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
        }}
      />

      {/* ── Gold edge glow — top ── */}
      <div
        className="pointer-events-none absolute top-0 left-0 right-0 h-px z-10"
        style={{ background: "linear-gradient(90deg, transparent, rgba(201,168,76,0.4), transparent)" }}
      />

      <div className="relative z-10 w-full max-w-5xl mx-auto px-6 py-20 flex flex-col items-center gap-16">

        {/* ── Header ── */}
        <div className="flex flex-col items-center gap-5 text-center max-w-3xl">

          {/* Eyebrow badge */}
          <div
            className="inline-flex items-center gap-2.5 rounded-full px-4 py-1.5"
            style={{
              background: "rgba(201,168,76,0.08)",
              border: "1px solid rgba(201,168,76,0.18)",
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background: "var(--gold)",
                boxShadow: "0 0 6px rgba(201,168,76,0.8)",
                animation: "blink 1.4s ease-in-out infinite",
              }}
            />
            <span
              className="text-xs font-semibold tracking-widest uppercase"
              style={{ color: "var(--gold)" }}
            >
              Powered by Aleks&apos;s entire YouTube library
            </span>
          </div>

          {/* Headline */}
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]">
            <span className="gradient-text">Ask Aleks.</span>
            <br />
            <span style={{ color: "var(--fg)" }}>Get the honest answer.</span>
          </h1>

          {/* Sub */}
          <p className="text-lg leading-relaxed max-w-[520px]" style={{ color: "var(--fg-muted)" }}>
            I can&apos;t reply to every comment. So I built an AI trained on everything I&apos;ve ever said
            — every video, every career story, every piece of advice. Ask it anything.
          </p>

          {/* Typewriter demo */}
          <div
            className="w-full max-w-xl rounded-xl px-5 py-3.5 text-left text-sm font-mono flex items-center gap-3"
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border-hi)",
              color: "var(--fg-muted)",
            }}
          >
            <span style={{ color: "var(--gold)", opacity: 0.7 }}>›</span>
            <span className="flex-1 min-h-[1.25em]">
              {typedQ}
              <span className="cursor-blink" style={{ color: "var(--gold)" }}>|</span>
            </span>
          </div>
        </div>

        {/* ── Gate form ── */}
        <div
          className="glass-gold w-full max-w-md rounded-2xl p-8 flex flex-col gap-6"
          style={{ boxShadow: "0 24px 80px -20px rgba(0,0,0,0.6), 0 0 0 1px rgba(201,168,76,0.10)" }}
        >
          {/* Form header */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2.5 mb-1">
              <div
                className="h-8 w-8 rounded-lg flex items-center justify-center"
                style={{ background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.2)" }}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 1.5L10 5.5H14L10.9 7.9L12 12L8 9.5L4 12L5.1 7.9L2 5.5H6L8 1.5Z"
                    fill="var(--gold)" opacity="0.9" />
                </svg>
              </div>
              <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: "var(--gold)" }}>
                Free Access
              </span>
            </div>
            <h2 className="text-xl font-bold" style={{ color: "var(--fg)" }}>Unlock AI Aleks</h2>
            <p className="text-sm leading-relaxed" style={{ color: "var(--fg-muted)" }}>
              Drop your name and email — you&apos;ll also join Aleks&apos;s newsletter. No spam. Unsubscribe any time.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium tracking-wide uppercase" style={{ color: "var(--fg-muted)" }}>
                First Name
              </label>
              <input
                ref={nameRef}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Aleks"
                required
                autoComplete="given-name"
                className="input-gold w-full rounded-xl px-4 py-3 text-sm transition-all"
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border-hi)",
                  color: "var(--fg)",
                }}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium tracking-wide uppercase" style={{ color: "var(--fg-muted)" }}>
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="input-gold w-full rounded-xl px-4 py-3 text-sm transition-all"
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border-hi)",
                  color: "var(--fg)",
                }}
              />
            </div>

            {error && (
              <p className="text-sm text-red-400 text-center">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="shimmer-btn w-full rounded-xl py-3.5 text-sm font-semibold transition-all duration-300 mt-1 disabled:opacity-60"
              style={{
                background: "var(--gold)",
                color: "#000",
                boxShadow: "0 0 24px rgba(201,168,76,0.20)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 40px rgba(201,168,76,0.40)";
                (e.currentTarget as HTMLButtonElement).style.filter = "brightness(1.1)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 24px rgba(201,168,76,0.20)";
                (e.currentTarget as HTMLButtonElement).style.filter = "brightness(1)";
              }}
            >
              {loading ? "Unlocking..." : "Start chatting — it's free →"}
            </button>

            <p className="text-xs text-center" style={{ color: "var(--fg-subtle)" }}>
              10 free messages per day. Your email is safe — Aleks hates spam too.
            </p>
          </form>

          {/* Social proof */}
          <div className="divider" />
          <div className="flex items-center justify-center gap-5">
            {[
              { n: "10 msgs", label: "free daily" },
              { n: "87+", label: "videos indexed" },
              { n: "100%", label: "Aleks&apos;s voice" },
            ].map((s) => (
              <div key={s.label} className="flex flex-col items-center gap-0.5">
                <span className="text-sm font-bold" style={{ color: "var(--gold)" }} dangerouslySetInnerHTML={{ __html: s.n }} />
                <span className="text-xs" style={{ color: "var(--fg-muted)" }} dangerouslySetInnerHTML={{ __html: s.label }} />
              </div>
            ))}
          </div>
        </div>

        {/* ── What you can ask ── */}
        <div className="flex flex-col items-center gap-5 w-full max-w-2xl">
          <p className="text-xs font-semibold tracking-widest uppercase" style={{ color: "var(--fg-muted)" }}>
            People ask things like
          </p>
          <div className="flex flex-wrap gap-2.5 justify-center">
            {[
              "Is data science actually worth it?",
              "How do I get my first internship?",
              "Python or R for data analysis?",
              "What GPA do big tech companies care about?",
              "How long did it take you to get a job offer?",
              "Should I do a bootcamp or a master's?",
            ].map((q) => (
              <div
                key={q}
                className="rounded-full px-4 py-2 text-xs"
                style={{
                  background: "var(--surface-1)",
                  border: "1px solid var(--border-hi)",
                  color: "var(--fg-muted)",
                }}
              >
                {q}
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* ── Footer ── */}
      <div className="relative z-10 w-full py-6 flex justify-center">
        <div className="divider absolute top-0" />
        <p className="text-xs mt-6" style={{ color: "var(--fg-subtle)" }}>
          Built by{" "}
          <a
            href="https://aleksgornik.com"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-[var(--gold)]"
            style={{ color: "var(--fg-muted)" }}
          >
            Aleks Gornik
          </a>
          {" · "}
          <a
            href="https://youtube.com/@aleksgornik"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-[var(--gold)]"
            style={{ color: "var(--fg-muted)" }}
          >
            YouTube
          </a>
        </p>
      </div>

    </div>
  );
}
