import { useState } from "react";
import { Upload, Loader2, Building2 } from "lucide-react";
import BillCard from "./BillCard";

export default function CompanyMatch() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAnalyze(e) {
    e.preventDefault();
    setError(null);
    if (!file && !text.trim()) {
      setError("Upload a file or paste a description first.");
      return;
    }
    setLoading(true);
    setResults(null);

    const fd = new FormData();
    if (file) fd.append("file", file);
    if (text.trim()) fd.append("company_text", text);

    try {
      const r = await fetch("/api/match", { method: "POST", body: fd });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(detail.detail || `HTTP ${r.status}`);
      }
      setResults(await r.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-7">
        <h1 className="mb-1.5 text-[26px] font-bold text-text-primary">
          Match my company
        </h1>
        <p className="text-[15px] text-text-secondary">
          Upload a 10-K or paste a company description. We'll surface the California
          environmental bills most likely to affect you.
        </p>
      </div>

      <form
        onSubmit={handleAnalyze}
        className="mb-6 flex flex-col gap-4 rounded-[14px] bg-card p-6 shadow-card"
      >
        <label className="flex cursor-pointer items-center gap-3 rounded-[10px] border-[1.5px] border-dashed border-border bg-chip-alt px-4 py-3 text-sm text-text-secondary transition-colors hover:border-text-primary">
          <Upload className="h-5 w-5 text-text-primary" strokeWidth={2} />
          <span className="flex-1">
            {file ? file.name : "Upload 10-K (PDF or TXT)"}
          </span>
          <input
            type="file"
            accept=".pdf,.txt"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                setFile(null);
              }}
              className="text-xs font-semibold text-text-muted hover:text-text-primary"
            >
              clear
            </button>
          )}
        </label>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="…or paste a company description, e.g. We manufacture lithium-ion battery cells in Fremont, CA, with 400 employees and water-cooled processes…"
          rows={5}
          className="w-full resize-y rounded-[10px] border-[1.5px] border-border bg-white px-4 py-3 text-[14px] leading-relaxed text-text-primary outline-none transition-colors focus:border-text-primary"
        />

        <div className="flex items-center justify-between">
          <p className="text-xs text-text-muted">
            Files stay in memory — nothing is uploaded outside this server.
          </p>
          <button
            type="submit"
            disabled={loading}
            className="rounded-[10px] bg-action-dark px-6 py-[11px] text-[15px] font-semibold text-white transition-opacity hover:opacity-85 disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-4 rounded-[10px] border border-border bg-card px-4 py-3 text-sm text-status-default-text">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-12 text-[15px] text-text-muted">
          <Loader2 className="mb-3 h-7 w-7 animate-spin text-text-primary" />
          <span>Ranking bills…</span>
        </div>
      )}

      {results && results.length === 0 && (
        <div className="rounded-[14px] bg-card px-6 py-12 text-center shadow-card">
          <Building2 className="mx-auto mb-3 h-8 w-8 text-text-muted" strokeWidth={1.5} />
          <h3 className="mb-2 text-lg font-semibold text-text-primary">
            No strong matches found.
          </h3>
          <p className="text-sm leading-relaxed text-text-muted">
            Try pasting a longer description or a full 10-K.
          </p>
        </div>
      )}

      {results && results.length > 0 && (
        <div>
          <h2 className="mb-3 text-[18px] font-bold text-text-primary">
            Top relevant bills
          </h2>
          <div className="flex flex-col gap-3">
            {results.map((r) => (
              <BillCard
                key={r.bill_number}
                bill={r}
                relevance={{ score: r.score, tier: r.tier }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
