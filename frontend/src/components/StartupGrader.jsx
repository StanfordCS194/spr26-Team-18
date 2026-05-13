import { useEffect, useMemo, useRef, useState } from "react";
import {
  Sparkles,
  RefreshCw,
  Upload,
  Loader2,
  FileText,
  ChevronDown,
  HelpCircle,
  Scale,
  ArrowRight,
} from "lucide-react";
import {
  AXES,
  AXIS_LABELS,
  AXIS_BLURBS,
  RULES,
  scoreFeatures,
  letterGrade,
  gradeColor,
} from "./startupRubric";
import {
  extractGithub,
  extractPRD,
  extractSpreadsheet,
  analyzePRD,
  analyzeCSV,
} from "./startupExtractors";
import StartupRadar from "./StartupRadar";

const ZERO_SCORES = AXES.reduce((o, a) => ({ ...o, [a]: 0 }), {});

// Short labels for the radar — full names are too long to render cleanly.
const RADAR_LABELS = {
  engineering: "Eng",
  legal: "Legal",
  financial: "Finance",
  compliance: "Compliance",
  product: "Product",
};

// Which axes each input contributes to. Used for empty-state coaching.
const INPUT_AXIS_MAP = {
  github: ["engineering", "legal"],
  prd: ["legal", "compliance", "product"],
  spreadsheet: ["financial"],
};

const LAST_GRADE_KEY = "startupGrader.lastGrade.v1";
export const STARTUP_RECOMMENDATIONS_KEY = "startupGrader.latestRecommendations.v1";
export const COMPANY_CONTEXT_KEY = "startupGrader.companyContext.v1";

function loadLastGrade() {
  try {
    const raw = localStorage.getItem(LAST_GRADE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.grade || !parsed?.timestamp) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveLastGrade(snapshot) {
  try {
    localStorage.setItem(LAST_GRADE_KEY, JSON.stringify(snapshot));
  } catch {
    // ignore quota / private mode failures — feature is best-effort
  }
}

function saveRecommendationsSnapshot(snapshot) {
  try {
    localStorage.setItem(STARTUP_RECOMMENDATIONS_KEY, JSON.stringify(snapshot));
    window.dispatchEvent(
      new CustomEvent("startup-recommendations-updated", { detail: snapshot })
    );
  } catch {
    // ignore quota / private mode failures — feature is best-effort
  }
}

function saveCompanyContext(name, features) {
  try {
    const parts = [name];
    if (features?.github?.description) parts.push(features.github.description);
    if (features?.github?.language) parts.push(`Primary language: ${features.github.language}`);
    if (features?.prd?.filename) {
      parts.push(`Product: ${features.prd.filename.replace(/\.(md|txt|pdf)$/i, "")}`);
    }
    localStorage.setItem(
      COMPANY_CONTEXT_KEY,
      JSON.stringify({ name, description: parts.join(". "), timestamp: Date.now() })
    );
  } catch {}
}

function timeAgo(ts) {
  const s = Math.max(1, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// Count the rules per axis once at module load — drives empty-state coaching.
const RULE_COUNT_BY_AXIS = AXES.reduce((o, a) => {
  o[a] = RULES.filter((r) => r.axis === a).length;
  return o;
}, {});

function rulesUnlockedBy(input) {
  const axes = INPUT_AXIS_MAP[input] || [];
  return axes.reduce((s, a) => s + RULE_COUNT_BY_AXIS[a], 0);
}

export default function StartupGrader({ onRecommendationsUpdated }) {
  // Inputs
  const [githubUrl, setGithubUrl] = useState("");
  const [prdFile, setPrdFile] = useState(null);
  const [sheetFile, setSheetFile] = useState(null);

  // State machine: idle | scanning | scoring | revealed
  const [step, setStep] = useState("idle");
  const [error, setError] = useState(null);
  const [working, setWorking] = useState(false);
  const [scanLog, setScanLog] = useState([]);

  // Result
  const [result, setResult] = useState(null);
  const [animatedScores, setAnimatedScores] = useState(ZERO_SCORES);
  const [revealedGrade, setRevealedGrade] = useState(null);
  const [drilldownAxis, setDrilldownAxis] = useState(null);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [lastGrade, setLastGrade] = useState(() => loadLastGrade());
  // verdict: { state: 'idle'|'loading'|'ok'|'unavailable'|'error', text, model, error }
  const [verdict, setVerdict] = useState({ state: "idle" });
  const rafRef = useRef(null);

  function reset() {
    cancelAnimationFrame(rafRef.current);
    setStep("idle");
    setResult(null);
    setAnimatedScores(ZERO_SCORES);
    setRevealedGrade(null);
    setDrilldownAxis(null);
    setError(null);
    setScanLog([]);
    setVerdict({ state: "idle" });
  }

  async function fetchVerdict(scored, name) {
    setVerdict({ state: "loading" });
    try {
      const payload = {
        name,
        grade: scored.grade,
        composite: scored.composite,
        axes: AXES.reduce((o, a) => {
          const ax = scored.axes[a];
          o[a] = {
            score: ax.score,
            results: ax.results.map((r) => ({
              title: r.title,
              passed: r.passed,
              status: r.status,
              observed: r.observed,
              fix: r.fix,
              weight: r.weight,
            })),
          };
          return o;
        }, {}),
        top_actions: scored.topActions.map((a) => ({
          title: a.title,
          fix: a.fix,
          axis: a.axis,
          weight: a.weight,
          dollarImpact: a.dollarImpact,
        })),
      };
      const r = await fetch("/api/startup/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (r.status === 503) {
        setVerdict({ state: "unavailable" });
        return;
      }
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(detail.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setVerdict({ state: "ok", text: data.verdict, model: data.model });
    } catch (e) {
      setVerdict({ state: "error", error: e.message || String(e) });
    }
  }

  function pushLog(line) {
    setScanLog((prev) => [...prev, line]);
  }

  async function runGrade(opts = {}) {
    if (working) return;
    const { presetFeatures, presetName } = opts;
    setWorking(true);
    setError(null);
    setStep("scanning");
    setScanLog([]);

    try {
      let features;
      if (presetFeatures) {
        features = presetFeatures;
        pushLog(`Loading preset · ${presetName}`);
        await wait(280);
        pushLog("(preset features are pre-computed — no live API call)");
        await wait(280);
      } else {
        features = { github: null, prd: null, spreadsheet: null };
        if (githubUrl.trim()) {
          pushLog(`Calling api.github.com · ${githubUrl.trim()}`);
          features.github = await extractGithub(githubUrl);
          pushLog(
            `✓ ${features.github.fullName} · ${features.github.filenames.length} top-level files · ${features.github.scannedFileCount || 0} code files scanned`
          );
          if (features.github.complianceFindings?.length) {
            pushLog(
              `✓ Repo compliance scan · ${features.github.highComplianceFindingCount || 0} high · ${features.github.mediumComplianceFindingCount || 0} medium findings`
            );
          }
        }
        if (prdFile) {
          pushLog(`Reading PRD · ${prdFile.name}`);
          features.prd = await extractPRD(prdFile);
          pushLog(`✓ PRD parsed · ${features.prd.length || 0} chars`);
        }
        if (sheetFile) {
          pushLog(`Parsing CSV · ${sheetFile.name}`);
          features.spreadsheet = await extractSpreadsheet(sheetFile);
          pushLog(`✓ ${features.spreadsheet.rowCount} rows · runway ${features.spreadsheet.runway ?? "?"}mo`);
        }
        if (!features.github && !features.prd && !features.spreadsheet) {
          throw new Error("Drop in at least one input — GitHub URL, PRD, or spreadsheet.");
        }
      }

      pushLog(`Running rubric · ${RULES.length} rules across 5 axes`);
      await wait(380);
      const scored = scoreFeatures(features);
      const name = presetName || nameFromInputs(features);
      saveCompanyContext(name, features);
      setResult({ features, ...scored, name });
      pushLog(`✓ Composite ${scored.composite}/100 · grade ${scored.grade}`);
      await wait(400);

      setStep("scoring");
      animateInto(scored, name);
    } catch (e) {
      setError(e.message || String(e));
      setStep("idle");
    } finally {
      setWorking(false);
    }
  }

  function animateInto(scored, name) {
    const target = AXES.reduce((o, a) => ({ ...o, [a]: scored.axes[a].score ?? 0 }), {});
    setAnimatedScores(ZERO_SCORES);
    setRevealedGrade(null);
    const start = performance.now();
    const dur = 1500;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = {};
      for (const a of AXES) next[a] = Math.round(target[a] * eased);
      setAnimatedScores(next);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setRevealedGrade(scored.grade);
        setStep("revealed");
        const snap = {
          name,
          composite: scored.composite,
          grade: scored.grade,
          axes: AXES.reduce((o, a) => ({ ...o, [a]: scored.axes[a].score }), {}),
          evaluatedAxes: scored.evaluatedAxes,
          timestamp: Date.now(),
        };
        const recommendationsSnap = {
          ...snap,
          axisResults: AXES.reduce((o, a) => {
            o[a] = {
              score: scored.axes[a].score,
              failed: scored.axes[a].results.filter((r) => r.status === "failed"),
              skipped: scored.axes[a].results.filter((r) => r.status === "skipped").length,
              passed: scored.axes[a].results.filter((r) => r.status === "passed").length,
              total: scored.axes[a].results.length,
              evaluated: scored.axes[a].evaluatedCount,
            };
            return o;
          }, {}),
          topActions: scored.topActions,
        };
        saveLastGrade(snap);
        saveRecommendationsSnapshot(recommendationsSnap);
        setLastGrade(snap);
        onRecommendationsUpdated?.(recommendationsSnap);
        // Fire-and-forget LLM verdict — non-blocking, panel renders its own state.
        fetchVerdict(scored, name);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
  }

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  // Demo deep link: ?demo=good|ok|bad auto-runs the matching preset on load.
  // Also accepts ?demo=clear to wipe the persisted last-grade banner.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const demo = params.get("demo");
    if (!demo) return;
    if (demo === "clear") {
      try {
        localStorage.removeItem(LAST_GRADE_KEY);
        localStorage.removeItem(STARTUP_RECOMMENDATIONS_KEY);
      } catch {}
      setLastGrade(null);
      return;
    }
    const presets = buildPresets();
    const target = presets.find((p) => p.key === demo.toLowerCase());
    if (target) {
      runGrade({ presetFeatures: target.features, presetName: target.name });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keyboard: cmd/ctrl+enter triggers grade from any focus, esc resets.
  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (step === "idle" && !working) {
          e.preventDefault();
          runGrade();
        }
      } else if (e.key === "Escape") {
        if (step === "revealed" || step === "scoring") {
          e.preventDefault();
          reset();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, working, githubUrl, prdFile, sheetFile]);

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-text-secondary">
          <Sparkles className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">
            Founder Copilot · Startup Health Grade
          </span>
        </div>
        <div className="flex items-end justify-between gap-4">
          <h1 className="text-[32px] font-bold tracking-tight">
            Your back office, graded in 30 seconds.
          </h1>
          <button
            onClick={() => setMethodologyOpen((v) => !v)}
            className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            <HelpCircle className="h-3.5 w-3.5" strokeWidth={2.4} />
            How is this scored?
            <ChevronDown
              className={"h-3 w-3 transition-transform " + (methodologyOpen ? "rotate-180" : "")}
              strokeWidth={2.4}
            />
          </button>
        </div>
        <p className="max-w-[680px] text-[14px] leading-relaxed text-text-secondary">
          Drop in your <span className="font-medium text-text-primary">GitHub repo</span>, a{" "}
          <span className="font-medium text-text-primary">PRD</span>, and a{" "}
          <span className="font-medium text-text-primary">finance spreadsheet</span>. We score 5
          axes against {RULES.length} rules and tell you the 5 highest-leverage things to fix this week.
        </p>
        {methodologyOpen && <Methodology />}
      </header>

      {step === "idle" && (
        <>
          {lastGrade && (
            <LastGradeBanner snapshot={lastGrade} onDismiss={() => setLastGrade(null)} />
          )}
          <InputPanel
            githubUrl={githubUrl}
            setGithubUrl={setGithubUrl}
            prdFile={prdFile}
            setPrdFile={setPrdFile}
            sheetFile={sheetFile}
            setSheetFile={setSheetFile}
            onSubmit={() => runGrade()}
            working={working}
            error={error}
          />
          <PresetRow
            disabled={working}
            onPick={(p) => runGrade({ presetFeatures: p.features, presetName: p.name })}
          />
        </>
      )}

      {step === "scanning" && <ScanStage log={scanLog} />}

      {(step === "scoring" || step === "revealed") && result && (
        <RevealStage
          result={result}
          animatedScores={animatedScores}
          revealedGrade={revealedGrade}
          step={step}
          drilldownAxis={drilldownAxis}
          setDrilldownAxis={setDrilldownAxis}
          onReset={reset}
          verdict={verdict}
          onRetryVerdict={() => fetchVerdict(result, result.name)}
        />
      )}

      <Footer />
    </section>
  );
}

function LegalSavingsTeaser({ name }) {
  return (
    <div className="animate-slide-up overflow-hidden rounded-3xl border border-accent-gold/30 bg-accent-gold/10 px-6 py-5 shadow-card">
      <div className="flex items-center justify-between gap-6">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-gold/20">
            <Scale className="h-5 w-5 text-accent-gold" strokeWidth={2} />
          </div>
          <div>
            <div className="text-[13px] font-semibold text-text-primary">
              See your legal cost savings
            </div>
            <div className="mt-0.5 text-[12px] leading-relaxed text-text-secondary">
              Your startup profile for <span className="font-medium text-text-primary">{name}</span> has
              been saved. Jump to Legal to see what a compliance attorney would charge — and what
              Legi-Bill covers automatically.
            </div>
          </div>
        </div>
        <button
          onClick={() => { window.location.hash = "#legal"; }}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-action-dark px-4 py-2 text-[13px] font-semibold text-text-invert transition-opacity hover:opacity-90"
        >
          See savings
          <ArrowRight className="h-3.5 w-3.5" strokeWidth={2.4} />
        </button>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <footer className="pt-6 text-[11px] leading-relaxed text-text-muted">
      v0.1 prototype · {RULES.length} deterministic rules · GitHub extraction is a live API call ·
      PRD + CSV parsed deterministically · LLM verdict synthesized server-side from the
      structured grade (not the raw inputs).
    </footer>
  );
}

function nameFromInputs(features) {
  if (features.github?.fullName) return features.github.fullName;
  if (features.prd?.filename) return features.prd.filename.replace(/\.(md|txt|markdown|pdf)$/i, "");
  if (features.spreadsheet?.filename) return features.spreadsheet.filename;
  return "Your startup";
}

function wait(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ──────────────────────────── Inputs ────────────────────────────

function InputPanel({
  githubUrl,
  setGithubUrl,
  prdFile,
  setPrdFile,
  sheetFile,
  setSheetFile,
  onSubmit,
  working,
  error,
}) {
  const prdRef = useRef(null);
  const sheetRef = useRef(null);
  const ready = githubUrl.trim() || prdFile || sheetFile;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="space-y-4"
    >
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <InputCard
          Icon={FileText}
          title="GitHub repo"
          subtitle="Live API call — no auth needed for public repos"
          unlocks={`unlocks ${rulesUnlockedBy("github")} rules in Engineering + Legal`}
          filled={!!githubUrl.trim()}
        >
          <input
            type="text"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            placeholder="github.com/owner/repo"
            className="w-full rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
          />
          <div className="mt-2 text-[11px] text-text-muted">
            Pulls license, contributors, CI, secrets, recency.
          </div>
        </InputCard>

        <InputCard
          Icon={FileText}
          title="PRD"
          subtitle=".pdf, .md, or .txt"
          unlocks={`unlocks ${rulesUnlockedBy("prd")} rules in Legal + Compliance + Product`}
          filled={!!prdFile}
        >
          <FileButton
            inputRef={prdRef}
            file={prdFile}
            accept=".pdf,.md,.txt,.markdown,application/pdf,text/plain,text/markdown"
            onChange={(f) => setPrdFile(f)}
            placeholder="Drop PRD"
          />
          <div className="mt-2 text-[11px] text-text-muted">
            Scans for problem, users, metrics, GDPR/CCPA, COPPA, ToS.
          </div>
        </InputCard>

        <InputCard
          Icon={FileText}
          title="Finance spreadsheet"
          subtitle=".csv export from Mercury / Stripe / Brex"
          unlocks={`unlocks ${rulesUnlockedBy("spreadsheet")} rules in Financial`}
          filled={!!sheetFile}
        >
          <FileButton
            inputRef={sheetRef}
            file={sheetFile}
            accept=".csv"
            onChange={(f) => setSheetFile(f)}
            placeholder="Drop CSV"
          />
          <div className="mt-2 text-[11px] text-text-muted">
            Computes runway, burn, revenue, top expense.
          </div>
        </InputCard>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-[12px] text-text-muted">
          {ready ? "Ready to grade." : "Add at least one input to continue."}
        </div>
        <button
          type="submit"
          disabled={working || !ready}
          className="flex items-center gap-2 rounded-full bg-action-dark px-5 py-2.5 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90 disabled:opacity-40"
        >
          {working ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" strokeWidth={2.4} />
          )}
          {working ? "Grading…" : "Grade my startup"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          <span className="mr-1.5 font-semibold">!</span> {error}
        </div>
      )}
    </form>
  );
}

function InputCard({ Icon, title, subtitle, children, unlocks, filled }) {
  return (
    <div
      className={
        "rounded-2xl border bg-card p-5 shadow-card transition-colors " +
        (filled ? "border-action-dark/30" : "border-border")
      }
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-chip-alt">
            <Icon className="h-4 w-4 text-text-primary" strokeWidth={2.2} />
          </div>
          <div>
            <div className="text-[14px] font-semibold tracking-tight text-text-primary">{title}</div>
            <div className="text-[11px] text-text-muted">{subtitle}</div>
          </div>
        </div>
        {filled ? (
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
            ready
          </span>
        ) : (
          unlocks && (
            <span className="text-right text-[10px] leading-tight text-accent-gold">
              → {unlocks}
            </span>
          )
        )}
      </div>
      {children}
    </div>
  );
}

function LastGradeBanner({ snapshot, onDismiss }) {
  const color = gradeColor(snapshot.grade);
  return (
    <div className="flex items-center justify-between rounded-2xl border border-border bg-card px-5 py-3 shadow-card">
      <div className="flex items-center gap-3">
        <div
          className={
            "flex h-10 w-10 items-center justify-center rounded-full border-2 border-accent-gold bg-card font-bold " +
            color
          }
        >
          {snapshot.grade}
        </div>
        <div>
          <div className="text-[13px] font-semibold text-text-primary">
            Last graded · {snapshot.name || "your startup"}
          </div>
          <div className="text-[11px] text-text-muted">
            {snapshot.composite}/100 · {(snapshot.evaluatedAxes || []).length || AXES.length}/{AXES.length} axes evaluated · {timeAgo(snapshot.timestamp)} · saved locally
          </div>
        </div>
      </div>
      <button
        onClick={onDismiss}
        className="text-[11px] text-text-muted hover:text-text-primary"
      >
        dismiss
      </button>
    </div>
  );
}

function FileButton({ inputRef, file, accept, onChange, placeholder }) {
  return (
    <div className="flex items-center gap-2">
      <label className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-chip-alt px-4 py-2.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-action-dark hover:text-text-primary">
        <Upload className="h-4 w-4" strokeWidth={2.4} />
        <span>{file ? truncate(file.name, 22) : placeholder}</span>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={(e) => onChange(e.target.files?.[0] || null)}
          className="hidden"
        />
      </label>
      {file && (
        <button
          type="button"
          onClick={() => {
            onChange(null);
            if (inputRef.current) inputRef.current.value = "";
          }}
          className="text-[11px] text-text-muted hover:text-text-primary"
        >
          clear
        </button>
      )}
    </div>
  );
}

function truncate(s, n) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

// ──────────────────────────── Presets ────────────────────────────

const PRESET_PRD_GOOD = `# Founder Copilot — PRD

## Problem
Today, pre-seed founders waste ~15 hrs/week on legal, financial, and admin tasks
they don't understand. Currently they either ignore the work or hire too early.

## Target user
2-3 person YC pre-seed founder, US Delaware C-corp, building SaaS or AI.

## Solution
A copilot that ingests GitHub, PRD, and Mercury CSV, then grades the startup
across 5 dimensions and surfaces the 5 highest-leverage actions weekly.

## Success metrics
North star: weekly active founders. Input metrics: time-to-first-grade,
% of recommendations acted on within 7 days, retention week 4.

## Scope
Out of scope: tax filing, payroll, equity issuance.
Non-goals: replacing a real lawyer for term sheet negotiation.

## Timeline
Q1 2026: Internal alpha. Q2 2026: 10 design partners.

## Compliance
US-only at launch (defer GDPR). CCPA-compliant from day 1 since we'll have CA users.
We will publish a Privacy Policy and Terms of Service. Authentication via Google OAuth.
PII handling: encrypted at rest, deleted on user request (data retention: 90 days post-cancel).
SOC2 Type 1 targeted by Q4 2026.

## Competition
Carta does cap tables. Pilot does books. Stripe Atlas does formation. None do all three
with active recommendations. Status quo is a Notion doc + 3 lawyers.

## Entity
Founder Copilot, Inc. (Delaware C-corp, formed via Clerky).
`;

const PRESET_PRD_BAD = `# Cool app idea

We're building an AI thing for kids that's super viral. It's like ChatGPT but for
TikTok. Users will love it. We'll make money somehow.
`;

const PRESET_CSV_GOOD = `date,amount,category,balance
2025-09-01,-12500,payroll,400000
2025-09-15,8000,revenue,408000
2025-10-01,-13200,payroll,394800
2025-10-15,9500,revenue,404300
2025-11-01,-13900,payroll,390400
2025-11-15,11200,revenue,401600
2025-12-01,-14500,payroll,387100
2025-12-15,12800,revenue,399900
2026-01-01,-15100,payroll,384800
2026-01-15,14500,revenue,399300
2026-02-01,-15800,payroll,383500
2026-02-15,16200,revenue,399700
`;

const PRESET_CSV_BAD = `transaction,price
"coffee",4.50
"uber",18.00
"slack",12.00
`;

function buildPresets() {
  return [
    {
      key: "good",
      name: "Founder Copilot, Inc. (well-run)",
      blurb: "Tight repo · complete PRD · 13mo runway",
      features: {
        github: {
          fullName: "founder-copilot/copilot",
          owner: "founder-copilot",
          repo: "copilot",
          description: "Founder copilot for legal/finance/ops",
          license: "Apache-2.0",
          language: "TypeScript",
          stars: 142,
          pushedAt: new Date(Date.now() - 2 * 86400000).toISOString(),
          daysSincePush: 2,
          filenames: ["README.md", "LICENSE", "package.json", "tests", ".gitignore", ".github"],
          readmeText: "x".repeat(2400),
          readmeLength: 2400,
          hasReadme: true,
          hasLicense: true,
          hasGitignore: true,
          hasPackageManifest: true,
          hasTests: true,
          hasEnvFile: false,
          hasCI: true,
          contributorCount: 4,
        },
        prd: analyzePRD(PRESET_PRD_GOOD, "PRD.md"),
        spreadsheet: analyzeCSV(PRESET_CSV_GOOD, "mercury_export.csv"),
      },
    },
    {
      key: "ok",
      name: "Bolt SaaS (mid)",
      blurb: "Decent repo · thin PRD · 5mo runway",
      features: {
        github: {
          fullName: "boltsaas/api",
          owner: "boltsaas",
          repo: "api",
          description: "B2B SaaS API",
          license: "MIT",
          language: "Python",
          stars: 12,
          pushedAt: new Date(Date.now() - 18 * 86400000).toISOString(),
          daysSincePush: 18,
          filenames: ["README.md", "LICENSE", "requirements.txt", ".gitignore"],
          readmeText: "x".repeat(450),
          readmeLength: 450,
          hasReadme: true,
          hasLicense: true,
          hasGitignore: true,
          hasPackageManifest: true,
          hasTests: false,
          hasEnvFile: false,
          hasCI: false,
          contributorCount: 2,
        },
        prd: analyzePRD(
          `# Bolt SaaS PRD\n\nProblem: companies need an API. Solution: we build one.\nTarget user: B2B teams. We'll add auth.\n`,
          "PRD.md"
        ),
        spreadsheet: analyzeCSV(
          `date,amount,balance\n2025-12-01,-22000,110000\n2026-01-01,-23000,87000\n2026-02-01,-24000,63000\n`,
          "books.csv"
        ),
      },
    },
    {
      key: "bad",
      name: "Friction Labs (vibe-coded)",
      blurb: "AGPL · no tests · runway unknown · COPPA risk",
      features: {
        github: {
          fullName: "friction-labs/kids-ai",
          owner: "friction-labs",
          repo: "kids-ai",
          description: "Viral AI for kids",
          license: "AGPL-3.0",
          language: "JavaScript",
          stars: 3,
          pushedAt: new Date(Date.now() - 87 * 86400000).toISOString(),
          daysSincePush: 87,
          filenames: ["index.js", ".env", "package.json"],
          readmeText: "TODO",
          readmeLength: 4,
          hasReadme: false,
          hasLicense: false,
          hasGitignore: false,
          hasPackageManifest: true,
          hasTests: false,
          hasEnvFile: true,
          hasCI: false,
          contributorCount: 1,
        },
        prd: analyzePRD(PRESET_PRD_BAD, "idea.md"),
        spreadsheet: analyzeCSV(PRESET_CSV_BAD, "expenses.csv"),
      },
    },
  ];
}

function PresetRow({ onPick, disabled }) {
  const [presets] = useState(() => buildPresets());
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            Or try a demo startup
          </div>
          <h3 className="mt-1 text-[16px] font-bold tracking-tight">No upload required</h3>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {presets.map((p) => (
          <button
            key={p.key}
            disabled={disabled}
            onClick={() => onPick(p)}
            className="group flex flex-col items-start gap-1 rounded-2xl border border-border bg-chip-alt px-4 py-4 text-left transition-all hover:-translate-y-0.5 hover:border-action-dark hover:bg-card hover:shadow-card-hover disabled:opacity-50"
          >
            <span className="text-[14px] font-semibold leading-snug text-text-primary">{p.name}</span>
            <span className="text-[12px] text-text-secondary">{p.blurb}</span>
            <span className="mt-2 text-[12px] text-text-muted group-hover:text-text-primary">grade →</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ──────────────────────────── Scan stage ────────────────────────────

function ScanStage({ log }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [log]);

  return (
    <div className="rounded-3xl border border-border bg-card p-8 shadow-card">
      <div className="mb-4 flex items-center gap-2 text-[12px] uppercase tracking-[0.18em] text-text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-accent-gold" />
        Scanning inputs
      </div>
      <div
        ref={ref}
        className="max-h-64 overflow-y-auto rounded-xl bg-chip-alt p-4 font-mono text-[12px] leading-relaxed text-text-secondary"
      >
        {log.map((line, i) => (
          <div key={i} className={line.startsWith("✓") ? "text-emerald-700" : ""}>
            <span className="mr-2 text-text-muted">[{String(i + 1).padStart(2, "0")}]</span>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

// ──────────────────────────── Reveal ────────────────────────────

function RevealStage({
  result,
  animatedScores,
  revealedGrade,
  step,
  drilldownAxis,
  setDrilldownAxis,
  onReset,
  verdict,
  onRetryVerdict,
}) {
  const showGrade = step === "revealed";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            Startup Health Grade
          </div>
          <div className="text-[22px] font-bold tracking-tight">{result.name}</div>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card transition-all hover:text-text-primary"
        >
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={2.4} />
          Try another
        </button>
      </div>

      {showGrade && verdict && (
        <VerdictPanel verdict={verdict} onRetry={onRetryVerdict} />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,360px]">
        <div className="relative rounded-3xl border border-border bg-card p-8 shadow-card">
          {showGrade && (
            <div className="absolute right-6 top-6 z-10">
              <GradeStamp grade={revealedGrade} composite={result.composite} />
            </div>
          )}

          <div className="mb-4 mt-1">
            <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">5 axes</div>
            <div className="text-[16px] font-semibold tracking-tight">
              Available-input grade {result.composite}/100
            </div>
            <div className="mt-1 text-[11px] text-text-muted">
              {result.evaluatedAxes.length}/{AXES.length} axes evaluated · missing-input checks skipped
            </div>
          </div>

          <div className="mb-4 flex items-center justify-center">
            <StartupRadar
              axes={AXES}
              scores={animatedScores}
              labels={RADAR_LABELS}
              animate={showGrade}
            />
          </div>

          <div className="grid grid-cols-1 gap-2">
            {AXES.map((axis) => (
              <AxisBar
                key={axis}
                axis={axis}
                score={animatedScores[axis]}
                clickable={showGrade}
                active={drilldownAxis === axis}
                onClick={() => setDrilldownAxis((cur) => (cur === axis ? null : axis))}
              />
            ))}
          </div>
          {showGrade && !drilldownAxis && (
            <div className="mt-3 text-center text-[11px] text-text-muted">
              Tap any axis to see the rules behind the score.
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
            <Sparkles className="h-3 w-3 text-accent-gold" strokeWidth={2.4} />
            Top 5 actions to raise your grade
          </div>
          <ul className="space-y-3">
            {result.topActions.length === 0 && (
              <li className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-[13px] text-emerald-800">
                ✓ No failed checks in the evaluated inputs.
              </li>
            )}
            {result.topActions.map((a, i) => (
              <ActionRow key={a.id} action={a} index={i} visible={showGrade} />
            ))}
          </ul>
        </div>
      </div>

      {showGrade && <LegalSavingsTeaser name={result.name} />}

      {showGrade && drilldownAxis && (
        <AxisDrilldown
          axis={drilldownAxis}
          axisData={result.axes[drilldownAxis]}
          onClose={() => setDrilldownAxis(null)}
        />
      )}
    </div>
  );
}

function VerdictPanel({ verdict, onRetry }) {
  const baseChip = "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide";

  return (
    <div className="rounded-2xl border border-accent-gold/40 bg-card p-5 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            AI verdict
          </span>
          <span className={baseChip + " bg-accent-gold/15 text-accent-gold"}>
            LLM-generated
          </span>
        </div>
        {verdict.model && (
          <span className="font-mono text-[10px] text-text-muted">{verdict.model}</span>
        )}
      </div>

      {verdict.state === "loading" && (
        <div className="flex items-center gap-2 text-[13px] text-text-secondary">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Synthesizing verdict from the
          structured grade…
        </div>
      )}

      {verdict.state === "ok" && (
        <p className="text-[14px] leading-relaxed text-text-primary">{verdict.text}</p>
      )}

      {verdict.state === "unavailable" && (
        <div className="text-[13px] text-text-secondary">
          Verdict skipped — backend has no <code className="font-mono">OPENAI_API_KEY</code>{" "}
          configured. The deterministic grade above is unaffected.
        </div>
      )}

      {verdict.state === "error" && (
        <div className="space-y-2">
          <div className="text-[13px] text-red-700">Verdict failed: {verdict.error}</div>
          <button
            onClick={onRetry}
            className="rounded-full border border-border bg-card px-3 py-1 text-[12px] font-medium text-text-secondary hover:text-text-primary"
          >
            retry
          </button>
        </div>
      )}

      {verdict.state === "ok" && (
        <div className="mt-2 text-[10px] text-text-muted">
          The LLM only synthesizes — the grade above is computed deterministically by the
          rubric, never by the model.
        </div>
      )}
    </div>
  );
}

function GradeStamp({ grade, composite }) {
  const color = gradeColor(grade);
  return (
    <div className="flex flex-col items-end gap-1">
      <div
        className={
          "flex items-center justify-center rounded-full border-4 border-accent-gold bg-card font-bold shadow-card-hover " +
          color
        }
        style={{ height: 86, width: 86, fontSize: 34 }}
      >
        {grade}
      </div>
      <div className="text-[11px] font-mono text-text-muted">{composite}/100</div>
    </div>
  );
}

function riskTone(score) {
  if (score == null) return { num: "text-text-muted", bar: "bg-border" };
  if (score < 40) return { num: "text-red-600", bar: "bg-red-500" };
  if (score < 65) return { num: "text-orange-500", bar: "bg-orange-400" };
  if (score < 85) return { num: "text-action-dark", bar: "bg-action-dark" };
  return { num: "text-emerald-600", bar: "bg-emerald-500" };
}

function AxisBar({ axis, score, clickable, active, onClick }) {
  const isSkipped = score == null;
  const pct = isSkipped ? 0 : Math.max(0, Math.min(100, score));
  const tone = riskTone(score);
  const Wrapper = clickable ? "button" : "div";
  return (
    <Wrapper
      type={clickable ? "button" : undefined}
      onClick={clickable ? onClick : undefined}
      className={
        "flex items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors " +
        (clickable ? "cursor-pointer hover:bg-chip-alt " : "") +
        (active ? "bg-chip-alt" : "")
      }
    >
      <div className="w-[160px] text-[13px] capitalize text-text-secondary">
        {AXIS_LABELS[axis]}
      </div>
      <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-chip-alt">
        <div
          className={"absolute inset-y-0 left-0 rounded-full " + tone.bar}
          style={{ width: `${pct}%`, transition: "width 0.06s linear" }}
        />
      </div>
      <div className={"w-10 text-right font-mono text-[14px] tabular-nums " + tone.num}>
        {isSkipped ? "N/A" : pct}
      </div>
    </Wrapper>
  );
}

function ActionRow({ action, index, visible }) {
  return (
    <li
      className="overflow-hidden rounded-xl border border-border-muted bg-chip-alt p-3 transition-all"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
        transition: `all 0.4s cubic-bezier(0.16,1,0.3,1) ${0.15 + index * 0.1}s`,
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="text-[13px] font-semibold text-text-primary">{action.title}</div>
          <div className="mt-1 text-[12px] leading-relaxed text-text-secondary">{action.fix}</div>
          {action.locations?.length > 0 && (
            <div className="mt-2 space-y-1">
              {action.locations.slice(0, 2).map((loc) => (
                <div
                  key={`${loc.path}:${loc.line}:${loc.title}`}
                  className="rounded-lg border border-border-muted bg-card px-2 py-1.5 font-mono text-[10px] leading-relaxed text-text-secondary"
                >
                  <div className="font-semibold text-text-primary">
                    {loc.path}:{loc.line}
                  </div>
                  <div className="truncate">{loc.snippet}</div>
                </div>
              ))}
            </div>
          )}
          <div className="mt-1.5 flex items-center gap-2 text-[11px]">
            <span className="rounded-full bg-card px-2 py-0.5 text-text-secondary">
              {AXIS_LABELS[action.axis]}
            </span>
            {action.dollarImpact > 0 && (
              <span className="rounded-full bg-red-50 px-2 py-0.5 text-red-700">
                up to ${action.dollarImpact.toLocaleString()} downside
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function AxisDrilldown({ axis, axisData, onClose }) {
  return (
    <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">Drilldown</div>
          <h3 className="mt-1 text-[18px] font-bold tracking-tight">{AXIS_LABELS[axis]}</h3>
          <div className="mt-1 text-[13px] text-text-secondary">{AXIS_BLURBS[axis]}</div>
        </div>
        <button
          onClick={onClose}
          className="text-[12px] text-text-muted hover:text-text-primary"
        >
          close
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {axisData.results.map((r) => (
          <div
            key={r.id}
            className={
              "flex items-start gap-3 rounded-xl border px-3 py-2.5 text-[13px] " +
              (r.status === "passed"
                ? "border-emerald-100 bg-emerald-50/40"
                : r.status === "skipped"
                  ? "border-border-muted bg-chip-alt"
                  : "border-red-100 bg-red-50/40")
            }
          >
            <span
              className={
                "mt-0.5 inline-flex h-4 w-4 flex-none items-center justify-center rounded-full text-[10px] font-bold " +
                (r.status === "passed"
                  ? "bg-emerald-100 text-emerald-700"
                  : r.status === "skipped"
                    ? "bg-card text-text-muted"
                    : "bg-red-100 text-red-700")
              }
            >
              {r.status === "passed" ? "✓" : r.status === "skipped" ? "–" : "✕"}
            </span>
            <div className="flex-1">
              <div className="font-medium text-text-primary">{r.title}</div>
              <div className="mt-0.5 text-[12px] text-text-secondary">{r.observed}</div>
              {r.status === "failed" && (
                <div className="mt-1 text-[12px] italic text-text-muted">→ {r.fix}</div>
              )}
              {r.status === "failed" && r.locations?.length > 0 && (
                <div className="mt-2 space-y-2">
                  {r.locations.map((loc) => (
                    <div
                      key={`${r.id}:${loc.path}:${loc.line}:${loc.title}`}
                      className="rounded-lg border border-border-muted bg-card px-2.5 py-2 font-mono text-[11px] leading-relaxed text-text-secondary"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2 font-sans text-[11px]">
                        <span className="font-semibold text-text-primary">
                          {loc.path}:{loc.line}
                        </span>
                        <span className="rounded-full bg-chip-alt px-2 py-0.5 uppercase tracking-wide text-text-muted">
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
            <div className="font-mono text-[11px] text-text-muted">{r.weight}pt</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Methodology() {
  const sorted = useMemo(
    () =>
      [...RULES].sort((a, b) => {
        if (a.axis !== b.axis) return AXES.indexOf(a.axis) - AXES.indexOf(b.axis);
        return b.weight - a.weight;
      }),
    []
  );

  return (
    <div className="mt-3 max-w-[840px] rounded-2xl border border-border bg-card p-5 shadow-card">
      <div className="space-y-2 text-[13px] leading-relaxed text-text-secondary">
        <p>
          <span className="font-semibold text-text-primary">Inputs.</span> GitHub repo (live API),
          PRD (.pdf/.md/.txt), and a finance CSV. Any combination works — missing inputs are
          skipped instead of counted against the grade.
        </p>
        <p>
          <span className="font-semibold text-text-primary">Rules.</span> {RULES.length}{" "}
          deterministic checks across 5 axes. No LLM in the scoring loop. Sub-grade = 100 −
          (failed-weight / evaluated-weight) × 100. Composite = equal-weight average of axes
          with at least one evaluated rule.
        </p>
      </div>

      <div className="mt-4 max-h-80 overflow-y-auto rounded-xl border border-border-muted">
        <table className="w-full text-left text-[12px]">
          <thead className="sticky top-0 bg-chip-alt text-[10px] uppercase tracking-wider text-text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Rule</th>
              <th className="px-3 py-2 font-medium">Axis</th>
              <th className="px-3 py-2 text-right font-medium">Weight</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.id} className="border-t border-border-muted">
                <td className="px-3 py-2 text-text-primary">
                  {r.title}
                  {r.dollarImpact > 0 && (
                    <span className="ml-2 rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-700">
                      ${r.dollarImpact.toLocaleString()} downside
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 capitalize text-text-secondary">{r.axis}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">
                  {r.weight}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] text-text-muted">
        Tune by editing <code className="font-mono">startupRubric.js</code> — no other file needs
        to change. Each role owns the rules in their axis.
      </p>
    </div>
  );
}
