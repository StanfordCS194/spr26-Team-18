import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  MessageCircle,
  RefreshCw,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { AXES, AXIS_LABELS } from "./startupRubric";
import { STARTUP_RECOMMENDATIONS_KEY } from "./StartupGrader";

function loadSnapshot() {
  try {
    const raw = localStorage.getItem(STARTUP_RECOMMENDATIONS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function timeAgo(ts) {
  if (!ts) return "unknown";
  const s = Math.max(1, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function impactLabel(action) {
  if (action.dollarImpact > 0) {
    return `up to $${action.dollarImpact.toLocaleString()} downside`;
  }
  return `${action.weight}pt grade leverage`;
}

function priorityTone(index) {
  if (index === 0) return "border-red-200 bg-red-50/60 text-red-700";
  if (index < 3) return "border-orange-200 bg-orange-50/60 text-orange-700";
  return "border-border bg-chip-alt text-text-secondary";
}

const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

function repoName(url = "") {
  const match = url.match(/github\.com\/([^/]+\/[^/?#]+)/i);
  return match ? match[1].replace(/\.git$/, "") : url || "latest repository";
}

function scanLocation(finding) {
  const evidence = Array.isArray(finding.evidence) ? finding.evidence : [];
  const firstEvidence = evidence[0] || {};
  const location = firstEvidence.location || {};
  const path = finding.path || location.path || firstEvidence.path || firstEvidence.file;
  const line = finding.line || location.line_start || firstEvidence.line_start || firstEvidence.line;
  if (!path) return null;
  return `${path}${line ? `:${line}` : ""}`;
}

export default function ActiveRecommendations({
  snapshot,
  latestRepoScan = null,
  onOpenScanner,
  onOpenIssues,
  onOpenLegal,
  onGoToStartup,
}) {
  const [storedSnapshot, setStoredSnapshot] = useState(() => snapshot || loadSnapshot());
  const openScanner = onOpenScanner || onGoToStartup;
  const scanFindings = Array.isArray(latestRepoScan?.results?.findings)
    ? latestRepoScan.results.findings
    : [];
  const rankedFindings = [...scanFindings]
    .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9))
    .slice(0, 6);

  useEffect(() => {
    if (snapshot) setStoredSnapshot(snapshot);
  }, [snapshot]);

  useEffect(() => {
    function onStorage() {
      setStoredSnapshot(loadSnapshot());
    }
    function onUpdated(event) {
      setStoredSnapshot(event.detail || loadSnapshot());
    }
    window.addEventListener("storage", onStorage);
    window.addEventListener("startup-recommendations-updated", onUpdated);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("startup-recommendations-updated", onUpdated);
    };
  }, []);

  const actions = storedSnapshot?.topActions || [];
  const axisRisks = useMemo(() => {
    if (!storedSnapshot?.axisResults) return [];
    return AXES.map((axis) => ({
      axis,
      label: AXIS_LABELS[axis],
      score: storedSnapshot.axisResults[axis]?.score ?? 0,
      failed: storedSnapshot.axisResults[axis]?.failed || [],
      skipped: storedSnapshot.axisResults[axis]?.skipped || 0,
      evaluated: storedSnapshot.axisResults[axis]?.evaluated || 0,
    })).sort((a, b) => {
      if (!a.evaluated && !b.evaluated) return 0;
      if (!a.evaluated) return 1;
      if (!b.evaluated) return -1;
      return a.score - b.score;
    });
  }, [storedSnapshot]);

  if (!storedSnapshot && scanFindings.length > 0) {
    return (
      <section className="space-y-7">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-text-secondary">
              <MessageCircle className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
              <span className="text-[12px] uppercase tracking-[0.18em]">
                Recommendations Engine
              </span>
            </div>
            <h1 className="text-[32px] font-bold tracking-tight">Recommended fixes from the latest scan.</h1>
            <p className="max-w-[720px] text-[14px] leading-relaxed text-text-secondary">
              Prioritized from {scanFindings.length} scanner findings on{" "}
              <span className="font-medium text-text-primary">{repoName(latestRepoScan?.repoUrl)}</span>.
              Use this as the demo worklist after the repository scan completes.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={onOpenIssues}
              className="flex items-center gap-1.5 rounded-full bg-action-dark px-4 py-2 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90"
            >
              Review by file
              <ArrowRight className="h-3.5 w-3.5" strokeWidth={2.4} />
            </button>
            <button
              onClick={onOpenLegal}
              className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card transition-all hover:text-text-primary"
            >
              Legal context
            </button>
          </div>
        </header>

        <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
            <TriangleAlert className="h-3.5 w-3.5 text-accent-gold" strokeWidth={2.4} />
            Top scanner-driven recommendations
          </div>
          <ol className="space-y-3">
            {rankedFindings.map((finding, index) => (
              <li
                key={finding.id || `${finding.title}-${index}`}
                className="rounded-2xl border border-border bg-chip-alt p-4 transition-all hover:bg-card hover:shadow-card"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={
                      "flex h-7 w-7 flex-none items-center justify-center rounded-full border text-[12px] font-bold " +
                      priorityTone(index)
                    }
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-[14px] font-semibold leading-snug text-text-primary">
                        {finding.title}
                      </h3>
                      <span className="rounded-full bg-card px-2 py-0.5 text-[11px] capitalize text-text-secondary">
                        {finding.severity || "info"}
                      </span>
                      {(finding.scanner_id || finding.scanner) && (
                        <span className="rounded-full bg-card px-2 py-0.5 text-[11px] text-text-secondary">
                          {String(finding.scanner_id || finding.scanner).replace(/_/g, " ")}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
                      {finding.recommendation || finding.description || "Review the mapped evidence and remediate the underlying control gap."}
                    </p>
                    {scanLocation(finding) && (
                      <div className="mt-2 inline-flex rounded-full border border-border bg-card px-2.5 py-1 font-mono text-[11px] text-text-muted">
                        {scanLocation(finding)}
                      </div>
                    )}
                  </div>
                  <ArrowRight className="mt-1 h-4 w-4 flex-none text-text-muted" />
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
    );
  }

  if (!storedSnapshot) {
    return (
      <section className="space-y-6">
        <header className="space-y-2">
          <div className="flex items-center gap-2 text-text-secondary">
            <MessageCircle className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
            <span className="text-[12px] uppercase tracking-[0.18em]">
              Recommendations Engine
            </span>
          </div>
          <h1 className="text-[32px] font-bold tracking-tight">No active grade yet.</h1>
          <p className="max-w-[640px] text-[14px] leading-relaxed text-text-secondary">
            Run a repository scan first. The recommendations workspace is most useful after
            findings are available, with file review, legal intelligence, and benchmark context
            ready for the demo.
          </p>
        </header>
        <button
          onClick={openScanner}
          className="flex items-center gap-2 rounded-full bg-action-dark px-5 py-2.5 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90"
        >
          <Sparkles className="h-3.5 w-3.5" strokeWidth={2.4} />
          Open Repo Scanner
        </button>
      </section>
    );
  }

  return (
    <section className="space-y-7">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-text-secondary">
          <MessageCircle className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">
            Recommendations Engine
          </span>
        </div>
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-[32px] font-bold tracking-tight">Highest-leverage fixes.</h1>
            <p className="mt-2 max-w-[720px] text-[14px] leading-relaxed text-text-secondary">
              Ranked from the latest readiness snapshot for{" "}
              <span className="font-medium text-text-primary">{storedSnapshot.name}</span>.
              Grade {storedSnapshot.grade} · {storedSnapshot.composite}/100 ·{" "}
              {(storedSnapshot.evaluatedAxes || []).length || AXES.length}/{AXES.length} axes evaluated ·{" "}
              {timeAgo(storedSnapshot.timestamp)}.
            </p>
          </div>
          <button
            onClick={openScanner}
            className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card transition-all hover:text-text-primary"
          >
            <RefreshCw className="h-3.5 w-3.5" strokeWidth={2.4} />
            Re-scan
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,340px]">
        <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
            <TriangleAlert className="h-3.5 w-3.5 text-accent-gold" strokeWidth={2.4} />
            Active recommendations
          </div>
          {actions.length === 0 ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-[14px] text-emerald-800">
              <div className="mb-1 flex items-center gap-2 font-semibold">
                <CheckCircle2 className="h-4 w-4" />
                No failed rules in the current grade.
              </div>
              The readiness rubric found no active recommendations.
            </div>
          ) : (
            <ol className="space-y-3">
              {actions.map((action, index) => (
                <li
                  key={action.id}
                  className="rounded-2xl border border-border bg-chip-alt p-4 transition-all hover:bg-card hover:shadow-card"
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={
                        "flex h-7 w-7 flex-none items-center justify-center rounded-full border text-[12px] font-bold " +
                        priorityTone(index)
                      }
                    >
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-[14px] font-semibold leading-snug text-text-primary">
                          {action.title}
                        </h3>
                        <span className="rounded-full bg-card px-2 py-0.5 text-[11px] text-text-secondary">
                          {AXIS_LABELS[action.axis]}
                        </span>
                      </div>
                      <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
                        {action.fix}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="rounded-full bg-card px-2 py-0.5 text-text-muted">
                          Observed: {action.observed}
                        </span>
                        <span className="rounded-full bg-red-50 px-2 py-0.5 text-red-700">
                          {impactLabel(action)}
                        </span>
                      </div>
                      {action.locations?.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {action.locations.slice(0, 4).map((loc) => (
                            <div
                              key={`${action.id}:${loc.path}:${loc.line}:${loc.title}`}
                              className="rounded-xl border border-border-muted bg-card px-3 py-2 font-mono text-[11px] leading-relaxed text-text-secondary"
                            >
                              <div className="mb-1 flex flex-wrap items-center gap-2 font-sans">
                                <span className="font-semibold text-text-primary">
                                  {loc.path}:{loc.line}
                                </span>
                                <span className="rounded-full bg-chip-alt px-2 py-0.5 text-[10px] uppercase tracking-wide text-text-muted">
                                  {loc.severity}
                                </span>
                              </div>
                              <div className="break-words">{loc.snippet}</div>
                              <div className="mt-1 font-sans text-[12px] text-text-muted">
                                Change: {loc.recommendation}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <ArrowRight className="mt-1 h-4 w-4 flex-none text-text-muted" />
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>

        <aside className="space-y-4">
          <div className="rounded-3xl border border-border bg-card p-5 shadow-card">
            <div className="mb-3 text-[11px] uppercase tracking-[0.18em] text-text-muted">
              Weakest axes
            </div>
            <div className="space-y-3">
              {axisRisks.slice(0, 5).map((axis) => (
                <div key={axis.axis}>
                  <div className="mb-1 flex items-center justify-between text-[12px]">
                    <span className="font-medium text-text-primary">{axis.label}</span>
                    <span className="font-mono text-text-secondary">
                      {axis.evaluated ? `${axis.score}/100` : "N/A"}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-chip-alt">
                    <div
                      className="h-full rounded-full bg-action-dark"
                      style={{ width: `${axis.evaluated ? Math.max(0, Math.min(100, axis.score)) : 0}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[11px] text-text-muted">
                    {axis.evaluated
                      ? `${axis.failed.length} failed · ${axis.skipped} skipped`
                      : "not evaluated"}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-card p-5 text-[12px] leading-relaxed text-text-secondary shadow-card">
            <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
              <Sparkles className="h-3 w-3 text-accent-gold" strokeWidth={2.4} />
              How this interfaces
            </div>
            Recommendations consumes the latest scored result, ranks failed evaluated checks by
            downside and rule weight, and keeps the worklist available after navigating away.
          </div>
        </aside>
      </div>
    </section>
  );
}
