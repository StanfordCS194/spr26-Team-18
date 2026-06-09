import { useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronRight, FileText,
  Loader2, ShieldCheck, Upload, X,
} from "lucide-react";

// ── Stage definitions ─────────────────────────────────────────────────────────

const STAGES = [
  { id: "pre_seed", label: "Pre-seed" },
  { id: "seed",     label: "Seed" },
  { id: "series_a", label: "Series A" },
  { id: "series_b", label: "Series B" },
  { id: "series_c_plus", label: "Series C+" },
];

const STAGE_ORDER = STAGES.map((s) => s.id);

// ── Document catalog ──────────────────────────────────────────────────────────
// minStage: earliest stage where this document is relevant.
// maxStage: latest stage (null = no upper bound).
// required: shown as required for that stage.

const DOCUMENT_CATALOG = [
  {
    id: "stock_agreements",
    label: "Stock Purchase Agreements",
    description: "Founder / early-employee restricted stock grant agreements",
    irsRule: "IRC §83(b) — election must be filed within 30 days of grant",
    minStage: "pre_seed",
    maxStage: "seed",
    required: true,
    accept: ".pdf,.doc,.docx",
  },
  {
    id: "safe_convertible_notes",
    label: "SAFE / Convertible Note Agreements",
    description: "SAFEs, convertible notes, or other pre-priced-round instruments",
    irsRule: "ASC 480/815 debt vs. equity classification; IRC §1273 OID accrual on discounted notes",
    minStage: "pre_seed",
    maxStage: "series_a",
    required: false,
    accept: ".pdf",
  },
  {
    id: "contractor_invoices",
    label: "Contractor & Vendor Invoices",
    description: "Payments to independent contractors or service vendors",
    irsRule: "Form 1099-NEC — required for $600+ in annual contractor payments",
    minStage: "pre_seed",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "cap_table",
    label: "Cap Table / Stock Ledger",
    description: "Current and historical ownership records",
    irsRule: "QSBS §1202 eligibility tracking; IRC §382 ownership-change history",
    minStage: "seed",
    maxStage: null,
    required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "payroll_records",
    label: "Payroll Records / W-2s",
    description: "Payroll summaries, W-2s, or Form 941 filings",
    irsRule: "FICA withholding; FUTA/SUTA; Form 941 quarterly deposits via EFTPS",
    minStage: "seed",
    maxStage: null,
    required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "eftps_deposit_records",
    label: "EFTPS / Payroll Tax Deposit Records",
    description: "EFTPS payment history or IRS deposit schedule confirmation",
    irsRule: "IRS deposit schedule (monthly/semiweekly) — FTD penalties 2–15% for late deposits",
    minStage: "seed",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "state_payroll_registrations",
    label: "State Payroll / Tax Registrations",
    description: "State employer registration docs for states where employees are based",
    irsRule: "State income tax nexus — one remote employee creates corporate return + payroll registration obligations",
    minStage: "seed",
    maxStage: null,
    required: false,
    accept: ".pdf",
  },
  {
    id: "valuation_409a",
    label: "409A Valuation Report",
    description: "Independent FMV appraisal for option grants",
    irsRule: "IRC §409A — every option must be granted at FMV; refresh at least annually",
    minStage: "seed",
    maxStage: null,
    required: true,
    accept: ".pdf",
  },
  {
    id: "option_grants",
    label: "Option Grant Agreements",
    description: "ISO and NSO grant documents",
    irsRule: "IRC §409A; §422(d) $100K annual ISO limit per employee",
    minStage: "series_a",
    maxStage: null,
    required: true,
    accept: ".pdf",
  },
  {
    id: "iso_plan",
    label: "Equity Incentive Plan",
    description: "ISO / NSO plan document (e.g. 20XX Stock Plan)",
    irsRule: "IRC §422 qualification; plan terms govern §422(d) $100K cap",
    minStage: "series_a",
    maxStage: null,
    required: true,
    accept: ".pdf",
  },
  {
    id: "severance_agreements",
    label: "Severance Agreements",
    description: "Employee separation and severance pay terms",
    irsRule: "IRC §409A — all non-stock deferred compensation subject to §409A",
    minStage: "series_a",
    maxStage: null,
    required: false,
    accept: ".pdf",
  },
  {
    id: "espp_records",
    label: "ESPP Records",
    description: "Employee Stock Purchase Plan enrollment and purchase records",
    irsRule: "Form 3922 — required for each ESPP stock transfer by January 31",
    minStage: "series_a",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "revenue_records",
    label: "Revenue / Billing Records",
    description: "Sales data, invoices, or billing system exports",
    irsRule: "Post-Wayfair sales tax nexus — ~$100K/state threshold in 45 states + DC",
    minStage: "series_b",
    maxStage: null,
    required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "nol_schedule",
    label: "NOL Schedule",
    description: "Net operating loss carryforward documentation",
    irsRule: "IRC §382 — equity financing ownership changes cap NOL utilization permanently",
    minStage: "series_b",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "rd_expenses",
    label: "R&D Expense Records",
    description: "Qualified research expense (QRE) documentation",
    irsRule: "IRC §41 R&D credit; §174 mandatory 5-year amortization (post-2022)",
    minStage: "series_b",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "rd_174_amortization_schedule",
    label: "IRC §174 Amortization Schedule",
    description: "Tax-basis amortization schedule for capitalized R&D expenditures",
    irsRule: "IRC §174 — post-2022: all R&D must be amortized 5 yrs (domestic) / 15 yrs (foreign); no immediate expensing on tax return",
    minStage: "seed",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "coc_agreements",
    label: "Change-of-Control Agreements",
    description: "M&A provisions and equity acceleration terms",
    irsRule: "IRC §280G — excess parachute payments trigger 20% excise tax on recipient",
    minStage: "series_b",
    maxStage: null,
    required: false,
    accept: ".pdf",
  },
  {
    id: "intercompany_agreements",
    label: "Intercompany / Related-Party Agreements",
    description: "IP licensing, management fees, intercompany loans",
    irsRule: "IRC §482 — arm's-length pricing required; contemporaneous docs mandatory",
    minStage: "series_b",
    maxStage: null,
    required: false,
    accept: ".pdf",
  },
  {
    id: "foreign_bank_statements",
    label: "Foreign Bank Statements",
    description: "Statements for any non-US bank accounts",
    irsRule: "FBAR (FinCEN 114) — required if aggregate balance ever exceeds $10,000",
    minStage: "series_b",
    maxStage: null,
    required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "exec_comp_agreements",
    label: "Executive Compensation Agreements",
    description: "CEO / CFO / named executive officer employment and comp terms",
    irsRule: "IRC §162(m) — $1M tax deduction cap on covered employee compensation",
    minStage: "series_c_plus",
    maxStage: null,
    required: true,
    accept: ".pdf",
  },
  {
    id: "revenue_recognition_policy",
    label: "Revenue Recognition Policy / Schedule",
    description: "ASC 606 policy document or deferred revenue schedules",
    irsRule: "ASC 606 / IRC §451 conformity — five-step model, performance obligations",
    minStage: "series_c_plus",
    maxStage: null,
    required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "debt_agreements",
    label: "Debt / Loan Agreements",
    description: "Credit facilities, venture debt, convertible notes",
    irsRule: "IRC §163(j) — business interest expense limited to 30% of ATI (EBIT basis post-2021)",
    minStage: "series_c_plus",
    maxStage: null,
    required: false,
    accept: ".pdf",
  },
];

function getDocsForStage(stageId) {
  const stageIdx = STAGE_ORDER.indexOf(stageId);
  return DOCUMENT_CATALOG.filter((doc) => {
    const minIdx = STAGE_ORDER.indexOf(doc.minStage);
    const maxIdx = doc.maxStage ? STAGE_ORDER.indexOf(doc.maxStage) : STAGE_ORDER.length - 1;
    return stageIdx >= minIdx && stageIdx <= maxIdx;
  });
}

// ── Risk display helpers ──────────────────────────────────────────────────────

const RISK_TEXT  = { Low: "text-green-600", Moderate: "text-orange-500", High: "text-red-600", Unknown: "text-text-muted" };
const RISK_BADGE = { Low: "border-green-200 bg-green-50", Moderate: "border-orange-200 bg-orange-50", High: "border-red-200 bg-red-50", Unknown: "border-border bg-chip-alt" };
const SEV_BADGE  = { high: "bg-red-50 text-red-700 border-red-200", medium: "bg-orange-50 text-orange-700 border-orange-200", low: "bg-green-50 text-green-700 border-green-200" };

// ── Component ─────────────────────────────────────────────────────────────────

export default function FinancialCompliance() {
  const [step, setStep] = useState(1);          // 1=setup, 2=docs, 3=results
  const [companyName, setCompanyName] = useState("");
  const [selectedStage, setSelectedStage] = useState(null);
  const [uploads, setUploads] = useState({});   // { docId: File }
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRefs = useRef({});

  const stageDocs  = selectedStage ? getDocsForStage(selectedStage) : [];
  const requiredIds = stageDocs.filter((d) => d.required).map((d) => d.id);
  const uploadedIds = Object.keys(uploads);
  const missingRequired = requiredIds.filter((id) => !uploadedIds.includes(id));
  const canScan = uploadedIds.length > 0;

  function handleFileChange(docId, file) {
    if (file) {
      setUploads((prev) => ({ ...prev, [docId]: file }));
    }
  }

  function removeUpload(docId) {
    setUploads((prev) => {
      const next = { ...prev };
      delete next[docId];
      return next;
    });
    if (fileRefs.current[docId]) fileRefs.current[docId].value = "";
  }

  async function runScan() {
    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    if (companyName.trim()) fd.append("company_name", companyName.trim());
    fd.append("funding_round", selectedStage);

    const docTypes = [];
    for (const [docId, file] of Object.entries(uploads)) {
      fd.append("files", file);
      const meta = DOCUMENT_CATALOG.find((d) => d.id === docId);
      docTypes.push(meta ? meta.label : docId);
    }
    fd.append("document_types", JSON.stringify(docTypes));

    try {
      const r = await fetch("/api/compliance/audit", { method: "POST", body: fd });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(detail.detail || `HTTP ${r.status}`);
      }
      setResult(await r.json());
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep(1);
    setCompanyName("");
    setSelectedStage(null);
    setUploads({});
    setResult(null);
    setError(null);
    fileRefs.current = {};
  }

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-text-secondary">
          <ShieldCheck className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">IRS Compliance · prototype</span>
        </div>
        <h1 className="text-[32px] font-bold tracking-tight">Financial compliance audit.</h1>
        <p className="max-w-[600px] text-[14px] leading-relaxed text-text-secondary">
          Upload your financial documents — cap table, payroll records, option grants, and
          more — to get a stage-specific IRS compliance risk assessment. Not a substitute
          for professional tax advice.
        </p>
      </header>

      {/* Step indicator */}
      {step < 3 && (
        <div className="flex items-center gap-2">
          {["Company setup", "Upload documents", "Results"].map((label, i) => {
            const n = i + 1;
            const active = n === step;
            const done = n < step;
            return (
              <div key={n} className="flex items-center gap-2">
                <div className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold transition-colors
                  ${done ? "bg-action-dark text-text-invert" : active ? "bg-action-dark/10 text-action-dark ring-1 ring-action-dark" : "bg-chip text-text-muted"}`}>
                  {done ? <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2.5} /> : n}
                </div>
                <span className={`text-[12px] font-medium ${active ? "text-text-primary" : "text-text-muted"}`}>{label}</span>
                {i < 2 && <ChevronRight className="h-3.5 w-3.5 text-text-muted" />}
              </div>
            );
          })}
        </div>
      )}

      {/* Step 1 — Company setup */}
      {step === 1 && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-card space-y-6">
          <h3 className="text-[18px] font-bold tracking-tight">Tell us about your company</h3>

          <div className="space-y-2">
            <label className="text-[12px] font-medium uppercase tracking-[0.14em] text-text-muted">
              Company name <span className="normal-case text-text-muted font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Corp"
              className="w-full rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
            />
          </div>

          <div className="space-y-3">
            <label className="text-[12px] font-medium uppercase tracking-[0.14em] text-text-muted">
              Funding stage <span className="text-red-500">*</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {STAGES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedStage(s.id)}
                  className={`rounded-full border px-4 py-1.5 text-[13px] font-semibold transition-all
                    ${selectedStage === s.id
                      ? "border-action-dark bg-action-dark text-text-invert shadow-card"
                      : "border-border bg-card text-text-secondary hover:border-action-dark hover:text-text-primary"
                    }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            {selectedStage && (
              <p className="text-[12px] text-text-secondary">
                We&apos;ll ask for the {getDocsForStage(selectedStage).length} documents most relevant to a&nbsp;
                <span className="font-semibold text-text-primary">
                  {STAGES.find((s) => s.id === selectedStage)?.label}
                </span>{" "}
                company.
              </p>
            )}
          </div>

          <div className="flex justify-end">
            <button
              disabled={!selectedStage}
              onClick={() => setStep(2)}
              className="flex items-center gap-2 rounded-full bg-action-dark px-5 py-2 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90 disabled:opacity-40"
            >
              Continue
              <ChevronRight className="h-3.5 w-3.5" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — Document upload */}
      {step === 2 && selectedStage && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-card">
            <div className="mb-1 flex items-center justify-between">
              <h3 className="text-[18px] font-bold tracking-tight">
                Upload your {STAGES.find((s) => s.id === selectedStage)?.label} documents
              </h3>
              <button
                onClick={() => setStep(1)}
                className="text-[12px] text-text-muted hover:text-text-primary"
              >
                ← Change stage
              </button>
            </div>
            <p className="mb-5 text-[13px] text-text-secondary">
              Upload as many documents as possible for the most accurate scan.
              Documents marked <span className="font-semibold text-text-primary">Required</span> are
              needed to evaluate critical IRS compliance areas for your stage.
            </p>

            <div className="space-y-3">
              {stageDocs.map((doc) => {
                const uploaded = uploads[doc.id];
                return (
                  <DocumentRow
                    key={doc.id}
                    doc={doc}
                    uploaded={uploaded}
                    fileRef={(el) => { fileRefs.current[doc.id] = el; }}
                    onFileChange={(file) => handleFileChange(doc.id, file)}
                    onRemove={() => removeUpload(doc.id)}
                  />
                );
              })}
            </div>
          </div>

          {/* Upload summary + action */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <div className="text-[13px] font-semibold text-text-primary">
                  {uploadedIds.length} of {stageDocs.length} documents uploaded
                </div>
                {missingRequired.length > 0 ? (
                  <div className="text-[12px] text-orange-600">
                    {missingRequired.length} required document{missingRequired.length !== 1 ? "s" : ""} still missing —
                    scan may be incomplete
                  </div>
                ) : (
                  <div className="text-[12px] text-green-600">All required documents uploaded</div>
                )}
              </div>
              <button
                disabled={!canScan || loading}
                onClick={runScan}
                className="flex items-center gap-2 rounded-full bg-action-dark px-5 py-2 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90 disabled:opacity-40"
              >
                {loading
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <ShieldCheck className="h-3.5 w-3.5" strokeWidth={2.4} />}
                {loading ? "Analyzing…" : "Run compliance scan"}
              </button>
            </div>

            {error && (
              <div className="mt-3 rounded-xl border border-status-committee-bg bg-status-committee-bg/40 px-4 py-2 text-[12px] text-status-committee-text">
                {error}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 3 — Results */}
      {step === 3 && result && (
        <AuditResult result={result} onReset={reset} />
      )}
    </section>
  );
}

// ── DocumentRow ───────────────────────────────────────────────────────────────

function DocumentRow({ doc, uploaded, fileRef, onFileChange, onRemove }) {
  return (
    <div className={`flex items-start gap-3 rounded-xl border p-4 transition-colors
      ${uploaded ? "border-green-200 bg-green-50/40" : "border-border bg-chip-alt/30 hover:border-border-muted"}`}
    >
      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-chip">
        <FileText className="h-4 w-4 text-text-secondary" strokeWidth={2} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-semibold text-text-primary">{doc.label}</span>
          {doc.required && (
            <span className="rounded-full bg-action-dark/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-action-dark">
              Required
            </span>
          )}
          {uploaded && (
            <span className="rounded-full border border-green-200 bg-green-50 px-2 py-0.5 text-[10px] font-semibold text-green-700">
              ✓ Uploaded
            </span>
          )}
        </div>
        <p className="mt-0.5 text-[12px] text-text-secondary">{doc.description}</p>
        <p className="mt-0.5 text-[11px] text-text-muted">
          <span className="font-medium text-text-secondary">IRS note: </span>{doc.irsRule}
        </p>

        {uploaded ? (
          <div className="mt-2 flex items-center gap-2">
            <span className="max-w-[220px] truncate text-[12px] text-text-secondary">{uploaded.name}</span>
            <button
              type="button"
              onClick={onRemove}
              className="flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-0.5 text-[11px] text-text-muted hover:text-red-600 hover:border-red-200"
            >
              <X className="h-3 w-3" strokeWidth={2.5} /> Remove
            </button>
          </div>
        ) : (
          <label className="mt-2 inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-[12px] font-medium text-text-secondary hover:border-action-dark hover:text-text-primary">
            <Upload className="h-3.5 w-3.5" strokeWidth={2.4} />
            Upload file
            <input
              ref={fileRef}
              type="file"
              accept={doc.accept}
              onChange={(e) => onFileChange(e.target.files?.[0] || null)}
              className="hidden"
            />
          </label>
        )}
      </div>
    </div>
  );
}

// ── AuditResult ───────────────────────────────────────────────────────────────

function AuditResult({ result, onReset }) {
  const risk   = result.overall_risk || "Unknown";
  const score  = result.risk_score;
  const issues = result.issues || [];
  const notes  = result.notes || [];
  const stage  = result.stage;

  const high   = issues.filter((i) => i.severity === "high");
  const medium = issues.filter((i) => i.severity === "medium");
  const low    = issues.filter((i) => i.severity === "low" || !i.severity);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className={`flex items-center gap-2 rounded-full border px-4 py-1.5 text-[14px] font-semibold ${RISK_BADGE[risk] || RISK_BADGE.Unknown}`}>
          {risk === "High"
            ? <AlertTriangle className={`h-4 w-4 ${RISK_TEXT[risk]}`} strokeWidth={2.4} />
            : <ShieldCheck className={`h-4 w-4 ${RISK_TEXT[risk]}`} strokeWidth={2.4} />}
          <span className={RISK_TEXT[risk]}>{risk} risk</span>
          {score != null && <span className="font-normal text-text-muted">· score {score}/100</span>}
          {stage && <span className="font-normal text-text-muted">· {stage}</span>}
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card hover:text-text-primary"
        >
          <X className="h-3.5 w-3.5" strokeWidth={2.4} />
          New scan
        </button>
      </div>

      {/* Summary */}
      <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">Summary</div>
        <p className="text-[14px] leading-relaxed text-text-primary">{result.summary}</p>
      </div>

      {/* Findings by severity */}
      {issues.length > 0 ? (
        <div className="space-y-4">
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            {issues.length} compliance issue{issues.length !== 1 ? "s" : ""} identified
          </div>
          {[
            { label: "High severity", items: high, color: "text-red-600", dot: "bg-red-500" },
            { label: "Medium severity", items: medium, color: "text-orange-600", dot: "bg-orange-400" },
            { label: "Low severity", items: low, color: "text-green-700", dot: "bg-green-500" },
          ].map(({ label, items, color, dot }) =>
            items.length > 0 ? (
              <div key={label} className="space-y-2">
                <div className={`flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide ${color}`}>
                  <span className={`h-2 w-2 rounded-full ${dot}`} />
                  {label} · {items.length}
                </div>
                {items.map((issue, i) => (
                  <IssueCard key={i} issue={issue} />
                ))}
              </div>
            ) : null
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-green-200 bg-green-50 p-5 text-[13px] text-green-700">
          No IRS compliance issues were identified in the provided documents.
        </div>
      )}

      {/* Notes */}
      {notes.length > 0 && (
        <div className="rounded-2xl border border-border-muted bg-chip-alt p-4">
          <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">Notes</div>
          <ul className="space-y-1">
            {notes.map((note, i) => (
              <li key={i} className="text-[12px] text-text-secondary">· {note}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[11px] text-text-muted">
        This audit is a prototype and not a substitute for professional tax or legal advice.
        Review results with an IRS compliance specialist.
      </p>
    </div>
  );
}

function IssueCard({ issue }) {
  const [open, setOpen] = useState(false);
  const sev = issue.severity || "low";
  return (
    <button
      type="button"
      onClick={() => setOpen((o) => !o)}
      className="w-full rounded-2xl border border-border bg-card p-5 shadow-card text-left transition-shadow hover:shadow-card-hover"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="rounded-full bg-chip px-2.5 py-0.5 text-[11px] font-medium text-text-secondary">
              {issue.area}
            </span>
            {issue.irc_section && issue.irc_section !== "N/A" && (
              <span className="rounded-full border border-border px-2.5 py-0.5 text-[11px] font-mono text-text-muted">
                {issue.irc_section}
              </span>
            )}
            <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${SEV_BADGE[sev] || SEV_BADGE.low}`}>
              {sev}
            </span>
          </div>
          <p className="text-[13px] leading-relaxed text-text-primary">{issue.finding}</p>
        </div>
        <ChevronRight className={`h-4 w-4 flex-shrink-0 text-text-muted transition-transform ${open ? "rotate-90" : ""}`} />
      </div>
      {open && (
        <div className="mt-3 rounded-xl border border-border bg-chip-alt px-4 py-3 text-left">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-1">
            Recommended action
          </div>
          <p className="text-[12px] text-text-secondary">{issue.recommendation}</p>
        </div>
      )}
    </button>
  );
}
