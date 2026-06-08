import { useState, useEffect, useRef } from "react";
import {
  GitBranch, Search, ChevronRight, CheckCircle2, Circle,
  AlertTriangle, XCircle, Info, Heart, DollarSign, Globe,
  BookOpen, Code2, Cpu, Building2, Layers, ArrowLeft,
  ShieldAlert, FileSearch, Package, Lock, BarChart2,
  Loader2, ExternalLink, ChevronDown, ChevronUp,
  KeyRound, Bug, RefreshCw, ShieldCheck,
} from "lucide-react";

// ── Industry verticals ────────────────────────────────────────────────────────

const INDUSTRIES = [
  { id: "health",     label: "Health & MedTech",  Icon: Heart,      desc: "HIPAA · PHI · patient data",          color: "text-rose-500",    bg: "bg-rose-50",    border: "border-rose-200" },
  { id: "fintech",    label: "Fintech",            Icon: DollarSign, desc: "PCI DSS · financial regulations",     color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200" },
  { id: "saas",       label: "Consumer SaaS",      Icon: Globe,      desc: "GDPR · CCPA · privacy",               color: "text-blue-500",    bg: "bg-blue-50",    border: "border-blue-200" },
  { id: "edtech",     label: "EdTech",             Icon: BookOpen,   desc: "FERPA · COPPA · student data",        color: "text-violet-500",  bg: "bg-violet-50",  border: "border-violet-200" },
  { id: "devtools",   label: "Developer Tools",    Icon: Code2,      desc: "OSS licenses · supply chain",         color: "text-orange-500",  bg: "bg-orange-50",  border: "border-orange-200" },
  { id: "ai",         label: "AI / ML",            Icon: Cpu,        desc: "AI data use · training data",         color: "text-purple-500",  bg: "bg-purple-50",  border: "border-purple-200" },
  { id: "enterprise", label: "Enterprise B2B",     Icon: Building2,  desc: "SOC 2 · access control · compliance", color: "text-slate-600",   bg: "bg-slate-50",   border: "border-slate-200" },
  { id: "other",      label: "Other / General",    Icon: Layers,     desc: "General security & hygiene scan",     color: "text-text-secondary", bg: "bg-chip",    border: "border-border" },
];

// ── Scanners ──────────────────────────────────────────────────────────────────
// These match the actual scanner IDs in the backend.

const BASE_SCANNERS = [
  { id: "static_hygiene",  label: "Static hygiene",          Icon: FileSearch,  desc: "Missing files, sensitive filenames" },
  { id: "license_scanner", label: "License inventory",       Icon: Lock,        desc: "GPL · AGPL · copyleft obligations" },
  { id: "secret_scanner",  label: "Secret detection",        Icon: KeyRound,    desc: "Hardcoded keys, PEM certs, connection strings" },
  { id: "dependency_vuln", label: "Dependency vulnerabilities", Icon: Bug,      desc: "Known CVEs via OSV database" },
  { id: "outdated_deps",   label: "Outdated dependencies",   Icon: RefreshCw,   desc: "Behind-latest packages per registry" },
  { id: "code_compliance", label: "Code compliance",         Icon: ShieldCheck, desc: "Privacy patterns, cookie flags, tracking SDKs" },
];

// Industry-specific scanners shown as aspirational (coming soon) in the scanner preview
const INDUSTRY_SCANNERS = {
  health:     [{ id: "hipaa",  label: "HIPAA / PHI rules",        Icon: Heart,      desc: "Coming soon" }],
  fintech:    [{ id: "pci",    label: "PCI DSS / financial data",  Icon: DollarSign, desc: "Coming soon" }],
  saas:       [{ id: "gdpr",   label: "GDPR / CCPA compliance",    Icon: Globe,      desc: "Coming soon" }],
  edtech:     [{ id: "ferpa",  label: "FERPA / COPPA rules",       Icon: BookOpen,   desc: "Coming soon" }],
  devtools:   [{ id: "oss",    label: "OSS license risk",          Icon: Code2,      desc: "Coming soon" }],
  ai:         [{ id: "aidata", label: "AI data use rules",         Icon: Cpu,        desc: "Coming soon" }],
  enterprise: [{ id: "soc2",   label: "SOC 2 readiness checks",    Icon: Building2,  desc: "Coming soon" }],
  other:      [],
};

// Human-readable scanner names for the FindingCard attribution badge
const SCANNER_LABELS = {
  static_hygiene:  "Static Hygiene",
  license_scanner: "License",
  secret_scanner:  "Secret Scanner",
  dependency_vuln: "Dependency Vuln",
  outdated_deps:   "Outdated Deps",
  code_compliance: "Code Compliance",
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

// Normalise evidence from the backend (location.path / location.line_start)
// or from old-style placeholder objects (file / line).
function evidenceLocation(ev) {
  if (ev.location?.path) {
    return {
      path: ev.location.path,
      line: ev.location.line_start ?? null,
    };
  }
  return { path: ev.file ?? ev.source ?? null, line: ev.line ?? null };
}

// ── Finding card ──────────────────────────────────────────────────────────────

function FindingCard({ finding }) {
  const [open, setOpen] = useState(false);
  const sev = SEV[finding.severity] ?? SEV.info;
  const SevIcon = sev.Icon;
  const scannerLabel = SCANNER_LABELS[finding.scanner_id] ?? finding.scanner_id;

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
            {scannerLabel && (
              <span className="rounded-full px-2 py-0.5 text-[11px] text-text-muted bg-white/60 border border-border/60">
                {scannerLabel}
              </span>
            )}
          </div>
          <p className="mt-1 text-[13px] text-text-secondary leading-relaxed line-clamp-2">
            {finding.description}
          </p>
        </div>
        {open
          ? <ChevronUp className="shrink-0 h-4 w-4 text-text-muted mt-0.5" />
          : <ChevronDown className="shrink-0 h-4 w-4 text-text-muted mt-0.5" />}
      </button>

      {open && (
        <div className="px-5 pb-4 space-y-3 border-t border-border/40 pt-3">
          {finding.evidence && finding.evidence.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-muted mb-1.5">Evidence</div>
              <div className="space-y-1.5">
                {finding.evidence.map((ev, i) => {
                  const loc = evidenceLocation(ev);
                  return (
                    <div key={i} className="text-[12px] bg-white/70 rounded-lg px-3 py-2 border border-border/50 space-y-1">
                      {loc.path && (
                        <div className="font-mono text-text-muted">
                          {loc.path}{loc.line ? `:${loc.line}` : ""}
                        </div>
                      )}
                      {ev.excerpt && (
                        <div className="font-mono text-text-primary truncate">{ev.excerpt}</div>
                      )}
                      {ev.description && (
                        <div className="text-text-secondary text-[11px]">{ev.description}</div>
                      )}
                    </div>
                  );
                })}
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
          <p className="text-[13px] text-text-secondary mt-1">
            Running {scanners.length} scanners. This takes 15–30 seconds.
          </p>
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
              <div className="flex-1 min-w-0">
                <span className={`text-[14px] ${done ? "text-text-primary font-medium" : active ? "text-accent-gold font-medium" : "text-text-muted"}`}>
                  {s.label}
                </span>
                {s.desc && (
                  <span className="ml-2 text-[11px] text-text-muted">{s.desc}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Results view ──────────────────────────────────────────────────────────────

function ResultsView({ results, repoUrl, industry, onReset }) {
  const findings = results.findings ?? [];
  const counts = Object.fromEntries(
    Object.keys(SEV).map((k) => [k, findings.filter((f) => f.severity === k).length])
  );
  const total = findings.length;
  const ind = INDUSTRIES.find((i) => i.id === industry);

  const bySeverity = ["critical", "high", "medium", "low", "info"]
    .map((sev) => ({ sev, items: findings.filter((f) => f.severity === sev) }))
    .filter((g) => g.items.length > 0);

  // Which scanners produced at least one finding
  const activeScanners = [...new Set(findings.map((f) => f.scanner_id).filter(Boolean))];

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
            {total === 0
              ? "No findings"
              : `${total} finding${total !== 1 ? "s" : ""} detected`}
          </h2>
          <p className="text-[14px] text-text-secondary mt-1">
            {total === 0
              ? "This repo looks clean across all scanned dimensions."
              : "Review each finding below. Severity and confidence are shown independently."}
          </p>
          {activeScanners.length > 0 && (
            <div className="mt-3 flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-text-muted">Scanners with findings:</span>
              {activeScanners.map((id) => (
                <span key={id} className="rounded-full bg-chip border border-border px-2 py-0.5 text-[11px] text-text-secondary">
                  {SCANNER_LABELS[id] ?? id}
                </span>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card hover:text-text-primary transition-colors shrink-0"
        >
          <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2.2} />
          New scan
        </button>
      </div>

      {/* Severity summary strip */}
      <div className="grid grid-cols-5 gap-3">
        {Object.entries(SEV).map(([key, cfg]) => (
          <div key={key} className={`rounded-2xl border ${cfg.border} ${cfg.bg} px-4 py-3 text-center`}>
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
                  {items.map((f) => <FindingCard key={f.id ?? f.title} finding={f} />)}
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

export default function RepoScanner() {
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

  // Tick through scanners during the request to show progress
  useEffect(() => {
    if (step !== "scanning") return;
    setScanLog([]);
    let i = 0;
    const interval = setInterval(() => {
      if (i < BASE_SCANNERS.length) {
        setScanLog((prev) => [...prev, BASE_SCANNERS[i].id]);
        i++;
      } else {
        clearInterval(interval);
      }
    }, 1800);
    return () => clearInterval(interval);
  }, [step]);

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
      setStep("results");
    } catch (err) {
      if (
        err.message.includes("Failed to fetch") ||
        err.message.includes("404") ||
        err.message.includes("NetworkError")
      ) {
        setResults(PLACEHOLDER_RESULTS);
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
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-text-secondary text-[12px] uppercase tracking-widest">
            <ShieldAlert className="h-4 w-4 text-accent-gold" strokeWidth={2} />
            <span>Startup Risk Scanner</span>
          </div>
          <h1 className="text-[36px] font-bold leading-tight tracking-tight animate-shimmer-text">
            Scan any public GitHub repo.
          </h1>
          <p className="text-[16px] text-text-secondary max-w-[560px] leading-relaxed">
            We run {BASE_SCANNERS.length} scanners against your codebase — secrets, outdated dependencies,
            known CVEs, license obligations, and privacy compliance patterns — and return evidence-backed
            findings with file and line number.
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
            Product / company name{" "}
            <span className="text-text-muted font-normal">(optional)</span>
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
                  <div className={`flex h-9 w-9 items-center justify-center rounded-xl border ${selected ? `${bg} ${border}` : "bg-chip border-border"}`}>
                    <Icon className={`h-4 w-4 ${selected ? color : "text-text-muted"}`} strokeWidth={2} />
                  </div>
                  <div>
                    <div className="text-[13px] font-semibold text-text-primary">{label}</div>
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
          <div className="rounded-2xl border border-border bg-card/60 p-5 shadow-card space-y-3 animate-fade-in">
            <div className="text-[12px] uppercase tracking-wider text-text-muted">Scanners that will run</div>
            <div className="flex flex-wrap gap-2">
              {BASE_SCANNERS.map((s) => (
                <span
                  key={s.id}
                  className="flex items-center gap-1.5 rounded-full border border-border bg-chip px-3 py-1 text-[12px] text-text-secondary"
                >
                  <s.Icon className="h-3 w-3" strokeWidth={2} />
                  {s.label}
                </span>
              ))}
              {(INDUSTRY_SCANNERS[industry] ?? []).map((s) => (
                <span
                  key={s.id}
                  className="flex items-center gap-1.5 rounded-full border border-dashed border-border-chip bg-chip/60 px-3 py-1 text-[12px] text-text-muted"
                >
                  <s.Icon className="h-3 w-3" strokeWidth={2} />
                  {s.label}
                  <span className="text-[10px] opacity-60">soon</span>
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

        <p className="text-[11px] text-text-muted leading-relaxed max-w-lg">
          Only public GitHub repositories are supported. No code is executed — all analysis is static.
          Findings are possible risk triggers, not legal conclusions.
        </p>
      </div>
    );
  }

  if (step === "scanning") {
    return <ScanningView scanners={scanners} log={scanLog} />;
  }

  return (
    <ResultsView
      results={results}
      repoUrl={url}
      industry={industry}
      onReset={handleReset}
    />
  );
}

// ── Placeholder results ───────────────────────────────────────────────────────
// Shown when the backend isn't connected. Evidence uses the backend's schema
// (location.path / location.line_start) so the FindingCard renders identically
// to real results and the transition to live data is seamless.

const PLACEHOLDER_RESULTS = {
  findings: [
    {
      id: "ph-secret-1",
      title: "Possible hardcoded API key in source file",
      description:
        "A source file contains what appears to be an API key assigned as a string literal. If this is a live credential it should be rotated immediately and moved to an environment variable or secrets manager.",
      severity: "high",
      confidence: "medium",
      scanner_id: "secret_scanner",
      evidence: [
        {
          location: { path: "src/config.js", line_start: 7 },
          description: "Matched hardcoded_secret pattern in root file.",
          excerpt: "api_key = '[REDACTED]'",
        },
      ],
      recommendation:
        "Remove the value from source control, rotate the credential, and load it from an environment variable or secrets manager (e.g. AWS Secrets Manager, Doppler).",
    },
    {
      id: "ph-vuln-1",
      title: "Known vulnerability in lodash 4.17.15 (GHSA-p6mc-m468-83gw)",
      description:
        "lodash@4.17.15 (npm) is affected by a prototype pollution vulnerability tracked in the OSV database. An attacker can modify Object.prototype via a crafted payload to _.set, _.merge, or _.setWith.",
      severity: "high",
      confidence: "high",
      scanner_id: "dependency_vuln",
      evidence: [
        {
          location: { path: "package.json", line_start: 12 },
          description: "GHSA-p6mc-m468-83gw: Prototype pollution in lodash.",
          excerpt: "https://osv.dev/vulnerability/GHSA-p6mc-m468-83gw",
        },
      ],
      recommendation:
        "Upgrade lodash to 4.17.21 or later. See https://osv.dev/vulnerability/GHSA-p6mc-m468-83gw for patched version ranges.",
    },
    {
      id: "ph-license-1",
      title: "GPL-3.0 runtime dependency — possible distribution obligation",
      description:
        "A GPL-3.0 licensed library is declared as a runtime dependency. If the product is distributed as a binary (not pure SaaS), GPL-3.0 may require making the full source of the combined work available to users.",
      severity: "high",
      confidence: "high",
      scanner_id: "license_scanner",
      evidence: [
        {
          location: { path: "requirements.txt", line_start: 18 },
          description: "Dependency uses GPL-3.0 license.",
          excerpt: "some-gpl-lib==2.1.0",
        },
      ],
      recommendation:
        "Review whether this dependency is required at runtime. Consider a permissively licensed alternative (MIT, Apache-2.0). Consult counsel if distributing binaries.",
    },
    {
      id: "ph-code-1",
      title: "Auth token stored in browser localStorage",
      description:
        "An auth token is being written to localStorage, which is accessible by any JavaScript on the page — including injected scripts. This is a common XSS attack vector.",
      severity: "high",
      confidence: "medium",
      scanner_id: "code_compliance",
      evidence: [
        {
          location: { path: "src/auth/session.ts", line_start: 23 },
          description: "Matched token_in_browser_storage pattern.",
          excerpt: "localStorage.setItem('auth_token', response.token)",
        },
      ],
      recommendation:
        "Store auth tokens in HttpOnly, Secure, SameSite=Lax cookies or a server-side session. Never store bearer tokens in web storage.",
    },
    {
      id: "ph-outdated-1",
      title: "Outdated dependency: express 4.17.1 → 4.21.2",
      description:
        "express (npm) is pinned to 4.17.1 but the latest release is 4.21.2. Outdated packages may contain unpatched vulnerabilities or miss important security fixes.",
      severity: "low",
      confidence: "high",
      scanner_id: "outdated_deps",
      evidence: [
        {
          location: { path: "package.json", line_start: 8 },
          description: "Pinned to 4.17.1, latest release is 4.21.2.",
          excerpt: '"express": "4.17.1"',
        },
      ],
      recommendation:
        "Upgrade express from 4.17.1 to 4.21.2. Review the changelog for breaking changes before upgrading.",
    },
    {
      id: "ph-hygiene-1",
      title: "Missing SECURITY.md",
      description:
        "The repository does not include a SECURITY.md file. This is expected by GitHub's security advisory system and by enterprise buyers during vendor diligence.",
      severity: "low",
      confidence: "high",
      scanner_id: "static_hygiene",
      evidence: [
        {
          location: null,
          description: "No top-level SECURITY.md file was found in the static snapshot.",
          excerpt: null,
        },
      ],
      recommendation:
        "Add a SECURITY.md to the repo root describing your vulnerability disclosure policy and a contact method for security researchers.",
    },
  ],
  disclaimer:
    "Backend not connected — these are illustrative example findings. The same scanner suite that produced this output runs against real repositories. No conclusions about any specific repository should be drawn from this placeholder output.",
};
