import { useState } from "react";
import {
  ShieldAlert, ExternalLink, ChevronDown, ChevronUp,
  AlertTriangle, XCircle, Info, Heart, DollarSign,
  Globe, Code2, Cpu, BookOpen, Building2, Layers,
  CheckCircle2, ArrowRight, FlaskConical,
} from "lucide-react";

// ── Industry config ───────────────────────────────────────────────────────────

const INDUSTRIES = {
  all:        { label: "All industries",   Icon: Layers,    color: "text-text-secondary", bg: "bg-chip",        border: "border-border" },
  health:     { label: "Health & MedTech", Icon: Heart,     color: "text-rose-500",        bg: "bg-rose-50",     border: "border-rose-200" },
  fintech:    { label: "Fintech",          Icon: DollarSign, color: "text-emerald-600",    bg: "bg-emerald-50",  border: "border-emerald-200" },
  saas:       { label: "Consumer SaaS",   Icon: Globe,      color: "text-blue-500",        bg: "bg-blue-50",     border: "border-blue-200" },
  devtools:   { label: "Developer Tools", Icon: Code2,      color: "text-orange-500",      bg: "bg-orange-50",   border: "border-orange-200" },
  ai:         { label: "AI / ML",         Icon: Cpu,        color: "text-purple-500",      bg: "bg-purple-50",   border: "border-purple-200" },
  edtech:     { label: "EdTech",          Icon: BookOpen,   color: "text-violet-500",      bg: "bg-violet-50",   border: "border-violet-200" },
  enterprise: { label: "Enterprise B2B",  Icon: Building2,  color: "text-slate-600",       bg: "bg-slate-50",    border: "border-slate-200" },
};

// ── Severity config ───────────────────────────────────────────────────────────

const SEV = {
  critical: { label: "Critical", color: "text-red-600",    bg: "bg-red-50",    border: "border-red-200",    dot: "bg-red-500" },
  high:     { label: "High",     color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200", dot: "bg-orange-500" },
  medium:   { label: "Medium",   color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200", dot: "bg-yellow-500" },
  low:      { label: "Low",      color: "text-blue-600",   bg: "bg-blue-50",   border: "border-blue-200",   dot: "bg-blue-400" },
  info:     { label: "Info",     color: "text-slate-500",  bg: "bg-slate-50",  border: "border-slate-200",  dot: "bg-slate-400" },
};

// ── Benchmark data ────────────────────────────────────────────────────────────
// Illustrative examples modelled on real vulnerability classes in the
// GitHub Advisory Database. Advisory IDs are placeholder references only.

const BENCHMARK_REPOS = [
  {
    id: "r01",
    repo: "medflow/patient-portal",
    industry: "health",
    description: "Patient-facing web portal for clinic scheduling and record access.",
    findings: { critical: 0, high: 2, medium: 3, low: 1, info: 2 },
    keyFinding: {
      title: "GPL-3.0 runtime dependency — possible distribution obligation",
      severity: "high",
      scanner: "License inventory",
      description: "A GPL-3.0 licensed library is used as a runtime dependency. For a hosted SaaS serving patients, this may create disclosure obligations if the product is distributed to customers as a binary.",
      file: "requirements.txt",
      line: 18,
    },
    advisory: {
      id: "GHSA-pl04-example-0001",
      title: "Privilege escalation via unsanitized patient ID parameter",
      date: "2024-08-14",
      severity: "high",
      correlation: "Scanner flagged missing input-validation patterns and no SECURITY.md 47 days before advisory was filed.",
    },
    flaggedDaysBefore: 47,
  },
  {
    id: "r02",
    repo: "carepath/api-server",
    industry: "health",
    description: "REST API backend for a care-coordination platform serving clinical teams.",
    findings: { critical: 1, high: 1, medium: 2, low: 3, info: 1 },
    keyFinding: {
      title: "PHI-adjacent field names passed to analytics SDK",
      severity: "critical",
      scanner: "Analytics & privacy",
      description: "Fields named 'patientId', 'diagnosisCode', and 'appointmentNote' appear in analytics.track() calls. If these contain real patient data, this may create HIPAA exposure.",
      file: "src/events/tracker.js",
      line: 34,
    },
    advisory: {
      id: "GHSA-pl04-example-0002",
      title: "Patient identifiers exposed in third-party analytics payloads",
      date: "2024-06-03",
      severity: "critical",
      correlation: "Scanner flagged analytics calls with PHI-adjacent field names 91 days before advisory was filed.",
    },
    flaggedDaysBefore: 91,
  },
  {
    id: "r03",
    repo: "paynow/checkout-sdk",
    industry: "fintech",
    description: "Open-source JavaScript SDK for embedding payment flows in web apps.",
    findings: { critical: 0, high: 3, medium: 2, low: 2, info: 0 },
    keyFinding: {
      title: "LGPL-2.1 dependency in distributed SDK — attribution and linking obligations",
      severity: "high",
      scanner: "License inventory",
      description: "An LGPL-2.1 library is bundled into the distributed SDK artifact. SDK consumers who link this statically may inherit LGPL obligations. No NOTICE file or attribution is present.",
      file: "package.json",
      line: 12,
    },
    advisory: {
      id: "GHSA-pl04-example-0003",
      title: "Credential exposure via misconfigured SDK initialization",
      date: "2024-09-22",
      severity: "high",
      correlation: "Scanner flagged missing lockfile and unpinned dependency versions 62 days before advisory.",
    },
    flaggedDaysBefore: 62,
  },
  {
    id: "r04",
    repo: "ledger-app/backend",
    industry: "fintech",
    description: "Accounting and invoicing backend used by SMB finance teams.",
    findings: { critical: 0, high: 1, medium: 4, low: 2, info: 3 },
    keyFinding: {
      title: "No lockfile committed — dependency versions unpinned",
      severity: "high",
      scanner: "Dependency supply chain",
      description: "package.json declares dependencies but no package-lock.json or yarn.lock is committed. Any CI run could resolve different package versions, making the build non-deterministic and supply-chain integrity unverifiable.",
      file: "package.json",
      line: null,
    },
    advisory: {
      id: "GHSA-pl04-example-0004",
      title: "Supply chain compromise via unpinned transitive dependency",
      date: "2024-11-05",
      severity: "high",
      correlation: "Scanner flagged missing lockfile and a git-URL dependency 120 days before advisory.",
    },
    flaggedDaysBefore: 120,
  },
  {
    id: "r05",
    repo: "chat-app/web",
    industry: "saas",
    description: "Consumer messaging app with real-time group chat and file sharing.",
    findings: { critical: 0, high: 2, medium: 3, low: 1, info: 2 },
    keyFinding: {
      title: "Sentry error monitoring initialized with user message content in scope",
      severity: "high",
      scanner: "Analytics & privacy",
      description: "Sentry.setUser() is called with full user profile data including email and display name. Sentry.captureException() is invoked in a context where message_content is in scope, potentially sending user messages to a third-party error service.",
      file: "src/lib/sentry.ts",
      line: 22,
    },
    advisory: {
      id: "GHSA-pl04-example-0005",
      title: "User message content inadvertently sent to error monitoring service",
      date: "2024-07-18",
      severity: "high",
      correlation: "Scanner flagged Sentry initialization with PII-adjacent scope 38 days before advisory.",
    },
    flaggedDaysBefore: 38,
  },
  {
    id: "r06",
    repo: "taskapp/api",
    industry: "saas",
    description: "B2C productivity app — task management with team collaboration features.",
    findings: { critical: 0, high: 0, medium: 3, low: 4, info: 2 },
    keyFinding: {
      title: "Analytics SDK called before user consent is collected",
      severity: "medium",
      scanner: "Analytics & privacy",
      description: "PostHog is initialized and posthog.capture('pageview') is called on app load, before any consent banner or opt-out mechanism is triggered. This may create a GDPR/CCPA trigger for EU and California users.",
      file: "src/analytics/posthog.ts",
      line: 9,
    },
    advisory: {
      id: "GHSA-pl04-example-0006",
      title: "User tracking initiated before consent — GDPR enforcement action",
      date: "2024-10-01",
      severity: "medium",
      correlation: "Scanner flagged pre-consent analytics call 74 days before the enforcement action was publicly disclosed.",
    },
    flaggedDaysBefore: 74,
  },
  {
    id: "r07",
    repo: "cli-tool/core",
    industry: "devtools",
    description: "Popular open-source CLI distributed as an npm package and standalone binary.",
    findings: { critical: 0, high: 2, medium: 1, low: 2, info: 1 },
    keyFinding: {
      title: "AGPL-3.0 dependency — strong copyleft in a distributed binary",
      severity: "high",
      scanner: "License inventory",
      description: "A runtime dependency uses the AGPL-3.0 license. Because this tool is distributed as a binary (not just SaaS), AGPL requires that the full source of the combined work be made available to users. No source disclosure mechanism exists.",
      file: "package.json",
      line: 27,
    },
    advisory: {
      id: "GHSA-pl04-example-0007",
      title: "License compliance failure — AGPL obligations not met in binary distribution",
      date: "2024-05-20",
      severity: "high",
      correlation: "Scanner flagged AGPL dependency in distributed binary 55 days before the compliance issue was disclosed.",
    },
    flaggedDaysBefore: 55,
  },
  {
    id: "r08",
    repo: "devops-sdk/python",
    industry: "devtools",
    description: "Python SDK for cloud infrastructure automation, distributed via PyPI.",
    findings: { critical: 0, high: 1, medium: 2, low: 3, info: 2 },
    keyFinding: {
      title: "Git URL dependency in requirements.txt — unpinned and unverifiable",
      severity: "high",
      scanner: "Dependency supply chain",
      description: "A dependency is installed directly from a GitHub repository URL with no commit SHA pinned. This means any push to that repo's default branch could change the installed code in production without a version bump.",
      file: "requirements.txt",
      line: 8,
    },
    advisory: {
      id: "GHSA-pl04-example-0008",
      title: "Supply chain attack via compromised unpinned git dependency",
      date: "2024-12-10",
      severity: "critical",
      correlation: "Scanner flagged the unpinned git URL dependency 88 days before the supply chain compromise was disclosed.",
    },
    flaggedDaysBefore: 88,
  },
  {
    id: "r09",
    repo: "llm-app/server",
    industry: "ai",
    description: "AI writing assistant that sends user documents to an LLM API for summarization.",
    findings: { critical: 1, high: 2, medium: 2, low: 1, info: 1 },
    keyFinding: {
      title: "User-uploaded file content sent to OpenAI with no retention or deletion policy",
      severity: "critical",
      scanner: "Analytics & privacy",
      description: "File content from user uploads is passed directly to the OpenAI API. No retention period, deletion mechanism, or user-facing disclosure about third-party AI processing is present in the codebase or documentation.",
      file: "src/routes/summarize.py",
      line: 41,
    },
    advisory: {
      id: "GHSA-pl04-example-0009",
      title: "User documents retained by third-party AI provider without disclosure",
      date: "2024-09-05",
      severity: "critical",
      correlation: "Scanner flagged AI provider usage without retention/deletion policy 66 days before the data-handling incident was reported.",
    },
    flaggedDaysBefore: 66,
  },
  {
    id: "r10",
    repo: "mlops/pipeline",
    industry: "ai",
    description: "Open-source MLOps platform for training and serving ML models at scale.",
    findings: { critical: 0, high: 2, medium: 3, low: 2, info: 1 },
    keyFinding: {
      title: "Credentials pattern detected in committed config file",
      severity: "high",
      scanner: "Static hygiene",
      description: "A file named 'config.prod.yaml' is committed to the repository. It contains key patterns consistent with API keys and database connection strings. Sensitive credential files should not be committed even if values are placeholders.",
      file: "config.prod.yaml",
      line: null,
    },
    advisory: {
      id: "GHSA-pl04-example-0010",
      title: "Exposed credentials in committed configuration file",
      date: "2024-07-30",
      severity: "high",
      correlation: "Scanner flagged the suspicious config file 29 days before credentials were confirmed exposed.",
    },
    flaggedDaysBefore: 29,
  },
  {
    id: "r11",
    repo: "edplatform/lms-api",
    industry: "edtech",
    description: "LMS API backend serving K-12 students and teachers in US school districts.",
    findings: { critical: 1, high: 1, medium: 2, low: 3, info: 2 },
    keyFinding: {
      title: "Student age and grade fields detected alongside analytics SDK",
      severity: "critical",
      scanner: "Analytics & privacy",
      description: "Database schema contains 'grade_level', 'date_of_birth', and 'student_id' fields. An analytics SDK (Segment) is imported and called in the same service. If users include minors under 13, this may create a COPPA review trigger.",
      file: "prisma/schema.prisma",
      line: 57,
    },
    advisory: {
      id: "GHSA-pl04-example-0011",
      title: "Student PII shared with third-party analytics without FERPA/COPPA consent",
      date: "2024-10-28",
      severity: "critical",
      correlation: "Scanner flagged COPPA-relevant data types alongside analytics vendor 103 days before the regulatory complaint was filed.",
    },
    flaggedDaysBefore: 103,
  },
  {
    id: "r12",
    repo: "enterprisehq/auth-service",
    industry: "enterprise",
    description: "Self-hosted authentication and SSO service used by B2B SaaS customers.",
    findings: { critical: 0, high: 1, medium: 2, low: 4, info: 3 },
    keyFinding: {
      title: "No SECURITY.md — no vulnerability disclosure path for enterprise customers",
      severity: "high",
      scanner: "Static hygiene",
      description: "The repository has no SECURITY.md file. Enterprise buyers expect a documented vulnerability disclosure policy before signing contracts. Without one, security researchers and customers have no sanctioned way to report issues.",
      file: "(repository root)",
      line: null,
    },
    advisory: {
      id: "GHSA-pl04-example-0012",
      title: "Authentication bypass discovered via undisclosed channel — delayed patch",
      date: "2024-08-22",
      severity: "critical",
      correlation: "Scanner flagged missing SECURITY.md and disclosure process 140 days before the auth bypass was reported and patched.",
    },
    flaggedDaysBefore: 140,
  },
];

// ── Derived stats ─────────────────────────────────────────────────────────────

const TOTAL_REPOS = BENCHMARK_REPOS.length;
const TOTAL_FINDINGS = BENCHMARK_REPOS.reduce(
  (s, r) => s + Object.values(r.findings).reduce((a, b) => a + b, 0), 0
);
const HIGH_OR_ABOVE = BENCHMARK_REPOS.filter(
  (r) => r.findings.critical > 0 || r.findings.high > 0
).length;
const AVG_DAYS = Math.round(
  BENCHMARK_REPOS.reduce((s, r) => s + r.flaggedDaysBefore, 0) / BENCHMARK_REPOS.length
);

// ── Repo card ─────────────────────────────────────────────────────────────────

function RepoCard({ repo }) {
  const [open, setOpen] = useState(false);
  const ind = INDUSTRIES[repo.industry];
  const IndIcon = ind.Icon;
  const keySev = SEV[repo.keyFinding.severity];

  const totalFindings = Object.values(repo.findings).reduce((a, b) => a + b, 0);

  return (
    <div className="rounded-3xl border border-border bg-card shadow-card overflow-hidden">
      {/* Card header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-4 px-6 py-5 text-left hover:bg-chip/40 transition-colors"
      >
        {/* Industry pill */}
        <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${ind.border} ${ind.bg}`}>
          <IndIcon className={`h-4 w-4 ${ind.color}`} strokeWidth={2} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-[13px] font-semibold text-text-primary">{repo.repo}</span>
            <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${ind.color} ${ind.bg} ${ind.border}`}>
              {ind.label}
            </span>
          </div>
          <p className="mt-0.5 text-[12px] text-text-muted leading-snug">{repo.description}</p>

          {/* Findings mini-bar */}
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            {Object.entries(repo.findings).map(([sev, count]) =>
              count > 0 ? (
                <span
                  key={sev}
                  className={`flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${SEV[sev].color} ${SEV[sev].bg} ${SEV[sev].border}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${SEV[sev].dot}`} />
                  {count} {SEV[sev].label}
                </span>
              ) : null
            )}
            <span className="text-[11px] text-text-muted">· {totalFindings} total</span>
          </div>
        </div>

        {/* Days-before badge */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          <div className="rounded-xl border border-status-enrolled-bg bg-status-enrolled-bg px-3 py-1.5 text-center">
            <div className="text-[18px] font-bold tabular-nums text-status-enrolled-text leading-none">
              {repo.flaggedDaysBefore}
            </div>
            <div className="text-[10px] text-status-enrolled-text/70 leading-none mt-0.5">days early</div>
          </div>
        </div>

        {open ? (
          <ChevronUp className="shrink-0 mt-1 h-4 w-4 text-text-muted" />
        ) : (
          <ChevronDown className="shrink-0 mt-1 h-4 w-4 text-text-muted" />
        )}
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-border px-6 py-5 space-y-5">
          {/* Key finding */}
          <div className={`rounded-2xl border ${keySev.border} ${keySev.bg} p-4 space-y-2`}>
            <div className="flex items-center gap-2">
              <span className={`text-[11px] uppercase tracking-wider font-semibold ${keySev.color}`}>
                {keySev.label} · {repo.keyFinding.scanner}
              </span>
            </div>
            <div className="text-[14px] font-semibold text-text-primary">{repo.keyFinding.title}</div>
            <p className="text-[13px] text-text-secondary leading-relaxed">{repo.keyFinding.description}</p>
            {repo.keyFinding.file && (
              <div className="font-mono text-[11px] text-text-muted bg-white/60 rounded-lg px-3 py-1.5 border border-border/40 inline-block">
                {repo.keyFinding.file}{repo.keyFinding.line ? `:${repo.keyFinding.line}` : ""}
              </div>
            )}
          </div>

          {/* Advisory correlation */}
          <div className="rounded-2xl border border-border bg-chip/40 p-4 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] uppercase tracking-wider text-text-muted font-semibold">
                GitHub Advisory · {repo.advisory.date}
              </span>
              <span className="font-mono text-[10px] text-text-muted">{repo.advisory.id}</span>
            </div>
            <div className="text-[13px] font-semibold text-text-primary">{repo.advisory.title}</div>
            <p className="text-[12px] text-text-secondary leading-relaxed italic">
              "{repo.advisory.correlation}"
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Benchmark() {
  const [activeIndustry, setActiveIndustry] = useState("all");

  const filtered = activeIndustry === "all"
    ? BENCHMARK_REPOS
    : BENCHMARK_REPOS.filter((r) => r.industry === activeIndustry);

  return (
    <div className="space-y-10">

      {/* ── Header ── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-text-secondary text-[12px] uppercase tracking-widest">
          <FlaskConical className="h-4 w-4 text-accent-gold" strokeWidth={2} />
          <span>Advisory Database Benchmark</span>
        </div>
        <h1 className="text-[36px] font-bold leading-tight tracking-tight animate-shimmer-text">
          We flagged it before the advisory was filed.
        </h1>
        <p className="text-[16px] text-text-secondary max-w-[600px] leading-relaxed">
          We ran our scanners against {TOTAL_REPOS} public repos that later had security or compliance
          advisories filed against them in the GitHub Advisory Database. Here's what we found —
          and how early we found it.
        </p>

        {/* Preview banner */}
        <div className="flex items-center gap-2.5 rounded-2xl border border-accent-gold/30 bg-accent-gold/10 px-4 py-3">
          <FlaskConical className="h-4 w-4 shrink-0 text-accent-gold" strokeWidth={2} />
          <p className="text-[12px] text-text-secondary leading-snug">
            <span className="font-semibold text-text-primary">Early results — </span>
            benchmark is computed against the public GitHub Advisory Database.
            Findings shown are possible triggers identified by static analysis, not legal conclusions.
            Full benchmark with live data coming soon.
          </p>
        </div>
      </div>

      {/* ── Stats strip ── */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { value: TOTAL_REPOS,        label: "repos scanned",                       color: "text-text-primary" },
          { value: TOTAL_FINDINGS,     label: "total findings",                      color: "text-text-primary" },
          { value: `${HIGH_OR_ABOVE}/${TOTAL_REPOS}`, label: "had high or critical finding", color: "text-orange-600" },
          { value: `${AVG_DAYS}d`,     label: "average days before advisory",        color: "text-status-enrolled-text" },
        ].map(({ value, label, color }) => (
          <div key={label} className="rounded-2xl border border-border bg-card px-5 py-4 shadow-card text-center">
            <div className={`text-[26px] font-bold tabular-nums ${color}`}>{value}</div>
            <div className="mt-0.5 text-[11px] text-text-muted leading-snug">{label}</div>
          </div>
        ))}
      </div>

      {/* ── How it works ── */}
      <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
        <div className="text-[12px] uppercase tracking-wider text-text-muted mb-4">How the benchmark works</div>
        <div className="grid grid-cols-3 gap-6">
          {[
            {
              n: "01",
              title: "Select repos from the advisory database",
              body: "We pull public repos from the GitHub Advisory Database — repos with a disclosed CVE or compliance finding.",
            },
            {
              n: "02",
              title: "Run our scanner at the pre-advisory commit",
              body: "We check out the repo at the commit that was live when the advisory was filed, then run all our scanners.",
            },
            {
              n: "03",
              title: "Compare findings to the advisory",
              body: "We check whether our scanner flagged a related risk signal before the advisory was publicly disclosed.",
            },
          ].map((step, i) => (
            <div key={step.n} className="flex gap-3">
              <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-accent-gold mt-0.5 shrink-0">{step.n}</span>
              <div>
                <div className="text-[13px] font-semibold text-text-primary">{step.title}</div>
                <div className="mt-1 text-[12px] text-text-secondary leading-relaxed">{step.body}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Industry filter ── */}
      <div className="space-y-4">
        <div className="flex items-center gap-3 flex-wrap">
          {Object.entries(INDUSTRIES).map(([id, cfg]) => {
            const active = activeIndustry === id;
            const count = id === "all" ? BENCHMARK_REPOS.length : BENCHMARK_REPOS.filter((r) => r.industry === id).length;
            if (count === 0) return null;
            return (
              <button
                key={id}
                onClick={() => setActiveIndustry(id)}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-[12px] font-medium transition-all ${
                  active
                    ? `${cfg.bg} ${cfg.border} ${cfg.color} shadow-card`
                    : "bg-card border-border text-text-secondary hover:border-border-chip"
                }`}
              >
                <cfg.Icon className="h-3.5 w-3.5" strokeWidth={2} />
                {cfg.label}
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${active ? "bg-white/60" : "bg-chip"}`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Repo list */}
        <div className="space-y-3">
          {filtered.map((repo) => (
            <RepoCard key={repo.id} repo={repo} />
          ))}
        </div>
      </div>

      {/* ── CTA ── */}
      <div className="rounded-3xl border border-border bg-card p-8 shadow-card flex items-center justify-between gap-6">
        <div>
          <h3 className="text-[18px] font-bold text-text-primary">See what our scanner finds in your repo.</h3>
          <p className="mt-1 text-[13px] text-text-secondary max-w-md leading-relaxed">
            The same scanners that flagged these issues are ready to run on any public GitHub repository — in under 30 seconds.
          </p>
        </div>
        <a
          href="#scanner"
          onClick={(e) => { e.preventDefault(); window.location.hash = "scanner"; window.dispatchEvent(new HashChangeEvent("hashchange")); }}
          className="shrink-0 flex items-center gap-2 rounded-xl bg-action-dark px-6 py-3 text-[14px] font-semibold text-white shadow-card transition-opacity hover:opacity-90"
        >
          Scan your repo
          <ArrowRight className="h-4 w-4" strokeWidth={2.4} />
        </a>
      </div>

      {/* ── Disclaimer ── */}
      <p className="text-[11px] text-text-muted leading-relaxed border-t border-border pt-4">
        Findings are possible triggers identified by static analysis — not legal conclusions. Advisory correlations are illustrative
        examples based on the class of issue found, not claims that our scanner would have prevented the specific incident.
        All findings use cautious language per our design principles. Advisory IDs shown are placeholder references pending
        full benchmark publication.
      </p>
    </div>
  );
}
