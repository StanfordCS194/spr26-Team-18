import { useState, useRef, useEffect } from "react";
import { Paperclip, Loader2, Sparkles, ArrowUp, X, ChevronDown } from "lucide-react";
import BillCard from "./BillCard";

const GREETING = {
  role: "assistant",
  content:
    "Hi! Tell me about your company — what you make, where you operate, roughly how many employees, and anything water/energy/emissions-relevant. You can also drop a 10-K and I'll read it.",
};

const INITIAL_VISIBLE = 5;

export default function CompanyMatch() {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  const isFirstUserTurn = !messages.some((m) => m.role === "user");

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function postChat(history, sentFile) {
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.append(
      "messages",
      JSON.stringify(history.map(({ role, content }) => ({ role, content })))
    );
    if (sentFile) fd.append("file", sentFile);

    try {
      const r = await fetch("/api/match/chat", { method: "POST", body: fd });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(detail.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message, matches: data.matches },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function send(e) {
    e?.preventDefault();
    if (loading) return;
    if (!input.trim() && !file) return;

    const userMsg = { role: "user", content: input.trim(), file: file?.name || null };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    const sentFile = file;
    setFile(null);
    await postChat(next, sentFile);
  }

  async function chatAboutBill(bill) {
    if (loading) return;
    const content = `Tell me more about ${bill.bill_number}: ${bill.title}`;
    const userMsg = { role: "user", content };
    const next = [...messages, userMsg];
    setMessages(next);
    await postChat(next, null);
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(e);
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      <div className="mb-5">
        <h1 className="mb-1.5 text-[28px] font-bold tracking-tight text-text-primary">
          Match my company
        </h1>
        <p className="text-[15px] text-text-secondary">
          Chat with the assistant or drop a 10-K. We'll surface the California environmental
          bills most likely to affect you.
        </p>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded-3xl border border-border-muted bg-card/60 p-6 shadow-card backdrop-blur-sm"
      >
        <div className="flex flex-col gap-4">
          {messages.map((m, i) => (
            <Bubble key={i} message={m} onChatAbout={chatAboutBill} />
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-[13px] text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin text-accent-gold" />
              <span>Thinking…</span>
            </div>
          )}
          {error && (
            <div className="rounded-xl bg-status-committee-bg/60 px-3 py-2 text-[13px] text-status-committee-text">
              {error}
            </div>
          )}
        </div>
      </div>

      <form onSubmit={send} className="mt-4">
        {file && (
          <div className="mb-2 flex items-center gap-2 self-start rounded-full border border-border bg-card px-3 py-1.5 text-[12px] text-text-secondary">
            <Paperclip className="h-3.5 w-3.5 text-action-dark" />
            <span className="max-w-[260px] truncate">{file.name}</span>
            <button
              type="button"
              onClick={() => setFile(null)}
              className="text-text-muted hover:text-text-primary"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-card focus-within:border-action-dark focus-within:ring-2 focus-within:ring-action/40">
          {isFirstUserTurn && (
            <label
              className="flex h-9 w-9 flex-shrink-0 cursor-pointer items-center justify-center rounded-xl text-text-muted transition-colors hover:bg-chip hover:text-text-primary"
              title="Attach a 10-K (PDF or TXT) — first turn only"
            >
              <Paperclip className="h-4 w-4" />
              <input
                type="file"
                accept=".pdf,.txt"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
          )}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              isFirstUserTurn
                ? "Tell me about your company…"
                : "Refine, ask follow-ups, or paste more context…"
            }
            rows={1}
            disabled={loading}
            className="flex-1 resize-none bg-transparent px-2 py-2 text-[14px] leading-relaxed text-text-primary outline-none placeholder:text-text-muted disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={loading || (!input.trim() && !file)}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-action-dark text-white transition-all hover:opacity-90 active:scale-[0.95] disabled:opacity-40"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}

function Bubble({ message, onChatAbout }) {
  const [showAll, setShowAll] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-action px-4 py-2.5 text-[14px] leading-relaxed text-text-primary shadow-card">
          {message.file && (
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-primary/70">
              <Paperclip className="h-3 w-3" />
              {message.file}
            </div>
          )}
          {message.content && <div className="whitespace-pre-wrap">{message.content}</div>}
        </div>
      </div>
    );
  }

  const matches = message.matches;
  const visible =
    matches && (showAll ? matches : matches.slice(0, INITIAL_VISIBLE));
  const hiddenCount = matches ? matches.length - INITIAL_VISIBLE : 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-2.5">
        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-accent-gold/40">
          <Sparkles className="h-3.5 w-3.5 text-text-primary" />
        </div>
        <div className="max-w-[88%] rounded-2xl rounded-tl-md bg-chip-alt px-4 py-2.5 text-[14px] leading-relaxed text-text-primary">
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
      </div>
      {matches && matches.length > 0 && (
        <div className="ml-9 flex flex-col gap-2">
          <p className="text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
            {matches.length} ranked bills · showing {visible.length}
          </p>
          {visible.map((r) => (
            <BillCard
              key={r.bill_number}
              bill={r}
              relevance={{ score: r.score, tier: r.tier }}
              onChatAbout={onChatAbout}
            />
          ))}
          {hiddenCount > 0 && !showAll && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="mt-1 inline-flex items-center justify-center gap-1.5 self-start rounded-full border border-border-chip bg-card px-4 py-2 text-[12px] font-semibold text-text-secondary transition-colors hover:border-action-dark hover:text-action-dark"
            >
              <ChevronDown className="h-3.5 w-3.5" />
              Show {hiddenCount} more
            </button>
          )}
        </div>
      )}
      {matches && matches.length === 0 && (
        <div className="ml-9 rounded-xl border border-border-muted bg-card px-4 py-3 text-[13px] text-text-muted">
          No strong matches yet. Add more detail and try again.
        </div>
      )}
    </div>
  );
}
