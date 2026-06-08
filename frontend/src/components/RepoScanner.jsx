import { useState, useEffect, useRef } from "react";
import {
  GitBranch, Search, ChevronRight, CheckCircle2, Circle,
  AlertTriangle, XCircle, Info, Heart, DollarSign, Globe,
  BookOpen, Code2, Cpu, Building2, Layers, ArrowLeft,
  ShieldAlert, FileSearch, Package, Lock, BarChart2,
  Loader2, ExternalLink, ChevronDown, ChevronUp,
} from "lucide-react";

// ── Industry verticals ────────────────────────────────────────────────────────

const INDUSTRIES = [
  { id: "health",     label: "Health & MedTech",   Icon: Heart,      desc: "HIPAA · PHI · patient data",           color: "text-rose-500",   bg: "bg-rose-50",   border: "border-rose-200" },
  { id: "fintech",    label: "Fintech",             Icon: DollarSign, desc: "PCI DSS · financial regulations",      color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200" },
  { id: "saas",       label: "Consumer SaaS",       Icon: Globe,      desc: "GDPR · CCPA · privacy",                color: "text-blue-500",   bg: "bg-blue-50",   border: "border-blue-200" },
  { id: "edtech",     label: "EdTech",              Icon: BookOpen,   desc: "FERPA · COPPA · student data",         color: "text-violet-500", bg: "bg-violet-50", border: "border-violet-200" },
  { id: "devtools",   label: "Developer Tools",     Icon: Code2,      desc: "OSS licenses · supply chain",          color: "text-orange-500", bg: "bg-orange-50", border: "border-orange-200" },
  { id: "ai",         label: "AI / ML",             Icon: Cpu,        desc: "AI data use · training data",          color: "text-purple-500", bg: "bg-purple-50", border: "border-purple-200" },
  { id: "enterprise", label: "Enterprise B2B",      Icon: Building2,  desc: "SOC 2 · access control · compliance",  color: "text-slate-600",  bg: "bg-slate-50",  border: "border-slate-200" },
  { id: "other",      label: "Other / General",     Icon: Layers,     desc: "General security & hygiene scan",      color: "text-text-secondary", bg: "bg-chip", border: "border-border" },
];

// ── Scanners that run per scan ────────────────────────────────────────────────

const BASE_SCANNERS = [
  { id: "hygiene",      label: "Static hygiene",         Icon: FileSearch },
  { id: "deps",         label: "Dependency supply chain", Icon: Package },
  { id: "licenses",     label: "License inventory",      Icon: Lock },
  { id: "analytics",    label: "Analytics & privacy",    Icon: BarChart2 },
];

const INDUSTRY_SCANNERS = {
  health:     [{ id: "hipaa",   label: "HIPAA / PHI rules",        Icon: Heart }],
  fintech:    [{ id: "pci",     label: "PCI DSS / financial data", Icon: DollarSign }],
  saas:       [{ id: "gdpr",    label: "GDPR / CCPA compliance",   Icon: Globe }],
  edtech:     [{ id: "ferpa",   label: "FERPA / COPPA rules",      Icon: BookOpen }],
  devtools:   [{ id: "oss",     label: "OSS license risk",         Icon: Code2 }],
  ai:         [{ id: "aidata",  label: "AI data use rules",        Icon: Cpu }],
  enterprise: [{ id: "soc2",    label: "SOC 2 readiness checks",   Icon: Building2 }],
  other:      [],
};

// ── Severity config ───────────────────────────────────────────────────────────

const SEV = {
  critical: { label: "Critical", color: "text-red-600",    bg: "bg-red-50",    border: "border-red-200",    Icon: XCircle },
  high:     { label: "High",     color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200", Icon: AlertTriangle },
  medium:   { label: "Medium",   color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200", Icon: AlertTriangle },
  low:      { label: "Low",      color: "text-blue-600",   bg: "bg-blue-50",   border: "border-blue-200",   Icon: Info },
  info:     { label: "Info",     color: "text-slate-500",  bg: "bg-slate-50",  border: "border-slate-200",  Icon: Info },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function validateGithubUrl(url) {
  return /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(\/?)$/.test(url.trim());
}

function ownerRepo(url) {
  const m = url.trim().match(/github\.com\/([\w.-]+\/[\w.-]+)/);
  return m ? m[1] : url;
}

function evidenceLabel(ev) {
  const path = ev.location?.path ?? ev.file ?? ev.path ?? ev.source ?? "—";
  const line = ev.location?.line_start ?? ev.line_start ?? ev.line;
  return `${path}${line ? `:${line}` : ""}`;
}

function shouldUsePlaceholderResults(err) {
  const message = String(err?.message || "");
  return (
    message.includes("Failed to fetch") ||
    message.includes("404") ||
    message.includes("502") ||
    message.includes("ECONNREFUSED") ||
    message.toLowerCase().includes("proxy")
  );
}

// ── Finding card ──────────────────────────────────────────────────────────────

function FindingCard({ finding }) {
  const [open, setOpen] = useState(false);
  const sev = SEV[finding.severity] ?? SEV.info;
  const SevIcon = sev.Icon;

  return (
    <div className={`rounded-2xl border ${sev.border} ${sev.bg} overflow-hidden`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-5 py-4 text-left"
      >
        <SevIcon className={`mt-0.5 h-4 w-4 shrink-0 ${sev.color}`} strokeWidth={2.2} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[14px] font-semibold text-text-primary leading-snug">
              {finding.title}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${sev.color} ${sev.bg} border ${sev.border}`}>
              {sev.label}
            </span>
            {finding.confidence && (
              <span className="rounded-full px-2 py-0.5 text-[11px] text-text-muted bg-chip border border-border">
                {finding.confidence} confidence
              </span>
            )}
          </div>
          <p className="mt-1 text-[13px] text-text-secondary leading-relaxed line-clamp-2">
            {finding.description}
          </p>
        </div>
        {open ? (
          <ChevronUp className="shrink-0 h-4 w-4 text-text-muted mt-0.5" />
        ) : (
          <ChevronDown className="shrink-0 h-4 w-4 text-text-muted mt-0.5" />
        )}
      </button>

      {open && (
        <div className="px-5 pb-4 space-y-3 border-t border-border/40 pt-3">
          {finding.evidence && finding.evidence.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-muted mb-1.5">Evidence</div>
              <div className="space-y-1">
                {finding.evidence.map((ev, i) => (
                  <div key={i} className="flex items-start gap-2 text-[12px] text-text-secondary font-mono bg-white/60 rounded-lg px-3 py-1.5 border border-border/50">
                    <span className="text-text-muted shrink-0">{evidenceLabel(ev)}</span>
                    {ev.excerpt && <span className="text-text-primary truncate">{ev.excerpt}</span>}
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

// ── Scanning animation ────────────────────────────────────────────────────────

function ScanningView({ scanners, log }) {
  return (
    <div className="space-y-8 py-4">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-accent-gold/10 border border-accent-gold/30">
          <Loader2 className="h-7 w-7 text-accent-gold animate-spin" strokeWidth={2} />
        </div>
        <div>
          <h2 className="text-[20px] font-bold text-text-primary">Scanning repository…</h2>
          <p className="text-[13px] text-text-secondary mt-1">Running {scanners.length} scanners. This takes about 15–30 seconds.</p>
        </div>
      </div>

      <div className="rounded-3xl border border-border bg-card p-6 shadow-card space-y-3 max-w-lg mx-auto">
        {scanners.map((s) => {
          const done = log.includes(s.id);
          const active = !done && log.length === scanners.findIndex((x) => x.id === s.id);
          return (
            <div key={s.id} className="flex items-center gap-3">
              {done ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" strokeWidth={2} />
              ) : active ? (
                <Loader2 className="h-5 w-5 text-accent-gold shrink-0 animate-spin" strokeWidth={2} />
              ) : (
                <Circle className="h-5 w-5 text-text-muted shrink-0" strokeWidth={1.5} />
              )}
              <span className={`text-[14px] ${done ? "text-text-primary font-medium" : active ? "text-accent-gold font-medium" : "text-text-muted"}`}>
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Results view ──────────────────────────────────────────────────────────────

function ResultsView({ results, repoUrl, industry, onReset, onViewIssues }) {
  const findings = results.findings ?? [];
  const counts = Object.fromEntries(
    Object.keys(SEV).map((k) => [k, findings.filter((f) => f.severity === k).length])
  );
  const total = findings.length;
  const ind = INDUSTRIES.find((i) => i.id === industry);

  const bySeverity = ["critical", "high", "medium", "low", "info"]
    .map((sev) => ({ sev, items: findings.filter((f) => f.severity === sev) }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-text-secondary text-[13px] mb-2">
            <GitBranch className="h-4 w-4" strokeWidth={1.5} />
            <a
              href={repoUrl}
              target="_blank"
              rel="noreferrer"
              className="hover:text-text-primary flex items-center gap-1 transition-colors"
            >
              {ownerRepo(repoUrl)}
              <ExternalLink className="h-3 w-3" strokeWidth={2} />
            </a>
            {ind && (
              <>
                <span className="text-text-muted">·</span>
                <ind.Icon className={`h-3.5 w-3.5 ${ind.color}`} strokeWidth={2} />
                <span>{ind.label}</span>
              </>
            )}
          </div>
          <h2 className="text-[24px] font-bold text-text-primary">
            {total === 0 ? "No findings" : `${total} finding${total !== 1 ? "s" : ""} detected`}
          </h2>
          <p className="text-[14px] text-text-secondary mt-1">
            {total === 0
              ? "This repo looks clean across all scanned dimensions."
              : "Review each finding below. Severity and confidence are listed independently."}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={onReset}
            className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2.2} />
            New scan
          </button>
          {total > 0 && onViewIssues && (
            <button
              onClick={onViewIssues}
              className="flex items-center gap-2 rounded-xl bg-action-dark px-4 py-2 text-[13px] font-semibold text-white shadow-card transition-opacity hover:opacity-90"
            >
              <Code2 className="h-3.5 w-3.5" strokeWidth={2.2} />
              Review by file
            </button>
          )}
        </div>
      </div>

      {/* Severity summary strip */}
      <div className="grid grid-cols-5 gap-3">
        {Object.entries(SEV).map(([key, cfg]) => (
          <div
            key={key}
            className={`rounded-2xl border ${cfg.border} ${cfg.bg} px-4 py-3 text-center`}
          >
            <div className={`text-[22px] font-bold tabular-nums ${cfg.color}`}>{counts[key] ?? 0}</div>
            <div className="text-[11px] text-text-muted mt-0.5">{cfg.label}</div>
          </div>
        ))}
      </div>

      {/* Findings grouped by severity */}
      {total === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-400" strokeWidth={1.5} />
          <p className="text-[15px] text-text-secondary">No issues found across all scanners.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {bySeverity.map(({ sev, items }) => {
            const cfg = SEV[sev];
            return (
              <div key={sev} className="space-y-3">
                <div className="flex items-center gap-3">
                  <cfg.Icon className={`h-4 w-4 ${cfg.color}`} strokeWidth={2.2} />
                  <h3 className="text-[13px] font-semibold uppercase tracking-wider text-text-muted">
                    {cfg.label} · {items.length}
                  </h3>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <div className="space-y-2">
                  {items.map((f) => (
                    <FindingCard key={f.id ?? f.title} finding={f} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {results.disclaimer && (
        <p className="text-[11px] text-text-muted leading-relaxed border-t border-border pt-4">
          {results.disclaimer}
        </p>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function RepoScanner({ onScanComplete, onViewIssues }) {
  const [step, setStep] = useState("form"); // "form" | "scanning" | "results"
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState("");
  const [industry, setIndustry] = useState(null);
  const [productName, setProductName] = useState("");
  const [results, setResults] = useState(null);
  const [apiError, setApiError] = useState("");
  const [scanLog, setScanLog] = useState([]);
  const scanners = [
    ...BASE_SCANNERS,
    ...(industry ? (INDUSTRY_SCANNERS[industry] ?? []) : []),
  ];
  const logRef = useRef(null);

  // Simulate scanner progress ticks while request is in-flight
  useEffect(() => {
    if (step !== "scanning") return;
    setScanLog([]);
    let i = 0;
    const interval = setInterval(() => {
      if (i < scanners.length) {
        setScanLog((prev) => [...prev, scanners[i].id]);
        i++;
      } else {
        clearInterval(interval);
      }
    }, 1800);
    return () => clearInterval(interval);
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleScan() {
    setUrlError("");
    setApiError("");

    if (!validateGithubUrl(url)) {
      setUrlError("Please enter a valid public GitHub URL (https://github.com/owner/repo).");
      return;
    }
    if (!industry) {
      setUrlError("Please select an industry to load the right scanners.");
      return;
    }

    setStep("scanning");

    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: url.trim(),
          industry,
          product_name: productName || undefined,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Server error ${res.status}`);
      }

      const data = await res.json();
      setResults(data);
      onScanComplete?.({
        results: data,
        repoUrl: url.trim(),
        industry,
        productName: productName || "",
      });
      setStep("results");
    } catch (err) {
      // If the backend isn't ready yet, show a friendly placeholder result
      if (shouldUsePlaceholderResults(err)) {
        setResults(PLACEHOLDER_RESULTS);
        onScanComplete?.({
          results: PLACEHOLDER_RESULTS,
          repoUrl: url.trim(),
          industry,
          productName: productName || "",
        });
        setStep("results");
      } else {
        setApiError(err.message);
        setStep("form");
      }
    }
  }

  function handleReset() {
    setStep("form");
    setResults(null);
    setScanLog([]);
    setApiError("");
  }

  // ── Form ──────────────────────────────────────────────────────────────────

  if (step === "form") {
    return (
      <div className="space-y-10">
        {/* Header */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-text-secondary text-[12px] uppercase tracking-widest">
            <ShieldAlert className="h-4 w-4 text-accent-gold" strokeWidth={2} />
            <span>Startup Risk Scanner</span>
          </div>
          <h1 className="text-[36px] font-bold leading-tight tracking-tight animate-shimmer-text">
            Scan any public GitHub repo.
          </h1>
          <p className="text-[16px] text-text-secondary max-w-[560px] leading-relaxed">
            We compare what your code actually does against known risk patterns — license exposure,
            privacy gaps, supply chain issues, and industry-specific compliance triggers.
          </p>
        </div>

        {/* URL input */}
        <div className="space-y-2">
          <label className="text-[13px] font-medium text-text-primary">GitHub repository URL</label>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <GitBranch
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted"
                strokeWidth={1.5}
              />
              <input
                type="url"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setUrlError(""); }}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
                placeholder="https://github.com/owner/repository"
                className="w-full rounded-2xl border border-border bg-card py-3 pl-10 pr-4 text-[14px] text-text-primary placeholder:text-text-muted shadow-card outline-none focus:border-accent-gold/60 focus:ring-2 focus:ring-accent-gold/20 transition-all"
              />
            </div>
          </div>
          {urlError && (
            <p className="text-[12px] text-red-500 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2} />
              {urlError}
            </p>
          )}
          {apiError && (
            <p className="text-[12px] text-red-500 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2} />
              {apiError}
            </p>
          )}
        </div>

        {/* Optional product name */}
        <div className="space-y-2">
          <label className="text-[13px] font-medium text-text-primary">
            Product / company name <span className="text-text-muted font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="e.g. Acme Health"
            className="w-full max-w-sm rounded-2xl border border-border bg-card py-2.5 px-4 text-[14px] text-text-primary placeholder:text-text-muted shadow-card outline-none focus:border-accent-gold/60 focus:ring-2 focus:ring-accent-gold/20 transition-all"
          />
        </div>

        {/* Industry selector */}
        <div className="space-y-3">
          <label className="text-[13px] font-medium text-text-primary">
            What kind of product is this?
            <span className="ml-2 text-text-muted font-normal text-[12px]">
              — we'll load the right scanners
            </span>
          </label>
          <div className="grid grid-cols-4 gap-3">
            {INDUSTRIES.map(({ id, label, Icon, desc, color, bg, border }) => {
              const selected = industry === id;
              return (
                <button
                  key={id}
                  onClick={() => setIndustry(id)}
                  className={`group flex flex-col items-start gap-2 rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 ${
                    selected
                      ? `${bg} ${border} shadow-card`
                      : "bg-card border-border shadow-card hover:shadow-card-hover"
                  }`}
                >
                  <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${selected ? bg : "bg-chip"} border ${selected ? border : "border-border"}`}>
                    <Icon className={`h-4 w-4 ${selected ? color : "text-text-muted group-hover:" + color}`} strokeWidth={2} />
                  </div>
                  <div>
                    <div className={`text-[13px] font-semibold ${selected ? "text-text-primary" : "text-text-primary"}`}>{label}</div>
                    <div className="text-[11px] text-text-muted leading-snug mt-0.5">{desc}</div>
                  </div>
                  {selected && (
                    <CheckCircle2 className={`h-4 w-4 ${color} self-end mt-1`} strokeWidth={2} />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Scanners preview */}
        {industry && (
          <div className="rounded-2xl border border-border bg-card/60 p-5 shadow-card space-y-2 animate-fade-in">
            <div className="text-[12px] uppercase tracking-wider text-text-muted mb-3">Scanners that will run</div>
            <div className="flex flex-wrap gap-2">
              {scanners.map((s) => (
                <span
                  key={s.id}
                  className="flex items-center gap-1.5 rounded-full border border-border bg-chip px-3 py-1 text-[12px] text-text-secondary"
                >
                  <s.Icon className="h-3 w-3" strokeWidth={2} />
                  {s.label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Scan button */}
        <button
          onClick={handleScan}
          disabled={!url || !industry}
          className="flex items-center gap-2 rounded-xl bg-action-dark px-7 py-3 text-[15px] font-semibold text-white shadow-card transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Search className="h-4 w-4" strokeWidth={2.4} />
          Scan repository
          <ChevronRight className="h-4 w-4" strokeWidth={2.4} />
        </button>

        {/* Disclaimer */}
        <p className="text-[11px] text-text-muted leading-relaxed max-w-lg">
          Only public GitHub repositories are supported. No code is executed — all analysis is static.
          Findings are possible triggers, not legal conclusions.
        </p>
      </div>
    );
  }

  // ── Scanning ──────────────────────────────────────────────────────────────

  if (step === "scanning") {
    return <ScanningView scanners={scanners} log={scanLog} />;
  }

  // ── Results ───────────────────────────────────────────────────────────────

  return (
    <ResultsView
      results={results}
      repoUrl={url}
      industry={industry}
      onReset={handleReset}
      onViewIssues={onViewIssues}
    />
  );
}

// ── Placeholder results (shown when backend isn't connected yet) ──────────────

const PLACEHOLDER_RESULTS = {
  placeholder: true,
  findings: [
    {
      id: "ph-1",
      title: "GPL-3.0 dependency detected",
      description: "One or more runtime dependencies use the GPL-3.0 license. If your product is distributed (not just SaaS), this may require review of your distribution obligations.",
      severity: "high",
      confidence: "high",
      evidence: [
        { file: "package.json", line: 14, excerpt: '"some-gpl-lib": "^2.1.0"' },
      ],
      recommendation: "Review whether this dependency is required at runtime. Consider alternatives with permissive licenses (MIT, Apache-2.0). Consult counsel if distributing binaries.",
    },
    {
      id: "ph-2",
      title: "Analytics SDK imported without visible consent gate",
      description: "An analytics library (e.g. Segment, PostHog) is imported and called before user consent is collected. This may create a GDPR/CCPA trigger.",
      severity: "medium",
      confidence: "medium",
      evidence: [
        { file: "src/analytics.ts", line: 3, excerpt: "import Analytics from '@segment/analytics-next'" },
        { file: "src/main.tsx", line: 11, excerpt: "analytics.track('page_view', { userId })" },
      ],
      recommendation: "Wrap analytics initialization and track calls behind a consent check. Ensure opt-out is accessible and persisted.",
    },
    {
      id: "ph-3",
      title: "No SECURITY.md found",
      description: "The repository does not contain a SECURITY.md file. This is expected by GitHub's security advisory system and by enterprise buyers during diligence.",
      severity: "low",
      confidence: "high",
      evidence: [],
      recommendation: "Add a SECURITY.md to the repo root describing your vulnerability disclosure policy and contact method.",
    },
    {
      id: "ph-4",
      title: "Lockfile missing for declared dependencies",
      description: "A package.json was found but no package-lock.json, yarn.lock, or pnpm-lock.yaml is committed. Without a lockfile, dependency versions are not pinned and supply chain integrity cannot be verified.",
      severity: "medium",
      confidence: "high",
      evidence: [
        { file: "package.json", excerpt: "Found, but no lockfile committed alongside it" },
      ],
      recommendation: "Commit your lockfile (package-lock.json or yarn.lock) and add CI checks to keep it up to date.",
    },
  ],
  disclaimer:
    "This is a placeholder result — the scanner backend is not yet connected. Findings shown are illustrative examples of what the scanner will produce. No conclusions about this specific repository should be drawn from this output.",
};
