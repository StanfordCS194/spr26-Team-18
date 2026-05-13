import { useRef, useState } from "react";
import { AlertTriangle, Loader2, ShieldCheck, Upload, X } from "lucide-react";

const RISK_TEXT = {
  Low: "text-green-600",
  Moderate: "text-orange-500",
  High: "text-red-600",
  Unknown: "text-text-muted",
};

const RISK_BADGE = {
  Low: "border-green-200 bg-green-50",
  Moderate: "border-orange-200 bg-orange-50",
  High: "border-red-200 bg-red-50",
  Unknown: "border-border bg-chip-alt",
};

export default function FinancialCompliance() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  async function submit(e) {
    e?.preventDefault();
    if (!file && !text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    if (file) fd.append("file", file);
    if (text.trim()) fd.append("document_text", text.trim());
    if (companyName.trim()) fd.append("company_name", companyName.trim());

    try {
      const r = await fetch("/api/compliance/audit", { method: "POST", body: fd });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(detail.detail || `HTTP ${r.status}`);
      }
      setResult(await r.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setFile(null);
    setText("");
    setCompanyName("");
    setResult(null);
    setError(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-text-secondary">
          <ShieldCheck className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">IRS Compliance · prototype</span>
        </div>
        <h1 className="text-[32px] font-bold tracking-tight">Financial compliance audit.</h1>
        <p className="max-w-[600px] text-[14px] leading-relaxed text-text-secondary">
          Upload a financial document or spreadsheet — PDF, TXT, CSV, or Excel — to get a
          preliminary IRS compliance risk assessment. Not a substitute for professional tax advice.
        </p>
      </header>

      {!result && (
        <form onSubmit={submit} className="rounded-2xl border border-border bg-card p-6 shadow-card">
          <h3 className="mb-4 text-[18px] font-bold tracking-tight">Upload financial document</h3>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr,1fr,160px]">
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Company name (optional)"
              className="rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
            />
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={file ? `Using file: ${file.name}` : "Or paste financial document text…"}
              rows={1}
              disabled={!!file}
              className="rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none disabled:bg-chip-alt disabled:text-text-muted"
            />
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-chip-alt px-4 py-2.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-action-dark hover:text-text-primary">
              <Upload className="h-4 w-4" strokeWidth={2.4} />
              <span>{file ? file.name.slice(0, 16) + "…" : "Upload file"}</span>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.csv,.xlsx,.xls"
                onChange={(e) => { setFile(e.target.files?.[0] || null); setText(""); }}
                className="hidden"
              />
            </label>
          </div>

          <div className="mt-3 flex items-center justify-between">
            <div className="text-[11px] text-text-muted">
              Accepts PDF, TXT, CSV, or Excel. Analysis typically takes 10–20s.
            </div>
            <button
              type="submit"
              disabled={loading || (!file && !text.trim())}
              className="flex items-center gap-2 rounded-full bg-action-dark px-5 py-2 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90 disabled:opacity-40"
            >
              {loading
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <ShieldCheck className="h-3.5 w-3.5" strokeWidth={2.4} />}
              {loading ? "Analyzing…" : "Run IRS compliance scan"}
            </button>
          </div>

          {error && (
            <div className="mt-3 rounded-xl border border-status-committee-bg bg-status-committee-bg/40 px-4 py-2 text-[12px] text-status-committee-text">
              {error}
            </div>
          )}
        </form>
      )}

      {result && <AuditResult result={result} onReset={reset} />}
    </section>
  );
}

function AuditResult({ result, onReset }) {
  const risk = result.overall_risk || "Unknown";
  const score = result.risk_score;
  const issues = result.issues || [];
  const notes = result.notes || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className={`flex items-center gap-2 rounded-full border px-4 py-1.5 text-[14px] font-semibold ${RISK_BADGE[risk] || RISK_BADGE.Unknown}`}>
          {risk === "High"
            ? <AlertTriangle className={`h-4 w-4 ${RISK_TEXT[risk]}`} strokeWidth={2.4} />
            : <ShieldCheck className={`h-4 w-4 ${RISK_TEXT[risk]}`} strokeWidth={2.4} />}
          <span className={RISK_TEXT[risk]}>{risk} risk</span>
          {score != null && (
            <span className="font-normal text-text-muted">· score {score}/100</span>
          )}
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card transition-colors hover:text-text-primary"
        >
          <X className="h-3.5 w-3.5" strokeWidth={2.4} />
          New scan
        </button>
      </div>

      <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">Summary</div>
        <p className="text-[14px] leading-relaxed text-text-primary">{result.summary}</p>
      </div>

      {issues.length > 0 ? (
        <div className="space-y-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            {issues.length} potential compliance issue{issues.length !== 1 ? "s" : ""}
          </div>
          {issues.map((issue, i) => (
            <div key={i} className="rounded-2xl border border-border bg-card p-5 shadow-card">
              <span className="mb-2 inline-block rounded-full bg-chip px-2.5 py-0.5 text-[11px] font-medium text-text-secondary">
                {issue.area}
              </span>
              <p className="mb-2 text-[13px] leading-relaxed text-text-primary">{issue.finding}</p>
              <p className="text-[12px] text-text-secondary">
                <span className="font-semibold text-text-primary">Next step: </span>
                {issue.recommendation}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-green-200 bg-green-50 p-5 text-[13px] text-green-700">
          No obvious IRS compliance issues were identified in the provided document.
        </div>
      )}

      {notes.length > 0 && (
        <div className="rounded-2xl border border-border-muted bg-chip-alt p-4">
          <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">Notes</div>
          <ul className="space-y-1">
            {notes.map((note, i) => (
              <li key={i} className="text-[12px] text-text-secondary">· {note}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[11px] text-text-muted">
        This audit is a prototype and not a substitute for professional tax or legal advice.
        Review results with an IRS compliance specialist.
      </p>
    </div>
  );
}
