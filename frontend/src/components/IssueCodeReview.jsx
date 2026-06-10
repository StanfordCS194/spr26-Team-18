import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  FileCode2,
  GitBranch,
  Info,
  Loader2,
  Search,
  XCircle,
} from "lucide-react";

const GH = "https://api.github.com";
const RAW_GH = "https://raw.githubusercontent.com";

const SEV = {
  critical: { label: "Critical", color: "text-red-600", bg: "bg-red-50", border: "border-red-200", Icon: XCircle },
  high: { label: "High", color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200", Icon: AlertTriangle },
  medium: { label: "Medium", color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200", Icon: AlertTriangle },
  low: { label: "Low", color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200", Icon: Info },
  info: { label: "Info", color: "text-slate-500", bg: "bg-slate-50", border: "border-slate-200", Icon: Info },
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];
export default function IssueCodeReview({ scan, onGoToScanner }) {
  const findings = scan?.results?.findings ?? [];
  const isPlaceholder = Boolean(scan?.results?.placeholder);
  const repo = useMemo(() => parseRepo(scan?.repoUrl), [scan?.repoUrl]);
  const issues = useMemo(() => findings.map((finding, index) => normalizeFinding(finding, index, isPlaceholder)), [findings, isPlaceholder]);
  const scannerIds = useMemo(
    () => Array.from(new Set(issues.map((issue) => issue.scannerId).filter(Boolean))).sort(),
    [issues]
  );

  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [scannerId, setScannerId] = useState("all");
  const [selectedId, setSelectedId] = useState(null);
  const [branch, setBranch] = useState("main");
  const [branchState, setBranchState] = useState("idle");
  const [fileCache, setFileCache] = useState({});

  useEffect(() => {
    setSelectedId(null);
    setFileCache({});
  }, [scan?.repoUrl, scan?.results]);

  useEffect(() => {
    if (!repo) return;
    let cancelled = false;
    setBranchState("loading");
    fetch(`${GH}/repos/${repo.owner}/${repo.name}`, {
      headers: { Accept: "application/vnd.github+json" },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        setBranch(data?.default_branch || "main");
        setBranchState(data?.default_branch ? "ready" : "fallback");
      })
      .catch(() => {
        if (!cancelled) setBranchState("fallback");
      });
    return () => {
      cancelled = true;
    };
  }, [repo?.owner, repo?.name]);

  const filteredIssues = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return issues.filter((issue) => {
      if (severity !== "all" && issue.severity !== severity) return false;
      if (scannerId !== "all" && issue.scannerId !== scannerId) return false;
      if (!needle) return true;
      return [issue.title, issue.description, issue.path, issue.scannerId, issue.recommendation]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle));
    });
  }, [issues, query, scannerId, severity]);

  useEffect(() => {
    if (filteredIssues.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!filteredIssues.some((issue) => issue.id === selectedId)) {
      setSelectedId(filteredIssues[0].id);
    }
  }, [filteredIssues, selectedId]);

  const selectedIssue = filteredIssues.find((issue) => issue.id === selectedId) ?? filteredIssues[0] ?? null;
  const selectedPath = selectedIssue?.path;
  const selectedLine = selectedIssue?.line;

  useEffect(() => {
    if (!repo || !selectedPath || fileCache[selectedPath]) return;
    setFileCache((prev) => ({
      ...prev,
      [selectedPath]: { state: "loading", text: "", error: "" },
    }));
    const url = `${RAW_GH}/${repo.owner}/${repo.name}/${encodeURIComponent(branch)}/${selectedPath
      .split("/")
      .map(encodeURIComponent)
      .join("/")}`;
    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(`GitHub returned ${res.status}`);
        return res.text();
      })
      .then((text) => {
        setFileCache((prev) => ({
          ...prev,
          [selectedPath]: { state: "ready", text, error: "" },
        }));
      })
      .catch((err) => {
        setFileCache((prev) => ({
          ...prev,
          [selectedPath]: { state: "error", text: "", error: err.message || "Could not load file" },
        }));
      });
  }, [branch, fileCache, repo, selectedPath]);

  if (!scan) {
    return <EmptyState onGoToScanner={onGoToScanner} />;
  }

  const counts = Object.fromEntries(
    SEVERITY_ORDER.map((key) => [key, issues.filter((issue) => issue.severity === key).length])
  );
  const mappedCount = issues.filter((issue) => issue.path && issue.line).length;
  const fileGroups = groupIssuesByFile(filteredIssues);
  const unmappedIssues = filteredIssues.filter((issue) => !issue.path || !issue.line);
  const selectedFile = selectedPath ? fileCache[selectedPath] : null;
  const selectedFileIssues = selectedPath
    ? filteredIssues.filter((issue) => issue.path === selectedPath && issue.line)
    : selectedIssue ? [selectedIssue] : [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[13px] text-text-secondary">
            <GitBranch className="h-4 w-4" strokeWidth={1.7} />
            <span>{repo ? `${repo.owner}/${repo.name}` : scan.repoUrl}</span>
            <span className="text-text-muted">·</span>
            <span>{branchState === "loading" ? "loading branch" : branch}</span>
          </div>
          <h1 className="text-[30px] font-bold tracking-tight text-text-primary">Issues by file and line</h1>
          <p className="mt-1 text-[14px] leading-relaxed text-text-secondary">
            {issues.length} findings from the latest scan. {mappedCount} are mapped to a source location.
            {isPlaceholder && " Demo findings are illustrative; source files are loaded from the selected repository when available."}
          </p>
        </div>
        <button
          onClick={onGoToScanner}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card transition-colors hover:text-text-primary"
        >
          <ChevronRight className="h-3.5 w-3.5 rotate-180" strokeWidth={2.2} />
          Repo Scanner
        </button>
      </header>

      <div className="grid grid-cols-5 gap-3">
        {SEVERITY_ORDER.map((key) => {
          const cfg = SEV[key];
          return (
            <button
              key={key}
              onClick={() => setSeverity(severity === key ? "all" : key)}
              className={`rounded-xl border px-4 py-3 text-left transition-all ${
                severity === key ? `${cfg.border} ${cfg.bg} shadow-card` : "border-border bg-card hover:bg-chip-alt"
              }`}
            >
              <div className={`text-[20px] font-bold tabular-nums ${cfg.color}`}>{counts[key] ?? 0}</div>
              <div className="text-[11px] text-text-muted">{cfg.label}</div>
            </button>
          );
        })}
      </div>

      <div className="grid min-h-[680px] grid-cols-1 gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="space-y-3 border-b border-border p-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" strokeWidth={2} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search issues, files, scanners..."
                className="w-full rounded-xl border border-border bg-chip-alt py-2 pl-9 pr-3 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-action-dark"
              />
            </div>
            <div className="flex gap-2">
              <select
                value={severity}
                onChange={(event) => setSeverity(event.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-border bg-chip-alt px-3 py-2 text-[12px] text-text-secondary outline-none focus:border-action-dark"
              >
                <option value="all">All severities</option>
                {SEVERITY_ORDER.map((key) => (
                  <option key={key} value={key}>{SEV[key].label}</option>
                ))}
              </select>
              <select
                value={scannerId}
                onChange={(event) => setScannerId(event.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-border bg-chip-alt px-3 py-2 text-[12px] text-text-secondary outline-none focus:border-action-dark"
              >
                <option value="all">All scanners</option>
                {scannerIds.map((id) => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="max-h-[590px] overflow-y-auto p-3">
            {filteredIssues.length === 0 ? (
              <div className="px-3 py-10 text-center text-[13px] text-text-muted">No findings match these filters.</div>
            ) : (
              <div className="space-y-4">
                {fileGroups.length > 0 && (
                  <div className="space-y-2">
                    <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                      Files · {fileGroups.length}
                    </div>
                    {fileGroups.map((group) => (
                      <FileIssueGroup
                        key={group.path}
                        group={group}
                        selectedPath={selectedPath}
                        selectedId={selectedIssue?.id}
                        onSelect={setSelectedId}
                      />
                    ))}
                  </div>
                )}
                {unmappedIssues.length > 0 && (
                  <div className="space-y-2">
                    <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                      Unmapped findings · {unmappedIssues.length}
                    </div>
                    {unmappedIssues.map((issue) => (
                      <IssueListItem
                        key={issue.id}
                        issue={issue}
                        selected={issue.id === selectedIssue?.id}
                        onSelect={() => setSelectedId(issue.id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>

        <CodePane
          issue={selectedIssue}
          file={selectedFile}
          repo={repo}
          branch={branch}
          fileIssues={selectedFileIssues}
          targetLine={selectedLine}
          selectedIssueId={selectedIssue?.id}
          onSelectIssue={setSelectedId}
        />
      </div>
    </div>
  );
}

function EmptyState({ onGoToScanner }) {
  return (
    <div className="flex min-h-[520px] items-center justify-center">
      <div className="max-w-md rounded-3xl border border-border bg-card p-8 text-center shadow-card">
        <FileCode2 className="mx-auto h-11 w-11 text-accent-gold" strokeWidth={1.7} />
        <h1 className="mt-4 text-[24px] font-bold text-text-primary">No scan selected</h1>
        <p className="mt-2 text-[14px] leading-relaxed text-text-secondary">
          Run a repository scan to view issues by file and line.
        </p>
        <button
          onClick={onGoToScanner}
          className="mt-5 rounded-xl bg-action-dark px-5 py-2.5 text-[13px] font-semibold text-white shadow-card transition-opacity hover:opacity-90"
        >
          Go to Repo Scanner
        </button>
      </div>
    </div>
  );
}

function FileIssueGroup({ group, selectedPath, selectedId, onSelect }) {
  const topSeverity = group.issues[0]?.severity ?? "info";
  const cfg = SEV[topSeverity] ?? SEV.info;
  const selected = group.path === selectedPath;
  return (
    <section className={`overflow-hidden rounded-xl border ${selected ? `${cfg.border} bg-white` : "border-border bg-card"}`}>
      <button
        onClick={() => onSelect(group.issues[0].id)}
        className={`flex w-full items-start gap-2 px-3 py-3 text-left transition-colors ${
          selected ? cfg.bg : "bg-chip-alt hover:bg-white"
        }`}
      >
        <FileCode2 className={`mt-0.5 h-4 w-4 shrink-0 ${cfg.color}`} strokeWidth={2} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <div className="truncate font-mono text-[12px] font-semibold text-text-primary">{group.path}</div>
            <span className={`shrink-0 rounded-full border ${cfg.border} bg-white/70 px-2 py-0.5 text-[10px] font-semibold ${cfg.color}`}>
              {group.issues.length}
            </span>
          </div>
          <div className="mt-0.5 text-[11px] text-text-muted">
            {group.lineCount} affected line{group.lineCount === 1 ? "" : "s"}
          </div>
        </div>
      </button>
      <div className="space-y-1 border-t border-border/70 bg-white p-2 pl-5">
        <div className="mb-1 flex items-center gap-2 px-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
          <span className="h-px w-4 bg-border" />
          Issues
        </div>
        {group.issues.map((issue) => (
          <IssueListItem
            key={issue.id}
            issue={issue}
            selected={issue.id === selectedId}
            onSelect={() => onSelect(issue.id)}
            nested
          />
        ))}
      </div>
    </section>
  );
}

function IssueListItem({ issue, selected, onSelect, nested = false }) {
  const cfg = SEV[issue.severity] ?? SEV.info;
  return (
    <button
      onClick={onSelect}
      className={`w-full rounded-lg border text-left transition-all ${
        nested
          ? selected ? `${cfg.border} ${cfg.bg}` : "border-transparent hover:border-border hover:bg-chip-alt"
          : selected ? `${cfg.border} ${cfg.bg}` : "border-transparent hover:border-border hover:bg-chip-alt"
      } ${nested ? "px-2.5 py-2" : "px-3 py-3"}`}
    >
      <div className="flex items-start gap-2">
        <cfg.Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${cfg.color}`} strokeWidth={2.2} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-start justify-between gap-2">
            <div className="line-clamp-2 text-[12px] font-semibold leading-snug text-text-primary">{issue.title}</div>
            {issue.line && (
              <span className="shrink-0 rounded-md border border-border bg-white px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
                L{issue.line}
              </span>
            )}
          </div>
          {!nested && (
            <div className="mt-1 truncate font-mono text-[11px] text-text-muted">
              {issue.path ? `${issue.path}${issue.line ? `:${issue.line}` : ""}` : "No source location"}
            </div>
          )}
          <div className="mt-1 truncate text-[11px] text-text-muted">{issue.scannerId}</div>
        </div>
      </div>
    </button>
  );
}

function CodePane({ issue, file, repo, branch, fileIssues, targetLine, selectedIssueId, onSelectIssue }) {
  if (!issue) {
    return (
      <section className="flex items-center justify-center rounded-2xl border border-border bg-card shadow-card">
        <div className="text-center text-[13px] text-text-muted">Select an issue to inspect its source location.</div>
      </section>
    );
  }

  const githubUrl = issue.path && repo
    ? `https://github.com/${repo.owner}/${repo.name}/blob/${encodeURIComponent(branch)}/${issue.path
        .split("/")
        .map(encodeURIComponent)
        .join("/")}#L${issue.line || 1}`
    : null;
  const visibleIssues = fileIssues?.length ? fileIssues : [issue];
  const issueLineCount = new Set(visibleIssues.map((item) => item.line).filter(Boolean)).size;

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
      <div className="flex items-start justify-between gap-4 border-b border-border bg-chip-alt px-5 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] text-text-muted">
            <FileCode2 className="h-3.5 w-3.5" strokeWidth={2} />
            <span className="truncate font-mono">{issue.path || "Unmapped finding"}</span>
            {issue.line && <span className="font-mono">:{issue.line}</span>}
          </div>
          <h2 className="mt-1 line-clamp-2 text-[16px] font-bold text-text-primary">
            Full source file
          </h2>
          <p className="mt-1 text-[12px] text-text-muted">
            {visibleIssues.length} review comment{visibleIssues.length === 1 ? "" : "s"} across {issueLineCount || visibleIssues.length} highlighted line{(issueLineCount || visibleIssues.length) === 1 ? "" : "s"}.
          </p>
        </div>
        {githubUrl && (
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            View on GitHub
            <ExternalLink className="h-3 w-3" strokeWidth={2.2} />
          </a>
        )}
      </div>

      {!issue.path || !issue.line ? (
        <EvidenceOnly issue={issue} message="This finding does not include a file and line location." />
      ) : file?.state === "loading" || !file ? (
        <div className="flex min-h-[420px] items-center justify-center gap-2 text-[13px] text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2.2} />
          Loading source file from GitHub...
        </div>
      ) : file.state === "error" ? (
        <EvidenceOnly issue={issue} message={`The full source file could not be loaded from GitHub. ${file.error || ""}`.trim()} />
      ) : (
        <CodeContext
          text={file.text}
          targetLine={targetLine}
          issues={visibleIssues}
          selectedIssueId={selectedIssueId}
          onSelectIssue={onSelectIssue}
        />
      )}
    </section>
  );
}

function CodeContext({ text, targetLine, issues, selectedIssueId, onSelectIssue }) {
  const containerRef = useRef(null);
  const rows = (text || "").split(/\r?\n/).map((line, index) => ({
    lineNumber: index + 1,
    text: line,
  }));
  const issueMap = useMemo(() => {
    const map = new Map();
    issues.forEach((issue) => {
      if (!issue.line) return;
      const lineIssues = map.get(issue.line) ?? [];
      lineIssues.push(issue);
      map.set(issue.line, lineIssues);
    });
    for (const lineIssues of map.values()) {
      lineIssues.sort(compareIssues);
    }
    return map;
  }, [issues]);
  const firstIssueLine = issues.find((issue) => issue.line)?.line;
  const fallbackLine = rows[0]?.lineNumber ?? 1;
  const scrollLine = targetLine || firstIssueLine || fallbackLine;

  useEffect(() => {
    const target = containerRef.current?.querySelector("[data-target-line='true']");
    target?.scrollIntoView({ block: "center" });
  }, [scrollLine, text]);

  if (rows.length === 0) {
    return (
      <div className="flex min-h-[420px] items-center justify-center text-[13px] text-text-muted">
        No source lines are available for this finding.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="max-h-[650px] overflow-auto bg-white">
      <table className="w-full border-collapse font-mono text-[12px]">
        <tbody>
          {rows.map((row) => {
            const lineNumber = row.lineNumber;
            const rowIssues = issueMap.get(lineNumber) ?? [];
            const hasIssue = rowIssues.length > 0;
            const active = lineNumber === scrollLine;
            return (
              <Fragment key={lineNumber}>
                <tr
                  className={hasIssue ? "bg-yellow-50" : "bg-white"}
                  data-target-line={active ? "true" : undefined}
                >
                  <td className={`w-14 select-none border-r border-border px-3 py-1.5 text-right ${hasIssue ? "bg-yellow-100 font-semibold text-yellow-800" : "bg-chip-alt text-text-muted"}`}>
                    {lineNumber}
                  </td>
                  <td className={`whitespace-pre border-l-2 px-4 py-1.5 ${hasIssue ? "border-yellow-400 text-text-primary" : "border-transparent text-text-secondary"}`}>
                    {row.text || " "}
                  </td>
                </tr>
                {hasIssue && (
                  <tr>
                    <td className="border-r border-border bg-chip-alt" />
                    <td className="border-b border-border px-4 py-3">
                      <div className="relative space-y-2 pl-5 before:absolute before:left-1 before:top-0 before:h-full before:w-px before:bg-border">
                        {rowIssues.map((issue) => (
                          <IssueCallout
                            key={issue.id}
                            issue={issue}
                            selected={issue.id === selectedIssueId}
                            onSelect={onSelectIssue ? () => onSelectIssue(issue.id) : undefined}
                          />
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function IssueCallout({ issue, selected = false, onSelect }) {
  const cfg = SEV[issue.severity] ?? SEV.info;
  const Tag = onSelect ? "button" : "div";
  return (
    <Tag
      type={onSelect ? "button" : undefined}
      onClick={onSelect}
      className={`block w-full rounded-xl border ${cfg.border} ${cfg.bg} px-4 py-3 text-left font-sans shadow-sm transition-all ${
        selected ? "ring-2 ring-action-dark/20" : onSelect ? "hover:-translate-y-0.5 hover:shadow-card" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full border ${cfg.border} bg-white/60 px-2 py-0.5 text-[11px] font-semibold ${cfg.color}`}>
          {cfg.label}
        </span>
        {issue.confidence && (
          <span className="rounded-full border border-border bg-white/60 px-2 py-0.5 text-[11px] text-text-muted">
            {issue.confidence} confidence
          </span>
        )}
        <span className="text-[11px] text-text-muted">{issue.scannerId}</span>
      </div>
      <p className="mt-2 text-[13px] font-semibold text-text-primary">{issue.title}</p>
      <p className="mt-1 text-[12px] leading-relaxed text-text-secondary">{issue.description}</p>
      {issue.recommendation && (
        <p className="mt-2 text-[12px] leading-relaxed text-text-secondary">
          <span className="font-semibold text-text-primary">Next step: </span>
          {issue.recommendation}
        </p>
      )}
    </Tag>
  );
}

function EvidenceOnly({ issue, message }) {
  return (
    <div className="space-y-4 p-5">
      <div className="rounded-xl border border-border bg-chip-alt px-4 py-3 text-[13px] text-text-secondary">
        {message}
      </div>
      <IssueCallout issue={issue} />
      {issue.evidence.length > 0 && (
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">Evidence locations</div>
          {issue.evidence.map((item, index) => (
            <div key={index} className="rounded-xl border border-border bg-white px-4 py-3">
              <div className="font-mono text-[11px] text-text-muted">
                {item.path || "No file"}{item.line ? `:${item.line}` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function normalizeFinding(finding, index, isPlaceholder = false) {
  const evidence = Array.isArray(finding.evidence) ? finding.evidence.map(normalizeEvidence) : [];
  const directEvidence = finding.path ? [{
    path: finding.path,
    line: finding.line ?? null,
    lineEnd: finding.line ?? null,
    excerpt: finding.snippet ?? finding.excerpt ?? null,
  }] : [];
  const allEvidence = [...directEvidence, ...evidence];
  const primary = allEvidence.find((item) => item.path) ?? {};
  const id = finding.id || `${finding.title || "finding"}-${index}`;
  return {
    id,
    title: finding.title || "Untitled finding",
    description: finding.description || finding.finding || "",
    severity: SEV[finding.severity] ? finding.severity : "info",
    confidence: finding.confidence || null,
    scannerId: finding.scanner_id || finding.scannerId || finding.category || "repo_scanner",
    recommendation: finding.recommendation || "",
    path: primary.path || null,
    line: primary.line || null,
    lineEnd: primary.lineEnd || primary.line || null,
    evidence: allEvidence,
  };
}

function groupIssuesByFile(issues) {
  const groups = new Map();
  issues
    .filter((issue) => issue.path && issue.line)
    .sort(compareIssues)
    .forEach((issue) => {
      const group = groups.get(issue.path) ?? { path: issue.path, issues: [], lineCount: 0 };
      group.issues.push(issue);
      groups.set(issue.path, group);
    });

  return Array.from(groups.values()).map((group) => ({
    ...group,
    lineCount: new Set(group.issues.map((issue) => issue.line)).size,
  }));
}

function compareIssues(a, b) {
  const severityDelta = SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity);
  if (severityDelta !== 0) return severityDelta;
  if ((a.path || "") !== (b.path || "")) return (a.path || "").localeCompare(b.path || "");
  return (a.line || 0) - (b.line || 0);
}

function normalizeEvidence(evidence) {
  const location = evidence.location || {};
  return {
    path: location.path || evidence.file || evidence.path || null,
    line: location.line_start || evidence.line_start || evidence.line || null,
    lineEnd: location.line_end || evidence.line_end || evidence.line || null,
    excerpt: evidence.excerpt || evidence.snippet || evidence.text || evidence.description || null,
  };
}

function parseRepo(url = "") {
  const match = url.trim().match(/github\.com[:/]([^/]+)\/([^/?#]+)/i);
  if (!match) return null;
  return {
    owner: match[1],
    name: match[2].replace(/\.git$/, ""),
  };
}
