import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  Code2,
  Database,
  FileCode2,
  FlaskConical,
  GitBranch,
  Landmark,
  MessageCircle,
  Rocket,
  Scale,
  ShieldAlert,
  Users,
  RefreshCw,
} from "lucide-react";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];

const SEV_META = {
  critical: { label: "Critical", color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
  high: { label: "High", color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200" },
  medium: { label: "Medium", color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200" },
  low: { label: "Low", color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200" },
  info: { label: "Info", color: "text-slate-500", bg: "bg-slate-50", border: "border-slate-200" },
};

const INDUSTRY_LABELS = {
  health: "Health & MedTech",
  fintech: "Fintech",
  saas: "Consumer SaaS",
  edtech: "EdTech",
  devtools: "Developer Tools",
  ai: "AI / ML",
  enterprise: "Enterprise B2B",
  other: "Other / General",
};

function repoName(url = "") {
  const match = url.match(/github\.com\/([^/]+\/[^/?#]+)/i);
  return match ? match[1].replace(/\.git$/, "") : url || "No repo connected";
}

function formatProfileValue(value) {
  if (!value) return "Not set";
  return String(value)
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function scanSummary(scan) {
  const findings = scan?.results?.findings ?? [];
  const counts = Object.fromEntries(
    SEVERITIES.map((severity) => [
      severity,
      findings.filter((finding) => finding.severity === severity).length,
    ])
  );
  return {
    findings,
    counts,
    total: findings.length,
    urgent: (counts.critical ?? 0) + (counts.high ?? 0),
    mapped: findings.filter((finding) => {
      const evidence = Array.isArray(finding.evidence) ? finding.evidence : [];
      return finding.path || evidence.some((item) => item.location?.path || item.file || item.path);
    }).length,
  };
}

function TopMetric({ label, value, detail, tone = "slate", Icon }) {
  const tones = {
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    orange: "border-orange-200 bg-orange-50 text-orange-700",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    slate: "border-border bg-card text-text-primary",
  };
  return (
    <div className={`rounded-2xl border p-4 shadow-card ${tones[tone] ?? tones.slate}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">{label}</div>
          <div className="mt-2 text-[30px] font-bold leading-none tabular-nums">{value}</div>
        </div>
        <Icon className="h-5 w-5 opacity-70" strokeWidth={2.1} />
      </div>
      <div className="mt-2 text-[12px] leading-relaxed opacity-75">{detail}</div>
    </div>
  );
}

function NavCard({ id, title, body, Icon, onTabChange }) {
  return (
    <button
      onClick={() => onTabChange(id)}
      className="group rounded-2xl border border-border bg-card p-4 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-action-dark hover:shadow-card-hover"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-chip-alt">
          <Icon className="h-5 w-5 text-action-dark" strokeWidth={2.1} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="font-semibold text-text-primary">{title}</div>
            <ArrowRight className="h-3.5 w-3.5 text-text-muted transition-transform group-hover:translate-x-1 group-hover:text-action-dark" strokeWidth={2.3} />
          </div>
          <div className="mt-1 text-[12px] leading-relaxed text-text-secondary">{body}</div>
        </div>
      </div>
    </button>
  );
}

function SeverityStrip({ counts }) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {SEVERITIES.map((severity) => {
        const cfg = SEV_META[severity];
        return (
          <div key={severity} className={`rounded-xl border px-3 py-2 text-center ${cfg.border} ${cfg.bg}`}>
            <div className={`text-[18px] font-bold tabular-nums ${cfg.color}`}>{counts[severity] ?? 0}</div>
            <div className="text-[10px] text-text-muted">{cfg.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function WorkItem({ title, body, action, onClick, urgent = false }) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-3 rounded-xl border border-border bg-white px-4 py-3 text-left transition-all hover:border-action-dark hover:shadow-card"
    >
      <div className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${urgent ? "bg-orange-500" : "bg-emerald-500"}`} />
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-semibold text-text-primary">{title}</div>
        <div className="mt-0.5 text-[12px] leading-relaxed text-text-secondary">{body}</div>
      </div>
      <div className="shrink-0 text-[11px] font-semibold text-action-dark">{action}</div>
    </button>
  );
}

export default function HomePage({
  onTabChange,
  profile = null,
  latestRepoScan = null,
  recommendations = null,
}) {
  const summary = scanSummary(latestRepoScan);
  const connectedRepo = latestRepoScan?.repoUrl || profile?.repoUrl || "";
  const companyName = profile?.companyName || latestRepoScan?.productName || "Demo workspace";
  const industry = INDUSTRY_LABELS[profile?.industry || latestRepoScan?.industry] || "Not set";
  const hasScan = Boolean(latestRepoScan?.results);
  const recCount = Array.isArray(recommendations?.recommendations)
    ? recommendations.recommendations.length
    : Array.isArray(recommendations)
      ? recommendations.length
      : 0;
  const [legalStatus, setLegalStatus] = useState(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/legal-intelligence/status")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (alive) setLegalStatus(data);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="space-y-6 pb-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            <Building2 className="h-4 w-4" strokeWidth={2} />
            Workspace
          </div>
          <h1 className="text-[34px] font-bold tracking-tight text-text-primary">
            {companyName} dashboard
          </h1>
          <p className="mt-1 max-w-[680px] text-[14px] leading-relaxed text-text-secondary">
            Track repository risk, legal exposure, financial readiness, and action items from one working view.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onTabChange("scanner")}
            className="flex items-center gap-2 rounded-xl bg-action-dark px-4 py-2.5 text-[13px] font-semibold text-white shadow-card transition-opacity hover:opacity-90"
          >
            <GitBranch className="h-4 w-4" strokeWidth={2.2} />
            Scan repo
          </button>
          {hasScan && (
            <button
              onClick={() => onTabChange("issues")}
              className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] font-semibold text-text-primary shadow-card transition-all hover:border-action-dark"
            >
              <FileCode2 className="h-4 w-4" strokeWidth={2.2} />
              Review code
            </button>
          )}
        </div>
      </header>

      <section className="grid grid-cols-4 gap-4">
        <TopMetric
          label="Repo Findings"
          value={hasScan ? summary.total : "-"}
          detail={hasScan ? `${summary.mapped} mapped to files or evidence.` : "Run a repo scan to populate this."}
          tone="blue"
          Icon={ShieldAlert}
        />
        <TopMetric
          label="High Priority"
          value={hasScan ? summary.urgent : "-"}
          detail={hasScan ? "Critical and high severity findings." : "Waiting for scanner results."}
          tone={summary.urgent > 0 ? "orange" : "green"}
          Icon={AlertTriangle}
        />
        <TopMetric
          label="Profile"
          value={profile ? "Ready" : "Basic"}
          detail={profile ? `${industry} · ${formatProfileValue(profile.stage)}` : "Signed in without onboarding."}
          tone="slate"
          Icon={Rocket}
        />
        <TopMetric
          label="Action Items"
          value={recCount || (hasScan ? Math.min(summary.total, 5) : "-")}
          detail={recCount ? "Active recommendations generated." : "Prioritized after scan and grading."}
          tone="green"
          Icon={CheckCircle2}
        />
      </section>

      <section className="grid grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)] gap-5">
        <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">Latest repo scan</div>
              <h2 className="mt-1 text-[20px] font-bold text-text-primary">{repoName(connectedRepo)}</h2>
              <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
                {hasScan
                  ? "Review severity totals and jump into file-by-file comments."
                  : "No scan results in this session yet. Start with a public GitHub repo."}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => onTabChange("scanner")}
                className="rounded-xl border border-border bg-chip-alt px-3 py-2 text-[12px] font-semibold text-text-primary transition-colors hover:border-action-dark"
              >
                {hasScan ? "New scan" : "Start scan"}
              </button>
              <button
                onClick={() => onTabChange("issues")}
                disabled={!hasScan}
                className="rounded-xl bg-action-dark px-3 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Review by file
              </button>
            </div>
          </div>
          <div className="mt-5">
            <SeverityStrip counts={summary.counts} />
          </div>
          <div className="mt-5 grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-border bg-chip-alt px-4 py-3">
              <div className="text-[11px] text-text-muted">Industry</div>
              <div className="mt-1 text-[13px] font-semibold text-text-primary">{industry}</div>
            </div>
            <div className="rounded-xl border border-border bg-chip-alt px-4 py-3">
              <div className="text-[11px] text-text-muted">Data profile</div>
              <div className="mt-1 text-[13px] font-semibold text-text-primary">{formatProfileValue(profile?.sensitiveData)}</div>
            </div>
            <div className="rounded-xl border border-border bg-chip-alt px-4 py-3">
              <div className="text-[11px] text-text-muted">GTM</div>
              <div className="mt-1 text-[13px] font-semibold text-text-primary">{formatProfileValue(profile?.gtm)}</div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <button
            onClick={() => onTabChange("legal")}
            className="mb-4 flex w-full items-center justify-between gap-4 rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-left transition-all hover:border-orange-300"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white">
                <Database className="h-5 w-5 text-orange-600" strokeWidth={2.2} />
              </div>
              <div className="min-w-0">
                <div className="text-[13px] font-semibold text-text-primary">Legal guidance freshness</div>
                <div className="mt-0.5 text-[12px] text-text-secondary">
                  {legalStatus?.last_checked
                    ? `Last refreshed ${new Date(legalStatus.last_checked).toLocaleString()}`
                    : `${legalStatus?.source_count ?? 0} configured sources; no refresh has run yet`}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <div className="text-right">
                <div className="text-[20px] font-bold tabular-nums text-orange-600">
                  {legalStatus?.enabled_rule_count ?? 0}
                </div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">rules</div>
              </div>
              <RefreshCw className="h-4 w-4 text-text-muted" strokeWidth={2.3} />
            </div>
          </button>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">Work queue</div>
          <div className="mt-4 space-y-2">
            <WorkItem
              title={hasScan ? "Inspect file-level findings" : "Run repository scanner"}
              body={hasScan ? "Open GitHub-style comments on affected lines." : "Connect a public GitHub repo and generate evidence-backed findings."}
              action={hasScan ? "Open" : "Scan"}
              urgent={hasScan && summary.urgent > 0}
              onClick={() => onTabChange(hasScan ? "issues" : "scanner")}
            />
            <WorkItem
              title="Review legal intelligence"
              body="Open source-backed legal context and automatic legal savings."
              action="Open"
              onClick={() => onTabChange("legal")}
            />
            <WorkItem
              title="Compare benchmarks"
              body="Use advisory-style examples to explain risk in a demo-friendly way."
              action="View"
              onClick={() => onTabChange("benchmark")}
            />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-3 gap-4">
        <NavCard
          id="scanner"
          title="Repo Scanner"
          body="Run deterministic checks and AI agents against a public GitHub repository."
          Icon={Code2}
          onTabChange={onTabChange}
        />
        <NavCard
          id="issues"
          title="Review By File"
          body="Inspect full source files with inline comments on only the affected lines."
          Icon={FileCode2}
          onTabChange={onTabChange}
        />
        <NavCard
          id="benchmark"
          title="Benchmark"
          body="Compare findings to sample advisory patterns and industry scenarios."
          Icon={FlaskConical}
          onTabChange={onTabChange}
        />
        <NavCard
          id="recs"
          title="Recommendations"
          body="Track prioritized next steps from grading and scanner output."
          Icon={MessageCircle}
          onTabChange={onTabChange}
        />
        <NavCard
          id="legal"
          title="Legal"
          body="Review regulatory and legal cost signals tied to your company context."
          Icon={Scale}
          onTabChange={onTabChange}
        />
        <NavCard
          id="financial"
          title="Financial"
          body="Estimate runway, tax-credit readiness, and finance compliance status."
          Icon={Landmark}
          onTabChange={onTabChange}
        />
        <NavCard
          id="scanner"
          title="Company Profile"
          body={`${formatProfileValue(profile?.customers)} customers · ${formatProfileValue(profile?.stage)} stage.`}
          Icon={Users}
          onTabChange={onTabChange}
        />
        <NavCard
          id="scanner"
          title="Data Handling"
          body={`Sensitive data: ${formatProfileValue(profile?.sensitiveData)}.`}
          Icon={Database}
          onTabChange={onTabChange}
        />
      </section>
    </div>
  );
}
