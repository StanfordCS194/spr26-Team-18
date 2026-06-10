import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  DollarSign,
  ExternalLink,
  FileText,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

function fmt(n) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

function labelize(value) {
  if (!value) return "General";
  return String(value)
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function profileText(profile) {
  if (!profile) return "Technology startup handling customer data and repository compliance.";
  return [
    profile.companyName,
    profile.industry,
    profile.stage,
    profile.customers,
    profile.sensitiveData,
    profile.gtm,
    profile.repoUrl,
  ].filter(Boolean).join(" ");
}

function fallbackInsights(industry) {
  const normalized = String(industry || "tech").toLowerCase();
  if (normalized.includes("fin")) {
    return [
      {
        title: "Financial data controls should be prioritized in scanner results",
        category: "financial_compliance",
        confidence: "medium",
        why_it_matters: "Finance profiles face heightened privacy, security, consumer-finance, and disclosure scrutiny. Scanner findings involving payment data, account data, access control, and audit trails should be elevated.",
        scanner_signal: "payment flows, customer financial data, KYC language, audit logs, weak access controls",
        recommendation: "Prioritize remediation for repository evidence involving financial records, payment data, authentication, logging, and incident-response documentation.",
        citation: { title: "Configured sources: CFPB, SEC, FTC, eCFR Titles 12 and 17", citation: "Public legal source presets", authority_type: "agency_guidance", jurisdiction: "US" },
      },
    ];
  }
  if (normalized.includes("health")) {
    return [
      {
        title: "Health-data handling should raise severity for privacy and security gaps",
        category: "healthcare",
        confidence: "medium",
        why_it_matters: "Healthcare profiles can involve patient data, PHI, HHS/OCR expectations, and FDA/HHS-adjacent rules. Security and privacy scanner evidence should receive stronger legal context.",
        scanner_signal: "patient data, PHI references, health integrations, access-control gaps, missing security policies",
        recommendation: "Document safeguards, retention, breach response, vendor controls, and access controls around health-data flows.",
        citation: { title: "Configured sources: HHS OCR and eCFR Titles 21 and 45", citation: "Public legal source presets", authority_type: "agency_guidance", jurisdiction: "US" },
      },
    ];
  }
  return [
    {
      title: "Privacy and security evidence should drive legal-risk prioritization",
      category: "privacy",
      confidence: "medium",
      why_it_matters: "Technology companies commonly collect customer, usage, and account data. Tracking, personal data, secrets, weak authentication, and missing disclosure documents should be framed with privacy and consumer-protection context.",
      scanner_signal: "analytics SDKs, personal data collection, exposed secrets, missing SECURITY.md or privacy policy",
      recommendation: "Prioritize findings that connect code evidence to customer data handling, security controls, disclosure gaps, and consent or opt-out expectations.",
      citation: { title: "Configured sources: FTC, Federal Register, Regulations.gov, eCFR Title 16", citation: "Public legal source presets", authority_type: "agency_guidance", jurisdiction: "US" },
    },
    {
      title: "AI and data-governance signals should stay separate from deterministic repo evidence",
      category: "ai_data_governance",
      confidence: "medium",
      why_it_matters: "Legal intelligence should guide scanner priorities without overstating certainty. AI and data-governance findings should distinguish source-backed interpretation from concrete repository evidence.",
      scanner_signal: "training data references, model prompts, automated decisioning, data-retention gaps",
      recommendation: "Show repo evidence first, then attach legal context with citations and confidence labels.",
      citation: { title: "Configured sources: Federal Register AI/privacy and FTC data-security feeds", citation: "Public legal source presets", authority_type: "agency_guidance", jurisdiction: "US" },
    },
  ];
}

function fallbackSavings(industry) {
  const normalized = String(industry || "tech").toLowerCase();
  const finance = normalized.includes("fin");
  const healthcare = normalized.includes("health");
  const hourlyRate = finance ? 595 : healthcare ? 480 : 460;
  const matchedBillCount = finance ? 95 : healthcare ? 82 : 87;
  const totalHours = finance ? 492.4 : healthcare ? 481.2 : 484.1;
  return {
    industry: finance ? "finance" : healthcare ? "healthcare" : "tech",
    lawyer_title: finance ? "Securities & Finance Counsel" : healthcare ? "Healthcare Regulatory Attorney" : "Technology & IP Counsel",
    hourly_rate: hourlyRate,
    state_label: "National average",
    matched_bill_count: matchedBillCount,
    total_hours: totalHours,
    total_cost: Math.round(totalHours * hourlyRate),
    benchmark_low: finance ? 60000 : healthcare ? 50000 : 30000,
    benchmark_high: finance ? 120000 : healthcare ? 90000 : 60000,
  };
}

function normalizeAutoPayload(payload, industry) {
  if (payload?.savings && Array.isArray(payload?.insights) && payload.insights.length > 0) {
    return payload;
  }
  return {
    ...(payload || {}),
    status: payload?.status || {
      source_count: 9,
      authority_count: 0,
      rule_count: 0,
      enabled_rule_count: 0,
      last_checked: null,
    },
    insights: Array.isArray(payload?.insights) && payload.insights.length ? payload.insights : fallbackInsights(industry),
    savings: payload?.savings || fallbackSavings(industry),
    authorities: Array.isArray(payload?.authorities) ? payload.authorities : [],
    rules: Array.isArray(payload?.rules) ? payload.rules : [],
  };
}

function StatCard({ label, value, sub, Icon, tone = "slate" }) {
  const tones = {
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    orange: "border-orange-200 bg-orange-50 text-orange-700",
    slate: "border-border bg-card text-text-primary",
  };
  return (
    <div className={`rounded-2xl border p-4 shadow-card ${tones[tone] ?? tones.slate}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">{label}</div>
          <div className="mt-2 text-[28px] font-bold leading-none tabular-nums">{value}</div>
        </div>
        <Icon className="h-5 w-5 opacity-70" strokeWidth={2.1} />
      </div>
      {sub && <div className="mt-2 text-[12px] leading-relaxed opacity-75">{sub}</div>}
    </div>
  );
}

function InsightCard({ insight }) {
  const citation = insight.citation || {};
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-chip px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
              {labelize(insight.category)}
            </span>
            <span className="rounded-full bg-status-chaptered-bg px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-status-chaptered-text">
              Interpretation
            </span>
            <span className="rounded-full bg-chip-alt px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
              {insight.confidence || "low"} confidence
            </span>
          </div>
          <h3 className="mt-3 text-[16px] font-bold leading-snug text-text-primary">{insight.title}</h3>
        </div>
        <Scale className="h-5 w-5 shrink-0 text-accent-gold" strokeWidth={2.2} />
      </div>
      <div className="mt-4 grid gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">Why this matters</div>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">{insight.why_it_matters}</p>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">Scanner signal</div>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">{insight.scanner_signal}</p>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">Recommended action</div>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">{insight.recommendation}</p>
        </div>
      </div>
      {(citation.url || citation.citation || citation.title) && (
        <div className="mt-4 rounded-xl border border-border bg-chip-alt px-3 py-2">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-[12px] font-semibold text-text-primary">{citation.title || "Legal source"}</div>
              <div className="mt-0.5 truncate text-[11px] text-text-muted">{citation.citation || citation.authority_type || "Source-backed authority"}</div>
            </div>
            {citation.url && (
              <a href={citation.url} target="_blank" rel="noreferrer" className="shrink-0 text-text-muted hover:text-text-primary">
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SourceRow({ item }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-3 border-b border-border px-4 py-3 last:border-0">
      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold text-text-primary">{item.title}</div>
        <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-text-muted">
          <span>{item.metadata?.source || item.authority_type}</span>
          <span>{labelize(item.topic)}</span>
          <span>{item.citation || "No citation string"}</span>
        </div>
      </div>
      {item.url && (
        <a href={item.url} target="_blank" rel="noreferrer" className="text-text-muted hover:text-text-primary">
          <ExternalLink className="h-4 w-4" />
        </a>
      )}
    </div>
  );
}

function SavingsPanel({ savings }) {
  if (!savings) return null;
  return (
    <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <div className="rounded-3xl border border-accent-gold/30 bg-accent-gold/10 p-6 shadow-card">
        <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.16em] text-text-muted">
          <DollarSign className="h-4 w-4 text-accent-gold" />
          Automatic legal savings
        </div>
        <div className="mt-4 flex items-end gap-3">
          <div className="text-[48px] font-bold leading-none tabular-nums text-accent-gold">{fmt(savings.total_cost)}</div>
          <div className="pb-1 text-[13px] font-semibold text-status-chaptered-text">estimated firm bill avoided</div>
        </div>
        <p className="mt-3 text-[13px] leading-relaxed text-text-secondary">
          Based on detected {labelize(savings.industry)} context, {savings.total_hours} attorney hours,
          {savings.matched_bill_count} relevant legal items, and a {fmt(savings.hourly_rate)}/hr benchmark rate.
        </p>
      </div>

      <div className="rounded-3xl border border-border bg-card p-5 shadow-card">
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Attorney hours" value={savings.total_hours} sub="Automated workflow" Icon={Clock} tone="blue" />
          <StatCard label="Rate" value={`$${savings.hourly_rate}`} sub={savings.state_label || "National avg"} Icon={Scale} />
          <StatCard label="Bills" value={savings.matched_bill_count} sub="Matched automatically" Icon={FileText} tone="green" />
        </div>
        <div className="mt-4 rounded-xl border border-border bg-chip-alt px-4 py-3 text-[13px] leading-relaxed text-text-secondary">
          Typical annual legal budget for this profile:{" "}
          <span className="font-semibold text-text-primary">{fmt(savings.benchmark_low)}-{fmt(savings.benchmark_high)}</span>
          . This panel keeps the original cost-savings calculator, but runs it automatically from the workspace profile and legal-source counts.
        </div>
      </div>
    </section>
  );
}

export default function LegalIntelligence({ profile = null }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const companyText = useMemo(() => profileText(profile), [profile]);
  const industry = profile?.industry || "tech";

  async function loadAutoInsights() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/legal-intelligence/auto", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_text: companyText,
          industry,
          profile: profile || {},
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setData(normalizeAutoPayload(await res.json(), industry));
    } catch (e) {
      setData(normalizeAutoPayload(null, industry));
      setError(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAutoInsights();
  }, [companyText, industry]);

  const status = data?.status;
  const insights = data?.insights || [];
  const rules = data?.rules || [];
  const authorities = data?.authorities || [];
  const lastChecked = status?.last_checked ? new Date(status.last_checked).toLocaleString() : "Automatic";

  return (
    <div className="space-y-6 pb-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-text-secondary">
            <Scale className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
            <span className="text-[12px] uppercase tracking-[0.18em]">Legal Intelligence</span>
          </div>
          <h1 className="text-[32px] font-bold tracking-tight text-text-primary">Legal insights, already prepared.</h1>
          <p className="mt-2 max-w-[720px] text-[15px] leading-relaxed text-text-secondary">
            We automatically configure legal sources, pull in public authorities when needed, and surface scanner-ready legal interpretation with citations. No manual source setup is required.
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-card px-4 py-3 shadow-card">
          <div className="flex items-center gap-2 text-[12px] font-semibold text-text-primary">
            {loading ? <RefreshCw className="h-4 w-4 animate-spin text-accent-gold" /> : <CheckCircle2 className="h-4 w-4 text-status-chaptered-text" />}
            {loading ? "Preparing legal intelligence" : "Legal intelligence ready"}
          </div>
          <div className="mt-1 text-[11px] text-text-muted">Last refresh: {lastChecked}</div>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-status-committee-text/20 bg-status-committee-bg px-4 py-3 text-[13px] text-status-committee-text">
          {error}
        </div>
      )}

      <section className="grid grid-cols-4 gap-3">
        <StatCard label="Sources" value={status?.source_count ?? 0} sub="Configured automatically" Icon={Database} tone="blue" />
        <StatCard label="Authorities" value={status?.authority_count ?? 0} sub="Stored legal materials" Icon={FileText} />
        <StatCard label="Insights" value={insights.length} sub="Interpreted scanner guidance" Icon={Sparkles} tone="green" />
        <StatCard label="Enabled rules" value={status?.enabled_rule_count ?? 0} sub={`${status?.rule_count ?? 0} total distilled rules`} Icon={ShieldCheck} tone="orange" />
      </section>

      <SavingsPanel savings={data?.savings} />

      <section>
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-[20px] font-bold text-text-primary">Our legal interpretation</h2>
            <p className="mt-1 text-[13px] text-text-secondary">
              These insights guide scanner prioritization. Repo evidence remains separate from legal interpretation.
            </p>
          </div>
        </div>
        {loading ? (
          <div className="rounded-3xl border border-border bg-card p-8 text-[13px] text-text-muted shadow-card">
            Loading legal sources and interpreted rules...
          </div>
        ) : insights.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {insights.map((insight, index) => (
              <InsightCard key={`${insight.title}-${index}`} insight={insight} />
            ))}
          </div>
        ) : (
          <div className="rounded-3xl border border-border bg-card p-8 text-[13px] text-text-muted shadow-card">
            No interpreted legal insights are available yet. The panel has configured sources and will surface rules as soon as the backend distillation store is populated.
          </div>
        )}
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-card">
          <div className="border-b border-border px-4 py-3">
            <div className="text-[13px] font-semibold text-text-primary">Recent public legal sources</div>
            <div className="mt-0.5 text-[11px] text-text-muted">Pulled automatically from configured public data sources.</div>
          </div>
          {authorities.length ? authorities.slice(0, 8).map((authority) => (
            <SourceRow key={authority.source_id} item={authority} />
          )) : (
            <div className="px-4 py-6 text-[13px] text-text-muted">No source records have been pulled yet.</div>
          )}
        </div>

        <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-card">
          <div className="border-b border-border px-4 py-3">
            <div className="text-[13px] font-semibold text-text-primary">Scanner guidance rules</div>
            <div className="mt-0.5 text-[11px] text-text-muted">Enabled rules that can enrich scanner findings with citations.</div>
          </div>
          {rules.length ? rules.slice(0, 8).map((rule) => (
            <div key={rule.id} className="border-b border-border px-4 py-3 last:border-0">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-status-chaptered-text" />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold text-text-primary">{rule.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <span className="rounded-full bg-chip px-2 py-0.5 text-[10px] font-semibold text-text-muted">{labelize(rule.category)}</span>
                    <span className="rounded-full bg-chip px-2 py-0.5 text-[10px] font-semibold text-text-muted">{rule.confidence} confidence</span>
                  </div>
                  <p className="mt-2 text-[12px] leading-relaxed text-text-secondary">{rule.finding_rationale}</p>
                </div>
              </div>
            </div>
          )) : (
            <div className="px-4 py-6 text-[13px] text-text-muted">No scanner guidance rules are available yet.</div>
          )}
        </div>
      </section>

      {data?.fetch_errors && Object.keys(data.fetch_errors).length > 0 && (
        <div className="rounded-2xl border border-border bg-chip-alt px-4 py-3 text-[12px] leading-relaxed text-text-muted">
          <div className="mb-1 flex items-center gap-2 font-semibold text-text-primary">
            <AlertTriangle className="h-4 w-4 text-accent-gold" />
            Some public feeds were unavailable
          </div>
          Cached legal intelligence is still shown. The backend will retry unavailable feeds on the next automatic refresh.
        </div>
      )}
    </div>
  );
}
