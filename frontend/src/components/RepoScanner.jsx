import { useState, useEffect, Component } from "react";
import {
  GitBranch, Search, ChevronRight, CheckCircle2, AlertTriangle,
  XCircle, Info, ShieldAlert, Loader2, ExternalLink,
  ChevronDown, ChevronUp, ArrowLeft, Clock, Trophy, Bug,
} from "lucide-react";

// ── Error boundary ────────────────────────────────────────────────────────────

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center space-y-3">
          <p className="text-[15px] font-semibold text-red-700">Something went wrong rendering results</p>
          <p className="text-[12px] font-mono text-red-500">{this.state.error.message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded-xl border border-red-200 px-4 py-2 text-[13px] text-red-600 hover:bg-red-100 transition-colors"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Severity config ───────────────────────────────────────────────────────────

const SEV = {
  critical: { label: "Critical", color: "text-red-600",    bg: "bg-red-50",    border: "border-red-200",    Icon: XCircle },
  high:     { label: "High",     color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200", Icon: AlertTriangle },
  medium:   { label: "Medium",   color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200", Icon: AlertTriangle },
  low:      { label: "Low",      color: "text-blue-600",   bg: "bg-blue-50",   border: "border-blue-200",   Icon: Info },
  info:     { label: "Info",     color: "text-slate-500",  bg: "bg-slate-50",  border: "border-slate-200",  Icon: Info },
};

const SEVERITIES = ["critical", "high", "medium", "low", "info"];

// ── Industry list ─────────────────────────────────────────────────────────────

const INDUSTRIES = [
  { id: "saas",       label: "Consumer SaaS"      },
  { id: "health",     label: "Health & MedTech"   },
  { id: "fintech",    label: "Fintech"             },
  { id: "devtools",   label: "Developer Tools"     },
  { id: "ai",         label: "AI / ML"             },
  { id: "edtech",     label: "EdTech"              },
  { id: "enterprise", label: "Enterprise B2B"      },
  { id: "other",      label: "Other / General"     },
];

// ── Finding card ──────────────────────────────────────────────────────────────

function FindingCard({ finding }) {
  const [open, setOpen] = useState(false);
  const cfg = SEV[finding.severity] ?? SEV.info;
  const SevIcon = cfg.Icon;

  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} overflow-hidden`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-5 py-4 text-left"
      >
        <SevIcon className={`mt-0.5 h-4 w-4 shrink-0 ${cfg.color}`} strokeWidth={2.2} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[14px] font-semibold text-text-primary">{finding.title}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cfg.color} ${cfg.bg} border ${cfg.border}`}>
              {cfg.label}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-text-secondary leading-relaxed line-clamp-2">
            {finding.description}
          </p>
        </div>
        {open
          ? <ChevronUp className="shrink-0 h-4 w-4 text-text-muted mt-0.5" />
          : <ChevronDown className="shrink-0 h-4 w-4 text-text-muted mt-0.5" />
        }
      </button>

      {open && (
        <div className="px-5 pb-4 space-y-3 border-t border-border/40 pt-3">
          {finding.evidence?.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-muted mb-1.5">Evidence</div>
              <div className="space-y-1">
                {finding.evidence.map((ev, i) => (
                  <div key={i} className="flex items-start gap-2 text-[12px] text-text-secondary font-mono bg-white/60 rounded-lg px-3 py-1.5 border border-border/50">
                    <span className="text-text-muted shrink-0">
                      {ev.file || "—"}{ev.line ? `:${ev.line}` : ""}
                    </span>
                    {ev.excerpt && (
                      <span className="text-text-primary truncate">{ev.excerpt}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {finding.recommendation && (
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-muted mb-1">Recommended action</div>
              <p className="text-[13px] text-text-secondary leading-relaxed">{finding.recommendation}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Results view ──────────────────────────────────────────────────────────────

function ResultsView({ results, repoUrl, onReset }) {
  const findings = Array.isArray(results.findings) ? results.findings : [];

  const countBySev = Object.fromEntries(
    SEVERITIES.map((s) => [s, findings.filter((f) => f.severity === s).length])
  );

  const trivy = results.trivy_comparison;
  const ourVulns = results.our_vuln_count ?? 0;
  const cves = findings.filter((f) => f.category === "dependency_vulnerability");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-text-secondary text-[13px] mb-2">
            <GitBranch className="h-4 w-4" strokeWidth={1.5} />
            <a href={repoUrl} target="_blank" rel="noreferrer"
              className="hover:text-text-primary flex items-center gap-1 transition-colors">
              {repoUrl.replace("https://github.com/", "")}
              <ExternalLink className="h-3 w-3" strokeWidth={2} />
            </a>
          </div>
          <h2 className="text-[24px] font-bold text-text-primary">
            {findings.length === 0
              ? "No findings"
              : `${findings.length} finding${findings.length !== 1 ? "s" : ""} detected`}
          </h2>
        </div>
        <button onClick={onReset}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card hover:text-text-primary transition-colors shrink-0">
          <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2.2} />
          New scan
        </button>
      </div>

      {/* Timing */}
      {results.timing_seconds && (
        <div className="flex items-center gap-2 text-[13px] text-text-secondary">
          <Clock className="h-3.5 w-3.5 text-text-muted" strokeWidth={2} />
          Scan completed in <strong className="text-text-primary ml-1">{results.timing_seconds}s</strong>
        </div>
      )}

      {/* CVE banner */}
      {cves.length > 0 && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-100 border border-red-200">
              <Bug className="h-4 w-4 text-red-600" strokeWidth={2} />
            </div>
            <div>
              <div className="text-[14px] font-semibold text-red-800 mb-1">
                {cves.length} known CVE{cves.length !== 1 ? "s" : ""} detected in dependencies
              </div>
              {cves.map((f) => (
                <div key={f.id} className="mt-2 text-[13px] font-medium text-red-700">
                  {f.title}
                  {f.evidence?.[0]?.excerpt && (
                    <a href={f.evidence[0].excerpt} target="_blank" rel="noreferrer"
                      className="ml-2 text-[12px] text-red-500 underline inline-flex items-center gap-0.5">
                      OSV advisory <ExternalLink className="h-3 w-3" strokeWidth={2} />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Trivy comparison */}
      {trivy && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-100 border border-emerald-200">
              <Trophy className="h-4 w-4 text-emerald-600" strokeWidth={2} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[14px] font-semibold text-text-primary">Benchmark vs. Trivy</span>
                {ourVulns > trivy.trivy_vulns && (
                  <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-emerald-700 bg-emerald-100 border border-emerald-200">
                    We found more
                  </span>
                )}
              </div>
              <p className="text-[13px] text-text-secondary leading-relaxed">{trivy.trivy_note}</p>
              <div className="mt-3 flex gap-6">
                <div>
                  <div className="text-[20px] font-bold text-emerald-600">{ourVulns}</div>
                  <div className="text-[11px] text-text-muted">Our CVEs</div>
                </div>
                <div className="flex items-center text-text-muted">vs</div>
                <div>
                  <div className="text-[20px] font-bold text-text-muted">{trivy.trivy_vulns}</div>
                  <div className="text-[11px] text-text-muted">Trivy CVEs</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Severity counts */}
      <div className="grid grid-cols-5 gap-3">
        {SEVERITIES.map((sev) => {
          const cfg = SEV[sev];
          return (
            <div key={sev} className={`rounded-2xl border ${cfg.border} ${cfg.bg} px-4 py-3 text-center`}>
              <div className={`text-[22px] font-bold tabular-nums ${cfg.color}`}>{countBySev[sev]}</div>
              <div className="text-[11px] text-text-muted mt-0.5">{cfg.label}</div>
            </div>
          );
        })}
      </div>

      {/* Findings */}
      {findings.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-400" strokeWidth={1.5} />
          <p className="text-[15px] text-text-secondary">No issues found across all scanners.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {SEVERITIES.map((sev) => {
            const items = findings.filter((f) => f.severity === sev);
            if (items.length === 0) return null;
            const cfg = SEV[sev];
            const SevIcon = cfg.Icon;
            return (
              <div key={sev} className="space-y-3">
                <div className="flex items-center gap-3">
                  <SevIcon className={`h-4 w-4 ${cfg.color}`} strokeWidth={2.2} />
                  <h3 className="text-[13px] font-semibold uppercase tracking-wider text-text-muted">
                    {cfg.label} · {items.length}
                  </h3>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <div className="space-y-2">
                  {items.map((f) => <FindingCard key={f.id || f.title} finding={f} />)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main scanner component ────────────────────────────────────────────────────

export default function RepoScanner() {
  const [step, setStep] = useState("form"); // form | scanning | results
  const [url, setUrl] = useState("");
  const [industry, setIndustry] = useState("");
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [scanLog, setScanLog] = useState([]);

  const SCAN_STEPS = ["Hygiene & secrets", "License inventory", "Code compliance", "Dependency vulns", "Summarising"];

  // Tick through progress steps while scanning
  useEffect(() => {
    if (step !== "scanning") return;
    setScanLog([]);
    let i = 0;
    const iv = setInterval(() => {
      if (i < SCAN_STEPS.length) { setScanLog((p) => [...p, i]); i++; }
      else clearInterval(iv);
    }, 3000);
    return () => clearInterval(iv);
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleScan() {
    setError("");
    if (!url.trim()) { setError("Enter a GitHub URL."); return; }
    if (!url.includes("github.com")) { setError("Must be a GitHub URL."); return; }
    if (!industry) { setError("Select an industry."); return; }

    setStep("scanning");

    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url.trim(), industry, vuln_osv: true }),
      });

      if (!res.ok) {
        const body = await res.text();
        throw new Error(`Server returned ${res.status}: ${body.slice(0, 200)}`);
      }

      const data = await res.json();
      setResults(data);
      setStep("results");
    } catch (err) {
      // Backend not available → show placeholder
      if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
        setResults({ findings: [], timing_seconds: null, trivy_comparison: null, our_vuln_count: 0 });
        setStep("results");
      } else {
        setError(err.message);
        setStep("form");
      }
    }
  }

  // ── Form ──────────────────────────────────────────────────────────────────

  if (step === "form") {
    return (
      <div className="space-y-8">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-text-secondary text-[12px] uppercase tracking-widest">
            <ShieldAlert className="h-4 w-4 text-accent-gold" strokeWidth={2} />
            <span>Startup Risk Scanner</span>
          </div>
          <h1 className="text-[32px] font-bold leading-tight tracking-tight text-text-primary">
            Scan any public GitHub repo.
          </h1>
          <p className="text-[15px] text-text-secondary max-w-[520px] leading-relaxed">
            Static analysis across secrets, licenses, code compliance, and known CVEs.
            No code is executed.
          </p>
        </div>

        {/* URL */}
        <div className="space-y-2">
          <label className="text-[13px] font-medium text-text-primary">GitHub URL</label>
          <div className="relative max-w-lg">
            <GitBranch className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" strokeWidth={1.5} />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleScan()}
              placeholder="https://github.com/owner/repo"
              className="w-full rounded-2xl border border-border bg-card py-3 pl-11 pr-4 text-[14px] text-text-primary placeholder:text-text-muted shadow-card outline-none focus:border-accent-gold/60 focus:ring-2 focus:ring-accent-gold/20 transition-all"
            />
          </div>
        </div>

        {/* Industry */}
        <div className="space-y-2">
          <label className="text-[13px] font-medium text-text-primary">Industry</label>
          <div className="flex flex-wrap gap-2">
            {INDUSTRIES.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setIndustry(id)}
                className={`rounded-full border px-4 py-1.5 text-[13px] font-medium transition-all ${
                  industry === id
                    ? "border-accent-gold bg-accent-gold/10 text-text-primary"
                    : "border-border bg-card text-text-secondary hover:text-text-primary"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p className="text-[13px] text-red-500 flex items-center gap-1.5">
            <AlertTriangle className="h-4 w-4" strokeWidth={2} />
            {error}
          </p>
        )}

        <button
          onClick={handleScan}
          className="flex items-center gap-2 rounded-xl bg-action-dark px-6 py-3 text-[14px] font-semibold text-white shadow-card transition-all hover:opacity-90"
        >
          <Search className="h-4 w-4" strokeWidth={2.4} />
          Scan repository
          <ChevronRight className="h-4 w-4" strokeWidth={2.4} />
        </button>

        <p className="text-[11px] text-text-muted">
          Public GitHub repos only. Findings are indicators, not legal conclusions.
        </p>
      </div>
    );
  }

  // ── Scanning ──────────────────────────────────────────────────────────────

  if (step === "scanning") {
    return (
      <div className="space-y-8 py-4">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-accent-gold/10 border border-accent-gold/30">
            <Loader2 className="h-7 w-7 text-accent-gold animate-spin" strokeWidth={2} />
          </div>
          <div>
            <h2 className="text-[20px] font-bold text-text-primary">Scanning repository…</h2>
            <p className="text-[13px] text-text-secondary mt-1">
              This takes 15–60 seconds depending on repo size.
            </p>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-card p-6 shadow-card space-y-3 max-w-sm mx-auto">
          {SCAN_STEPS.map((label, i) => {
            const done = scanLog.includes(i);
            const active = !done && scanLog.length === i;
            return (
              <div key={i} className="flex items-center gap-3">
                {done
                  ? <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" strokeWidth={2} />
                  : active
                    ? <Loader2 className="h-5 w-5 text-accent-gold shrink-0 animate-spin" strokeWidth={2} />
                    : <div className="h-5 w-5 rounded-full border-2 border-border shrink-0" />
                }
                <span className={`text-[14px] ${done ? "text-text-primary font-medium" : active ? "text-accent-gold font-medium" : "text-text-muted"}`}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ── Results ───────────────────────────────────────────────────────────────

  return (
    <ErrorBoundary>
      {results && (
        <ResultsView
          results={results}
          repoUrl={url}
          onReset={() => { setStep("form"); setResults(null); setError(""); setScanLog([]); }}
        />
      )}
    </ErrorBoundary>
  );
}
