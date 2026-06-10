import { useEffect, useRef, useState } from "react";
import {
  Scale, ChevronDown, ChevronUp, CheckCircle2,
  Clock, DollarSign, ShieldAlert, ShieldCheck, Sparkles, X,
  Database, RefreshCw, Play, Search, FileText, ExternalLink, ToggleLeft, ToggleRight,
} from "lucide-react";

const COMPANY_CONTEXT_KEY = "startupGrader.companyContext.v1";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt(n) {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
  }).format(n);
}

function fmtRange(lo, hi) {
  return `${fmt(lo)}–${fmt(hi)}`;
}

// ── static data ───────────────────────────────────────────────────────────────

const US_STATES = [
  ["", "Select state…"],
  ["AL","Alabama"],["AK","Alaska"],["AZ","Arizona"],["AR","Arkansas"],
  ["CA","California"],["CO","Colorado"],["CT","Connecticut"],["DE","Delaware"],
  ["DC","Washington D.C."],["FL","Florida"],["GA","Georgia"],["HI","Hawaii"],
  ["ID","Idaho"],["IL","Illinois"],["IN","Indiana"],["IA","Iowa"],
  ["KS","Kansas"],["KY","Kentucky"],["LA","Louisiana"],["ME","Maine"],
  ["MD","Maryland"],["MA","Massachusetts"],["MI","Michigan"],["MN","Minnesota"],
  ["MS","Mississippi"],["MO","Missouri"],["MT","Montana"],["NE","Nebraska"],
  ["NV","Nevada"],["NH","New Hampshire"],["NJ","New Jersey"],["NM","New Mexico"],
  ["NY","New York"],["NC","North Carolina"],["ND","North Dakota"],["OH","Ohio"],
  ["OK","Oklahoma"],["OR","Oregon"],["PA","Pennsylvania"],["RI","Rhode Island"],
  ["SC","South Carolina"],["SD","South Dakota"],["TN","Tennessee"],["TX","Texas"],
  ["UT","Utah"],["VT","Vermont"],["VA","Virginia"],["WA","Washington"],
  ["WV","West Virginia"],["WI","Wisconsin"],["WY","Wyoming"],
];

const INDUSTRY_DISPLAY = {
  environmental: "Environmental",
  finance:       "Finance",
  healthcare:    "Healthcare",
  tech:          "Technology",
  manufacturing: "Manufacturing",
  retail:        "Retail / CPG",
  real_estate:   "Real Estate",
  agriculture:   "Agriculture",
  general:       "General",
};

const CATEGORY_ACCENT = {
  "Research & Discovery":     "text-status-enrolled-text",
  "Analysis & Documentation": "text-status-committee-text",
  "Strategic Planning":       "text-accent-gold",
  "Client Communication":     "text-status-chaptered-text",
};

const CATEGORY_BADGE_BG = {
  "Research & Discovery":     "bg-status-enrolled-bg text-status-enrolled-text",
  "Analysis & Documentation": "bg-status-committee-bg text-status-committee-text",
  "Strategic Planning":       "bg-accent-gold/20 text-accent-gold",
  "Client Communication":     "bg-status-chaptered-bg text-status-chaptered-text",
};

const LEGAL_SOURCE_OPTIONS = [
  ["federal_register", "Federal Register"],
  ["courtlistener", "CourtListener"],
  ["ecfr", "eCFR"],
  ["regulations_gov", "Regulations.gov"],
  ["ftc", "FTC"],
  ["cfpb", "CFPB"],
  ["sec", "SEC"],
  ["hhs_ocr", "HHS OCR"],
  ["eeoc", "EEOC"],
  ["dol", "DOL"],
  ["irs", "IRS"],
  ["state_ag", "State AG"],
];

const TOPIC_OPTIONS = [
  ["privacy", "Privacy"],
  ["financial_compliance", "Financial compliance"],
  ["employment_payroll", "Employment / payroll"],
  ["security_controls", "Security controls"],
  ["licensing", "Licensing"],
  ["consumer_protection", "Consumer protection"],
  ["healthcare", "Healthcare"],
  ["ai_data_governance", "AI / data governance"],
  ["compliance", "General compliance"],
];

const BULK_SOURCE_OPTIONS = [
  ["govinfo", "GovInfo bulk"],
  ["ecfr", "eCFR title XML"],
  ["courtlistener", "CourtListener / Free Law"],
  ["generic", "Custom bulk root"],
];

const DEFAULT_BULK_PRESETS = [
  ["govinfo_cfr", "GovInfo CFR bulk"],
  ["govinfo_fr", "GovInfo Federal Register bulk"],
  ["govinfo_uscode", "GovInfo U.S. Code bulk"],
  ["ecfr_financial_title_12", "eCFR Title 12 banks"],
  ["ecfr_sec_title_17", "eCFR Title 17 securities"],
  ["ecfr_ftc_title_16", "eCFR Title 16 FTC/commercial practices"],
  ["ecfr_health_title_21", "eCFR Title 21 FDA/health"],
  ["ecfr_hhs_title_45", "eCFR Title 45 HHS/HIPAA"],
  ["ecfr_labor_title_29", "eCFR Title 29 labor"],
  ["ecfr_tax_title_26", "eCFR Title 26 tax"],
  ["free_law_opinions", "Free Law CourtListener opinions"],
  ["free_law_clusters", "Free Law CourtListener case clusters"],
];

const BULK_DATASET_HINTS = {
  govinfo: "CFR, FR, or USCODE",
  ecfr: "title-16 or title-21",
  courtlistener: "opinions or clusters",
  generic: "dataset folder or file path",
};

// ── sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, delay = "0s" }) {
  return (
    <div
      className="animate-slide-up rounded-2xl border border-border bg-card px-5 py-4 shadow-card"
      style={{ animationDelay: delay }}
    >
      <div className="mb-1 text-[11px] uppercase tracking-wider text-text-muted">{label}</div>
      <div className="text-[22px] font-bold tabular-nums text-text-primary">{value}</div>
      {sub && <div className="mt-0.5 text-[12px] text-text-muted">{sub}</div>}
    </div>
  );
}

function ComparisonTable({ result }) {
  const rows = [
    {
      label: "Cost",
      legibill: "Included",
      lawyer: fmt(result.total_cost),
      nothing: "$0 today",
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass: "text-status-committee-text font-semibold",
      nothingClass: "text-text-muted",
    },
    {
      label: "Timeline",
      legibill: "Seconds",
      lawyer: "6–8 weeks",
      nothing: "—",
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass: "text-text-secondary",
      nothingClass: "text-text-muted",
    },
    {
      label: "Bills covered",
      legibill: `All ${result.ca_bills_introduced.toLocaleString()}`,
      lawyer: "Selective",
      nothing: "None",
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass: "text-text-secondary",
      nothingClass: "text-text-muted",
    },
    {
      label: "Compliance risk",
      legibill: "Managed",
      lawyer: "Managed",
      nothing: "High",
      legibillIcon: <ShieldCheck className="inline h-3.5 w-3.5 mr-1 text-status-chaptered-text" />,
      lawyerIcon:   <ShieldCheck className="inline h-3.5 w-3.5 mr-1 text-status-chaptered-text" />,
      nothingIcon:  <ShieldAlert className="inline h-3.5 w-3.5 mr-1 text-status-committee-text" />,
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass:   "text-status-chaptered-text",
      nothingClass:  "text-status-committee-text font-semibold",
    },
  ];

  return (
    <div className="animate-slide-up overflow-hidden rounded-3xl border border-border bg-card shadow-card" style={{ animationDelay: "0.14s" }}>
      <div className="border-b border-border px-6 py-4">
        <div className="text-[13px] font-semibold text-text-primary">How it compares</div>
        <div className="mt-0.5 text-[12px] text-text-muted">Legi-Bill vs. hiring a law firm vs. doing nothing</div>
      </div>

      {/* Header row */}
      <div className="grid grid-cols-4 border-b border-border bg-chip-alt/60 px-6 py-2.5">
        <div />
        <div className="text-center text-[12px] font-semibold text-text-primary">Legi-Bill</div>
        <div className="text-center text-[12px] font-medium text-text-secondary">Hire a Firm</div>
        <div className="text-center text-[12px] font-medium text-text-secondary">Do Nothing</div>
      </div>

      {rows.map((row, i) => (
        <div
          key={row.label}
          className={`grid grid-cols-4 px-6 py-3 ${i < rows.length - 1 ? "border-b border-border" : ""}`}
        >
          <div className="text-[13px] text-text-muted self-center">{row.label}</div>
          <div className={`text-center text-[13px] self-center ${row.legibillClass}`}>
            {row.legibillIcon}{row.legibill}
          </div>
          <div className={`text-center text-[13px] self-center ${row.lawyerClass}`}>
            {row.lawyerIcon}{row.lawyer}
          </div>
          <div className={`text-center text-[13px] self-center ${row.nothingClass}`}>
            {row.nothingIcon}{row.nothing}
          </div>
        </div>
      ))}
    </div>
  );
}

function LegalIntelligenceWorkspace() {
  const [status, setStatus] = useState(null);
  const [sources, setSources] = useState([]);
  const [authorities, setAuthorities] = useState([]);
  const [rules, setRules] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [query, setQuery] = useState("privacy notice data security");
  const [source, setSource] = useState("federal_register");
  const [topic, setTopic] = useState("privacy");
  const [industryTag, setIndustryTag] = useState("tech");
  const [bulkLocation, setBulkLocation] = useState("");
  const [bulkSource, setBulkSource] = useState("govinfo");
  const [bulkDataset, setBulkDataset] = useState("CFR");
  const [bulkBaseUrl, setBulkBaseUrl] = useState("");
  const [bulkPreset, setBulkPreset] = useState("govinfo_cfr");
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState(null);

  async function loadWorkspace() {
    try {
      const [statusRes, sourcesRes, rulesRes, catalogRes] = await Promise.all([
        fetch("/api/legal-intelligence/status"),
        fetch("/api/legal-intelligence/sources"),
        fetch("/api/legal-intelligence/rules"),
        fetch("/api/legal-intelligence/catalog"),
      ]);
      if (!statusRes.ok || !sourcesRes.ok || !rulesRes.ok) {
        throw new Error("Could not load legal intelligence workspace.");
      }
      const statusData = await statusRes.json();
      const sourcesData = await sourcesRes.json();
      const rulesData = await rulesRes.json();
      const catalogData = catalogRes.ok ? await catalogRes.json() : null;
      setStatus(statusData);
      setSources(sourcesData.sources || []);
      setAuthorities(sourcesData.authorities || []);
      setRules(rulesData.rules || []);
      setCatalog(catalogData);
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    }
  }

  useEffect(() => {
    loadWorkspace();
  }, []);

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function runFetch() {
    if (!query.trim()) return;
    setBusy("fetch");
    setMessage(null);
    try {
      const data = await postJson("/api/legal-intelligence/fetch", {
        source,
        query,
        topic,
        jurisdiction: "US",
        industry_tags: industryTag ? [industryTag] : [],
        limit: 8,
        save_source: true,
      });
      setMessage({ type: "ok", text: `Fetched ${data.fetched_count} authorities; ${data.changed_count} changed or new.` });
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function runBulkImport() {
    if (!bulkLocation.trim()) return;
    setBusy("bulk");
    setMessage(null);
    try {
      const data = await postJson("/api/legal-intelligence/bulk-import", {
        location: bulkLocation.trim(),
        source_name: "bulk",
        topic,
        jurisdiction: "US",
        industry_tags: industryTag ? [industryTag] : [],
        limit: 500,
        save_source: true,
      });
      setMessage({ type: "ok", text: `Imported ${data.imported_count} bulk authorities; ${data.changed_count} changed or new.` });
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function runBulkSync() {
    if (bulkPreset === "custom" && !bulkDataset.trim()) return;
    setBusy("bulk-sync");
    setMessage(null);
    try {
      const data = await postJson("/api/legal-intelligence/bulk-sync", {
        preset_id: bulkPreset === "custom" ? null : bulkPreset,
        source: bulkSource,
        dataset: bulkDataset.trim(),
        bulk_base_url: bulkBaseUrl.trim() || null,
        topic,
        jurisdiction: "US",
        industry_tags: industryTag ? [industryTag] : [],
        limit: 500,
        max_files: 8,
        max_depth: 3,
        save_source: true,
      });
      setMessage({ type: "ok", text: `Synced ${data.discovered_locations.length} bulk files; imported ${data.imported_count} authorities.` });
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function setupExplicitSources() {
    setBusy("setup-sources");
    setMessage(null);
    try {
      const data = await postJson("/api/legal-intelligence/source-setup", {
        industry: industryTag || null,
        include_bulk: true,
      });
      setMessage({ type: "ok", text: `Configured ${data.public_source_count} API/feed sources and ${data.bulk_source_count} bulk sources.` });
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function runDistill() {
    setBusy("distill");
    setMessage(null);
    try {
      const data = await postJson("/api/legal-intelligence/distill", {
        changed_only: true,
        verify_citations: true,
      });
      setMessage({ type: "ok", text: `Distilled ${data.rule_count} scanner guidance rules.` });
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function runPipeline() {
    setBusy("pipeline");
    setMessage(null);
    try {
      const data = await postJson("/api/legal-intelligence/pipeline", {
        changed_only: true,
        verify_citations: true,
      });
      setMessage({ type: "ok", text: `Pipeline complete: ${data.changed_count} changed authorities, ${data.rule_count} rules.` });
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function toggleRule(rule) {
    setBusy(rule.id);
    try {
      const res = await fetch(`/api/legal-intelligence/rules/${encodeURIComponent(rule.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadWorkspace();
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  const enabledRules = rules.filter((r) => r.enabled && r.review_status !== "rejected").length;
  const lastChecked = status?.last_checked ? new Date(status.last_checked).toLocaleString() : "Not refreshed";
  const bulkPresetOptions = catalog?.bulk_sources?.length
    ? catalog.bulk_sources.map((preset) => [preset.id, preset.label])
    : DEFAULT_BULK_PRESETS;

  return (
    <section className="space-y-5">
      <div className="animate-slide-up">
        <div className="mb-2 flex items-center gap-2 text-text-secondary">
          <Database className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">Legal Intelligence</span>
        </div>
        <h1 className="animate-shimmer-text text-[32px] font-bold tracking-tight">
          Scanner Guidance Workspace
        </h1>
        <p className="mt-2 max-w-[680px] text-[15px] leading-relaxed text-text-secondary">
          Fetch public legal authorities, distill them into scanner guidance, and decide which
          source-backed rules should enrich repo findings.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Authorities" value={status?.authority_count ?? 0} sub="Fetched source records" />
        <StatCard label="Enabled rules" value={enabledRules} sub={`${status?.rule_count ?? 0} total rules`} />
        <StatCard label="Saved queries" value={status?.source_count ?? 0} sub="Refreshable sources" />
        <StatCard label="Last refresh" value={lastChecked === "Not refreshed" ? "Never" : "Ready"} sub={lastChecked} />
      </div>

      <div className="rounded-3xl border border-border bg-card p-5 shadow-card">
        <div className="grid gap-3 lg:grid-cols-[1.4fr_180px_180px_140px_auto]">
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Public legal query</label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-text-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full rounded-xl border border-border bg-chip-alt py-2 pl-9 pr-3 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
                placeholder="privacy notice data security"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Source</label>
            <select value={source} onChange={(e) => setSource(e.target.value)} className="w-full rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none">
              {LEGAL_SOURCE_OPTIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Topic</label>
            <select value={topic} onChange={(e) => setTopic(e.target.value)} className="w-full rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none">
              {TOPIC_OPTIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Industry tag</label>
            <input
              value={industryTag}
              onChange={(e) => setIndustryTag(e.target.value)}
              className="w-full rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
              placeholder="tech"
            />
          </div>
          <div className="flex items-end">
            <button onClick={runFetch} disabled={!!busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-action-dark px-4 py-2 text-[13px] font-semibold text-text-invert hover:opacity-90 disabled:opacity-40">
              <RefreshCw className={`h-4 w-4 ${busy === "fetch" ? "animate-spin" : ""}`} />
              Fetch
            </button>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-border bg-chip-alt/60 p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[12px] font-semibold text-text-primary">
              <Database className="h-4 w-4 text-accent-gold" />
              Explicit legal data sources
            </div>
            <button onClick={setupExplicitSources} disabled={!!busy} className="rounded-xl border border-border bg-card px-3 py-1.5 text-[12px] font-semibold text-text-primary hover:bg-white disabled:opacity-40">
              Set up defaults
            </button>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
            <div>
              <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Bulk source preset</label>
              <select value={bulkPreset} onChange={(e) => setBulkPreset(e.target.value)} className="w-full rounded-xl border border-border bg-card px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none">
                {bulkPresetOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                <option value="custom">Custom bulk source</option>
              </select>
            </div>
            <div className="flex items-end">
              <button onClick={runBulkSync} disabled={!!busy || (bulkPreset === "custom" && !bulkDataset.trim())} className="flex w-full items-center justify-center gap-2 rounded-xl bg-action-dark px-4 py-2 text-[13px] font-semibold text-text-invert hover:opacity-90 disabled:opacity-40">
                <RefreshCw className={`h-4 w-4 ${busy === "bulk-sync" ? "animate-spin" : ""}`} />
                Sync selected
              </button>
            </div>
          </div>
          {bulkPreset === "custom" && (
          <div className="mt-3 grid gap-3 lg:grid-cols-[180px_180px_1fr]">
            <div>
              <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Bulk source</label>
              <select value={bulkSource} onChange={(e) => setBulkSource(e.target.value)} className="w-full rounded-xl border border-border bg-card px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none">
                {BULK_SOURCE_OPTIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Dataset</label>
              <input
                value={bulkDataset}
                onChange={(e) => setBulkDataset(e.target.value)}
                className="w-full rounded-xl border border-border bg-card px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
                placeholder={BULK_DATASET_HINTS[bulkSource]}
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Base URL override</label>
              <input
                value={bulkBaseUrl}
                onChange={(e) => setBulkBaseUrl(e.target.value)}
                className="w-full rounded-xl border border-border bg-card px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
                placeholder="Optional S3/static bulk root"
              />
            </div>
          </div>
          )}
          <div className="mt-2 text-[11px] leading-5 text-text-muted">
            Defaults include GovInfo CFR/Federal Register/U.S. Code, eCFR domain titles, Free Law CourtListener bulk snapshots, and agency/API feeds. The selected preset is saved for future refreshes.
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">Bulk data path or HTTPS URL</label>
            <input
              value={bulkLocation}
              onChange={(e) => setBulkLocation(e.target.value)}
              className="w-full rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
              placeholder="/data/courtlistener/opinions.jsonl.gz or https://..."
            />
          </div>
          <div className="flex items-end">
            <button onClick={runBulkImport} disabled={!!busy || !bulkLocation.trim()} className="flex items-center gap-2 rounded-xl border border-border bg-chip-alt px-4 py-2 text-[13px] font-semibold text-text-primary hover:bg-white disabled:opacity-40">
              <Database className="h-4 w-4" />
              Bulk import
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button onClick={runDistill} disabled={!!busy} className="flex items-center gap-2 rounded-xl border border-border bg-chip-alt px-4 py-2 text-[13px] font-semibold text-text-primary hover:bg-white disabled:opacity-40">
            <FileText className="h-4 w-4" />
            Distill changed sources
          </button>
          <button onClick={runPipeline} disabled={!!busy} className="flex items-center gap-2 rounded-xl bg-accent-gold px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-40">
            <Play className="h-4 w-4" />
            Run pipeline
          </button>
          {message && (
            <div className={`rounded-xl px-3 py-2 text-[12px] ${message.type === "error" ? "bg-status-committee-bg text-status-committee-text" : "bg-status-chaptered-bg text-status-chaptered-text"}`}>
              {message.text}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <LegalTable
          title="Fetched authorities"
          empty="No authorities fetched yet."
          rows={authorities.slice(0, 8)}
          render={(authority) => (
            <div key={authority.source_id} className="grid grid-cols-[1fr_auto] gap-3 border-b border-border px-4 py-3 last:border-0">
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold text-text-primary">{authority.title}</div>
                <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-text-muted">
                  <span>{authority.metadata?.source || authority.authority_type}</span>
                  <span>{authority.topic}</span>
                  <span>{authority.citation || "No citation"}</span>
                </div>
              </div>
              {authority.url && (
                <a href={authority.url} target="_blank" rel="noreferrer" className="text-text-muted hover:text-text-primary">
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
          )}
        />

        <LegalTable
          title="Distilled scanner rules"
          empty="No scanner guidance rules yet."
          rows={rules.slice(0, 8)}
          render={(rule) => (
            <div key={rule.id} className="border-b border-border px-4 py-3 last:border-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold text-text-primary">{rule.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <span className="rounded-full bg-chip px-2 py-0.5 text-[10px] font-semibold text-text-muted">{rule.category}</span>
                    <span className="rounded-full bg-chip px-2 py-0.5 text-[10px] font-semibold text-text-muted">{rule.confidence} confidence</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${rule.citation_verified ? "bg-status-chaptered-bg text-status-chaptered-text" : "bg-chip text-text-muted"}`}>
                      {rule.citation_verified ? "citation verified" : "source-backed"}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-text-secondary">{rule.finding_rationale}</p>
                </div>
                <button onClick={() => toggleRule(rule)} disabled={busy === rule.id} className="text-text-muted hover:text-text-primary">
                  {rule.enabled ? <ToggleRight className="h-6 w-6 text-status-chaptered-text" /> : <ToggleLeft className="h-6 w-6" />}
                </button>
              </div>
            </div>
          )}
        />
      </div>
    </section>
  );
}

function LegalTable({ title, empty, rows, render }) {
  return (
    <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-card">
      <div className="border-b border-border px-4 py-3">
        <div className="text-[13px] font-semibold text-text-primary">{title}</div>
      </div>
      {rows.length ? rows.map(render) : <div className="px-4 py-6 text-[13px] text-text-muted">{empty}</div>}
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function LegalIntelligence() {
  const [companyText, setCompanyText] = useState("");
  const [prefilled, setPrefilled] = useState(null);
  const [state, setState] = useState("");
  const [rateOverride, setRateOverride] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});
  const resultsRef = useRef(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(COMPANY_CONTEXT_KEY);
      if (!raw) return;
      const ctx = JSON.parse(raw);
      if (ctx?.description) {
        setCompanyText(ctx.description);
        setPrefilled(ctx);
      }
    } catch {}
  }, []);

  function clearPrefill() {
    setPrefilled(null);
    setCompanyText("");
    try { localStorage.removeItem(COMPANY_CONTEXT_KEY); } catch {}
  }

  async function calculate() {
    if (!companyText.trim()) return;
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.append("company_text", companyText);
    if (state) fd.append("state", state);
    if (rateOverride) fd.append("hourly_rate", rateOverride);
    try {
      const res = await fetch("/api/legal-savings", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const open = {};
      data.categories.forEach((c) => (open[c.category] = true));
      setExpanded(open);
      setResult(data);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function toggle(cat) {
    setExpanded((prev) => ({ ...prev, [cat]: !prev[cat] }));
  }

  return (
    <div className="space-y-8">
      <LegalIntelligenceWorkspace />

      {/* ── Header ── */}
      <div className="animate-slide-up border-t border-border pt-8">
        <div className="mb-2 flex items-center gap-2 text-text-secondary">
          <Scale className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">Legal Intelligence</span>
        </div>
        <h1 className="animate-shimmer-text text-[32px] font-bold tracking-tight">
          Legal Cost Savings
        </h1>
        <p className="mt-2 max-w-[560px] text-[15px] leading-relaxed text-text-secondary">
          Enter your company details and we'll show you exactly what a compliance
          attorney would charge — and what Legi-Bill handles for you automatically.
        </p>
      </div>

      {/* ── Input card ── */}
      <div
        className="animate-slide-up rounded-3xl border border-border bg-card p-6 shadow-card"
        style={{ animationDelay: "0.08s" }}
      >
        <div className="mb-2 flex items-center justify-between">
          <label className="text-[13px] font-semibold text-text-primary">
            Describe your company
          </label>
          {prefilled && (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-full bg-status-chaptered-bg px-2.5 py-0.5">
                <Sparkles className="h-3 w-3 text-status-chaptered-text" strokeWidth={2.4} />
                <span className="text-[11px] font-semibold text-status-chaptered-text">
                  Pre-filled from Startup Health · {prefilled.name}
                </span>
              </div>
              <button onClick={clearPrefill} className="text-text-muted hover:text-text-primary transition-colors">
                <X className="h-3.5 w-3.5" strokeWidth={2.4} />
              </button>
            </div>
          )}
        </div>
        <textarea
          rows={3}
          placeholder="e.g. We're a 60-person fintech startup in Austin building B2B payment infrastructure for mid-market businesses…"
          className="w-full resize-none rounded-xl border border-border bg-chip-alt px-4 py-3 text-[14px] text-text-primary placeholder:text-text-muted focus:border-accent-gold focus:outline-none"
          value={companyText}
          onChange={(e) => setCompanyText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) calculate(); }}
        />

        <div className="mt-3 flex flex-wrap items-end gap-3">
          {/* State picker */}
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">
              State
            </label>
            <select
              value={state}
              onChange={(e) => setState(e.target.value)}
              className="w-48 rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
            >
              {US_STATES.map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>

          {/* Rate override */}
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">
              Override rate ($/hr)
            </label>
            <input
              type="number"
              min={0}
              placeholder="Auto by industry"
              className="w-40 rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted focus:border-accent-gold focus:outline-none"
              value={rateOverride}
              onChange={(e) => setRateOverride(e.target.value)}
            />
          </div>

          <button
            onClick={calculate}
            disabled={!companyText.trim() || loading}
            className="rounded-xl bg-action-dark px-6 py-2 text-[13px] font-semibold text-text-invert transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Calculating…" : "Calculate Savings"}
          </button>
        </div>

        {error && <p className="mt-3 text-[12px] text-status-committee-text">{error}</p>}
      </div>

      {/* ── Results ── */}
      {result && (
        <div ref={resultsRef} className="space-y-5">

          {/* Hero banner */}
          <div
            className="animate-slide-up overflow-hidden rounded-3xl border border-accent-gold/30 bg-accent-gold/10 px-8 py-6 shadow-card"
            style={{ animationDelay: "0s" }}
          >
            <div className="flex items-center justify-between gap-6">
              <div>
                <div className="text-[13px] uppercase tracking-wider text-text-muted">
                  Attorney work automated
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-[52px] font-bold tabular-nums leading-none text-text-primary">
                    {result.total_hours}
                  </span>
                  <span className="text-[20px] text-text-muted">hours</span>
                </div>
                <div className="mt-2 text-[14px] text-text-secondary">
                  Delivered in seconds — not the{" "}
                  <span className="font-semibold text-text-primary">6–8 weeks</span> a firm would take.
                </div>
              </div>
              <div className="hidden flex-col items-end gap-2 sm:flex">
                <div className="text-[13px] uppercase tracking-wider text-text-muted">
                  Estimated legal bill
                </div>
                <div className="text-[44px] font-bold tabular-nums leading-none text-accent-gold">
                  {fmt(result.total_cost)}
                </div>
                <div className="text-[13px] font-semibold text-status-chaptered-text">
                  Included in your subscription
                </div>
              </div>
            </div>
          </div>

          {/* 3 stat cards */}
          <div className="grid grid-cols-3 gap-3">
            <StatCard
              label="Industry detected"
              value={INDUSTRY_DISPLAY[result.industry] ?? result.industry}
              sub={result.lawyer_title}
              delay="0.04s"
            />
            <StatCard
              label={`Attorney rate · ${result.state_label}`}
              value={`$${result.hourly_rate}/hr`}
              sub={
                result.state && result.state_multiplier !== 1.0
                  ? `${result.state_multiplier > 1 ? "+" : ""}${Math.round((result.state_multiplier - 1) * 100)}% vs. national avg`
                  : "National average rate"
              }
              delay="0.08s"
            />
            <StatCard
              label="Relevant bills found"
              value={result.matched_bill_count}
              sub={`of ${result.ca_bills_introduced.toLocaleString()} introduced this session`}
              delay="0.12s"
            />
          </div>

          {/* Benchmark context */}
          <div
            className="animate-slide-up rounded-2xl border border-border bg-chip-alt px-5 py-4 shadow-card"
            style={{ animationDelay: "0.1s" }}
          >
            <div className="flex items-start gap-3">
              <DollarSign className="mt-0.5 h-4 w-4 shrink-0 text-status-committee-text" strokeWidth={2} />
              <p className="text-[13px] leading-relaxed text-text-secondary">
                <span className="font-semibold text-text-primary">
                  {INDUSTRY_DISPLAY[result.industry] ?? result.industry} companies
                  {result.state ? ` in ${result.state_label}` : ""} typically budget{" "}
                  {fmtRange(result.benchmark_low, result.benchmark_high)}/year{" "}
                </span>
                {result.benchmark_note}. A full one-time regulatory engagement like
                this is typically scoped and billed separately on top of that retainer.
              </p>
            </div>
          </div>

          {/* Comparison table */}
          <ComparisonTable result={result} />

          {/* Invoice */}
          <div
            className="animate-slide-up overflow-hidden rounded-3xl border border-border bg-card shadow-card"
            style={{ animationDelay: "0.18s" }}
          >
            {/* Invoice header */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-text-muted">
                  Line-item breakdown
                </div>
                <div className="mt-0.5 text-[15px] font-semibold text-text-primary">
                  What a law firm would invoice
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] text-text-muted">
                  At {fmt(result.hourly_rate)}/hr · {result.matched_bill_count} relevant bills
                </div>
              </div>
            </div>

            {/* Column labels */}
            <div className="grid grid-cols-[1fr_72px_100px_140px] gap-2 border-b border-border px-6 py-2">
              <div className="text-[11px] uppercase tracking-wider text-text-muted">Service</div>
              <div className="text-right text-[11px] uppercase tracking-wider text-text-muted">Hrs</div>
              <div className="text-right text-[11px] uppercase tracking-wider text-text-muted">Cost</div>
              <div className="text-center text-[11px] uppercase tracking-wider text-text-muted">Legi-Bill status</div>
            </div>

            {result.categories.map((cat) => (
              <div key={cat.category} className="border-b border-border last:border-0">
                {/* Category header */}
                <button
                  onClick={() => toggle(cat.category)}
                  className="grid w-full grid-cols-[1fr_72px_100px_140px] gap-2 px-6 py-3 transition-colors hover:bg-chip-alt"
                >
                  <div className="flex items-center gap-2">
                    {expanded[cat.category]
                      ? <ChevronUp className="h-3.5 w-3.5 shrink-0 text-text-muted" />
                      : <ChevronDown className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
                    <span className={`text-[13px] font-semibold ${CATEGORY_ACCENT[cat.category] ?? "text-text-primary"}`}>
                      {cat.category}
                    </span>
                  </div>
                  <div className="self-center text-right text-[13px] font-medium tabular-nums text-text-primary">
                    {cat.subtotal_hours}h
                  </div>
                  <div className="self-center text-right text-[13px] tabular-nums">
                    <span className="text-text-muted line-through">{fmt(cat.subtotal_cost)}</span>
                  </div>
                  <div className="flex items-center justify-center">
                    <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${CATEGORY_BADGE_BG[cat.category] ?? "bg-chip text-text-muted"}`}>
                      {cat.badge}
                    </span>
                  </div>
                </button>

                {/* Task rows */}
                {expanded[cat.category] && cat.tasks.map((task) => (
                  <div
                    key={task.name}
                    className="grid grid-cols-[1fr_72px_100px_140px] gap-2 bg-chip-alt/50 px-6 py-2.5"
                  >
                    <div className="pl-5">
                      <div className="text-[13px] text-text-primary">{task.name}</div>
                      <div className="mt-0.5 text-[11px] text-text-muted">{task.description}</div>
                    </div>
                    <div className="self-center text-right text-[12px] tabular-nums text-text-secondary">
                      {task.hours}h
                    </div>
                    <div className="self-center text-right text-[12px] tabular-nums">
                      <span className="text-text-muted line-through">{fmt(task.cost)}</span>
                    </div>
                    <div className="flex items-center justify-center self-center">
                      <div className="flex items-center gap-1 rounded-full bg-status-chaptered-bg px-2 py-0.5">
                        <CheckCircle2 className="h-3 w-3 text-status-chaptered-text" strokeWidth={2.5} />
                        <span className="text-[10px] font-semibold text-status-chaptered-text">Automated</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ))}

            {/* Total */}
            <div className="border-t-2 border-accent-gold/30 bg-accent-gold/8 px-6 py-5">
              <div className="flex items-end justify-between">
                <div className="flex items-center gap-3">
                  <Clock className="h-5 w-5 text-text-muted" strokeWidth={1.5} />
                  <div>
                    <div className="text-[12px] text-text-muted">Total attorney hours</div>
                    <div className="text-[28px] font-bold tabular-nums text-text-primary">
                      {result.total_hours}
                      <span className="ml-1 text-[14px] font-normal text-text-muted">hours</span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[12px] text-text-muted">Estimated attorney fees</div>
                  <div className="text-[28px] font-bold tabular-nums text-accent-gold">
                    {fmt(result.total_cost)}
                  </div>
                  <div className="mt-1 text-[12px] font-semibold text-status-chaptered-text">
                    Included in your Legi-Bill subscription
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Source footnote */}
          <p
            className="animate-slide-up text-[11px] leading-relaxed text-text-muted"
            style={{ animationDelay: "0.22s" }}
          >
            Bill volume: <span className="font-medium">4,821 bills introduced</span> and{" "}
            <span className="font-medium">1,684 signed into law</span> in the 2023-24 CA session
            (Capitol Weekly; CalMatters; LAist). Attorney rates:{" "}
            <span className="font-medium">2024 Clio Legal Trends Report</span>,{" "}
            <span className="font-medium">ABA Legal Technology Survey</span>, and{" "}
            <span className="font-medium">BLS Occupational Employment Statistics (SOC 23-1011, May 2023)</span>.
            State adjustments based on BLS regional wage indices. Hours estimates reflect typical
            compliance engagement scope; actual engagements vary by firm and complexity.
          </p>
        </div>
      )}
    </div>
  );
}
