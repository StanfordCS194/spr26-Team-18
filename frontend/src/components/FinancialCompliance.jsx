import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronRight, FileText,
  Globe, Loader2, MapPin, ShieldCheck, Upload, X,
} from "lucide-react";

// ── Constants ─────────────────────────────────────────────────────────────────

const STAGES = [
  { id: "pre_seed",     label: "Pre-seed" },
  { id: "seed",         label: "Seed" },
  { id: "series_a",     label: "Series A" },
  { id: "series_b",     label: "Series B" },
  { id: "series_c_plus",label: "Series C+" },
];

const ENTITY_TYPES = [
  { id: "c_corp", label: "C-Corp",        hint: "Standard for VC-backed startups" },
  { id: "s_corp", label: "S-Corp",        hint: "Pass-through, max 100 shareholders" },
  { id: "llc",    label: "LLC",           hint: "Flexible structure, tax elections vary" },
  { id: "other",  label: "Other / Unsure",hint: "" },
];

const COMPANY_SIZES = [
  { id: "1_10",    label: "1–10" },
  { id: "11_50",   label: "11–50" },
  { id: "51_200",  label: "51–200" },
  { id: "200_plus",label: "200+" },
];

const INDUSTRIES = [
  { id: "saas",      label: "SaaS / Software" },
  { id: "fintech",   label: "Fintech" },
  { id: "hardware",  label: "Hardware / IoT" },
  { id: "biotech",   label: "Biotech / Life Sciences" },
  { id: "ecommerce", label: "E-commerce" },
  { id: "other",     label: "Other" },
];

const US_STATES = [
  { code: "AL", name: "Alabama" },       { code: "AK", name: "Alaska" },
  { code: "AZ", name: "Arizona" },       { code: "AR", name: "Arkansas" },
  { code: "CA", name: "California" },    { code: "CO", name: "Colorado" },
  { code: "CT", name: "Connecticut" },   { code: "DE", name: "Delaware" },
  { code: "DC", name: "Washington D.C."},{ code: "FL", name: "Florida" },
  { code: "GA", name: "Georgia" },       { code: "HI", name: "Hawaii" },
  { code: "ID", name: "Idaho" },         { code: "IL", name: "Illinois" },
  { code: "IN", name: "Indiana" },       { code: "IA", name: "Iowa" },
  { code: "KS", name: "Kansas" },        { code: "KY", name: "Kentucky" },
  { code: "LA", name: "Louisiana" },     { code: "ME", name: "Maine" },
  { code: "MD", name: "Maryland" },      { code: "MA", name: "Massachusetts" },
  { code: "MI", name: "Michigan" },      { code: "MN", name: "Minnesota" },
  { code: "MS", name: "Mississippi" },   { code: "MO", name: "Missouri" },
  { code: "MT", name: "Montana" },       { code: "NE", name: "Nebraska" },
  { code: "NV", name: "Nevada" },        { code: "NH", name: "New Hampshire" },
  { code: "NJ", name: "New Jersey" },    { code: "NM", name: "New Mexico" },
  { code: "NY", name: "New York" },      { code: "NC", name: "North Carolina" },
  { code: "ND", name: "North Dakota" },  { code: "OH", name: "Ohio" },
  { code: "OK", name: "Oklahoma" },      { code: "OR", name: "Oregon" },
  { code: "PA", name: "Pennsylvania" },  { code: "RI", name: "Rhode Island" },
  { code: "SC", name: "South Carolina" },{ code: "SD", name: "South Dakota" },
  { code: "TN", name: "Tennessee" },     { code: "TX", name: "Texas" },
  { code: "UT", name: "Utah" },          { code: "VT", name: "Vermont" },
  { code: "VA", name: "Virginia" },      { code: "WA", name: "Washington" },
  { code: "WV", name: "West Virginia" }, { code: "WI", name: "Wisconsin" },
  { code: "WY", name: "Wyoming" },
];

const STAGE_ORDER = STAGES.map((s) => s.id);

// ── Document catalog ──────────────────────────────────────────────────────────

const DOCUMENT_CATALOG = [
  {
    id: "stock_agreements",
    label: "Stock Purchase Agreements",
    description: "Founder / early-employee restricted stock grant agreements",
    irsRule: "IRC §83(b) — election must be filed within 30 days of grant",
    minStage: "pre_seed", maxStage: "seed", required: true,
    accept: ".pdf,.doc,.docx",
  },
  {
    id: "safe_convertible_notes",
    label: "SAFE / Convertible Note Agreements",
    description: "SAFEs, convertible notes, or other pre-priced-round instruments",
    irsRule: "ASC 480/815 debt vs. equity classification; IRC §1273 OID accrual",
    minStage: "pre_seed", maxStage: "series_a", required: false,
    accept: ".pdf",
  },
  {
    id: "contractor_invoices",
    label: "Contractor & Vendor Invoices",
    description: "Payments to independent contractors or service vendors",
    irsRule: "Form 1099-NEC — required for $600+ in annual contractor payments",
    minStage: "pre_seed", maxStage: null, required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "cap_table",
    label: "Cap Table / Stock Ledger",
    description: "Current and historical ownership records",
    irsRule: "QSBS §1202 eligibility tracking; IRC §382 ownership-change history",
    minStage: "seed", maxStage: null, required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "payroll_records",
    label: "Payroll Records / W-2s",
    description: "Payroll summaries, W-2s, or Form 941 filings",
    irsRule: "FICA withholding; FUTA/SUTA; Form 941 quarterly deposits via EFTPS",
    minStage: "seed", maxStage: null, required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "eftps_deposit_records",
    label: "EFTPS / Payroll Tax Deposit Records",
    description: "EFTPS payment history or IRS deposit schedule confirmation",
    irsRule: "IRS deposit schedule (monthly/semiweekly) — FTD penalties 2–15%",
    minStage: "seed", maxStage: null, required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "state_payroll_registrations",
    label: "State Payroll / Tax Registrations",
    description: "State employer registration docs for each state with employees",
    irsRule: "State income tax nexus — one remote employee creates corporate return + payroll registration obligations",
    minStage: "seed", maxStage: null, required: false,
    requiresMultiState: true,
    accept: ".pdf",
  },
  {
    id: "valuation_409a",
    label: "409A Valuation Report",
    description: "Independent FMV appraisal for option grants",
    irsRule: "IRC §409A — every option must be granted at FMV; refresh at least annually",
    minStage: "seed", maxStage: null, required: true,
    accept: ".pdf",
  },
  {
    id: "rd_174_amortization_schedule",
    label: "IRC §174 Amortization Schedule",
    description: "Tax-basis amortization schedule for capitalized R&D expenditures",
    irsRule: "IRC §174 — post-2022: R&D must be amortized 5 yrs (domestic) / 15 yrs (foreign)",
    minStage: "seed", maxStage: null, required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "option_grants",
    label: "Option Grant Agreements",
    description: "ISO and NSO grant documents",
    irsRule: "IRC §409A; §422(d) $100K annual ISO limit per employee",
    minStage: "series_a", maxStage: null, required: true,
    accept: ".pdf",
  },
  {
    id: "iso_plan",
    label: "Equity Incentive Plan",
    description: "ISO / NSO plan document (e.g. 20XX Stock Plan)",
    irsRule: "IRC §422 qualification; plan terms govern §422(d) $100K cap",
    minStage: "series_a", maxStage: null, required: true,
    accept: ".pdf",
  },
  {
    id: "severance_agreements",
    label: "Severance Agreements",
    description: "Employee separation and severance pay terms",
    irsRule: "IRC §409A — all non-stock deferred compensation subject to §409A",
    minStage: "series_a", maxStage: null, required: false,
    accept: ".pdf",
  },
  {
    id: "espp_records",
    label: "ESPP Records",
    description: "Employee Stock Purchase Plan enrollment and purchase records",
    irsRule: "Form 3922 — required for each ESPP stock transfer by January 31",
    minStage: "series_a", maxStage: null, required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "revenue_records",
    label: "Revenue / Billing Records",
    description: "Sales data, invoices, or billing system exports",
    irsRule: "Post-Wayfair sales tax nexus — ~$100K/state threshold in 45 states + DC",
    minStage: "series_b", maxStage: null, required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "nol_schedule",
    label: "NOL Schedule",
    description: "Net operating loss carryforward documentation",
    irsRule: "IRC §382 — equity financing ownership changes cap NOL utilization permanently",
    minStage: "series_b", maxStage: null, required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "rd_expenses",
    label: "R&D Expense Records",
    description: "Qualified research expense (QRE) documentation",
    irsRule: "IRC §41 R&D credit; §174 mandatory 5-year amortization (post-2022)",
    minStage: "series_b", maxStage: null, required: false,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "coc_agreements",
    label: "Change-of-Control Agreements",
    description: "M&A provisions and equity acceleration terms",
    irsRule: "IRC §280G — excess parachute payments trigger 20% excise tax on recipient",
    minStage: "series_b", maxStage: null, required: false,
    accept: ".pdf",
  },
  {
    id: "intercompany_agreements",
    label: "Intercompany / Related-Party Agreements",
    description: "IP licensing, management fees, intercompany loans",
    irsRule: "IRC §482 — arm's-length pricing required; contemporaneous docs mandatory",
    minStage: "series_b", maxStage: null, required: false,
    requiresInternational: true,
    accept: ".pdf",
  },
  {
    id: "foreign_bank_statements",
    label: "Foreign Bank Statements",
    description: "Statements for any non-US bank accounts",
    irsRule: "FBAR (FinCEN 114) — required if aggregate balance ever exceeds $10,000",
    minStage: "series_b", maxStage: null, required: false,
    requiresInternational: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "exec_comp_agreements",
    label: "Executive Compensation Agreements",
    description: "CEO / CFO / named executive officer employment and comp terms",
    irsRule: "IRC §162(m) — $1M tax deduction cap on covered employee compensation",
    minStage: "series_c_plus", maxStage: null, required: true,
    accept: ".pdf",
  },
  {
    id: "revenue_recognition_policy",
    label: "Revenue Recognition Policy / Schedule",
    description: "ASC 606 policy document or deferred revenue schedules",
    irsRule: "ASC 606 / IRC §451 conformity — five-step model, performance obligations",
    minStage: "series_c_plus", maxStage: null, required: true,
    accept: ".pdf,.csv,.xlsx",
  },
  {
    id: "debt_agreements",
    label: "Debt / Loan Agreements",
    description: "Credit facilities, venture debt, convertible notes",
    irsRule: "IRC §163(j) — business interest expense limited to 30% of ATI (EBIT basis post-2021)",
    minStage: "series_c_plus", maxStage: null, required: false,
    accept: ".pdf",
  },
];

function getDocsForContext({ stage, international, employeeStates, incorporationState }) {
  const stageIdx = STAGE_ORDER.indexOf(stage);
  const allStateCodes = [...new Set([incorporationState, ...employeeStates].filter(Boolean))];
  const multiState = allStateCodes.length > 1;

  return DOCUMENT_CATALOG.filter((doc) => {
    const minIdx = STAGE_ORDER.indexOf(doc.minStage);
    const maxIdx = doc.maxStage ? STAGE_ORDER.indexOf(doc.maxStage) : STAGE_ORDER.length - 1;
    if (stageIdx < minIdx || stageIdx > maxIdx) return false;
    if (doc.requiresInternational && international !== "yes") return false;
    if (doc.requiresMultiState && !multiState) return false;
    return true;
  });
}

// ── Risk display helpers ──────────────────────────────────────────────────────

const RISK_TEXT  = { Low: "text-green-600", Moderate: "text-orange-500", High: "text-red-600", Unknown: "text-text-muted" };
const RISK_BADGE = { Low: "border-green-200 bg-green-50", Moderate: "border-orange-200 bg-orange-50", High: "border-red-200 bg-red-50", Unknown: "border-border bg-chip-alt" };
const SEV_BADGE  = { high: "bg-red-50 text-red-700 border-red-200", medium: "bg-orange-50 text-orange-700 border-orange-200", low: "bg-green-50 text-green-700 border-green-200" };

// ── Step indicator ────────────────────────────────────────────────────────────

const STEP_LABELS = ["Company profile", "Operations", "Upload documents"];

function StepIndicator({ step }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {STEP_LABELS.map((label, i) => {
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
            {i < STEP_LABELS.length - 1 && <ChevronRight className="h-3.5 w-3.5 text-text-muted" />}
          </div>
        );
      })}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function FinancialCompliance() {
  // Step 1 — profile
  const [companyName,   setCompanyName]   = useState("");
  const [entityType,    setEntityType]    = useState(null);
  const [selectedStage, setSelectedStage] = useState(null);
  const [companySize,   setCompanySize]   = useState(null);
  const [industry,      setIndustry]      = useState(null);
  const [otherIndustry, setOtherIndustry] = useState("");

  // Step 2 — operations
  const [incorporationState, setIncorporationState] = useState("");
  const [employeeStates,     setEmployeeStates]     = useState([]);
  const [international,      setInternational]      = useState(null); // "yes" | "no"

  // Step 3 — documents
  const [uploads, setUploads] = useState({});
  const fileRefs = useRef({});

  // Shared
  const [step,    setStep]    = useState(1);
  const [loading, setLoading] = useState(false);
  const [result,  setResult]  = useState(null);
  const [error,   setError]   = useState(null);

  // Computed
  const canStep2 = entityType && selectedStage && companySize && industry;
  const canStep3 = incorporationState && international !== null;

  const ctx = {
    stage: selectedStage,
    international,
    employeeStates,
    incorporationState,
  };
  const docs       = selectedStage ? getDocsForContext(ctx) : [];
  const uploadedIds = Object.keys(uploads);
  const requiredMissing = docs.filter((d) => d.required && !uploads[d.id]);
  const canScan = uploadedIds.length > 0;

  function handleFileChange(docId, file) {
    if (file) setUploads((p) => ({ ...p, [docId]: file }));
  }

  function removeUpload(docId) {
    setUploads((p) => { const n = { ...p }; delete n[docId]; return n; });
    if (fileRefs.current[docId]) fileRefs.current[docId].value = "";
  }

  async function runScan() {
    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    if (companyName.trim()) fd.append("company_name", companyName.trim());
    fd.append("funding_round", selectedStage);
    fd.append("entity_type", entityType);
    fd.append("company_size", companySize);
    fd.append("industry", industry === "other" && otherIndustry.trim() ? otherIndustry.trim() : industry);
    fd.append("international_presence", international);

    const allStates = [...new Set([incorporationState, ...employeeStates].filter(Boolean))];
    fd.append("operating_states", JSON.stringify(allStates));

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
      setStep(4);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep(1);
    setCompanyName(""); setEntityType(null); setSelectedStage(null);
    setCompanySize(null); setIndustry(null); setOtherIndustry("");
    setIncorporationState(""); setEmployeeStates([]); setInternational(null);
    setUploads({}); setResult(null); setError(null);
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
          Answer a few questions about your company, then upload your financial documents
          to get a stage-specific IRS compliance risk assessment. Not a substitute for
          professional tax advice.
        </p>
      </header>

      {step < 4 && <StepIndicator step={step} />}

      {/* ── Step 1: Company profile ── */}
      {step === 1 && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-card space-y-7">
          <div>
            <h3 className="text-[18px] font-bold tracking-tight">Tell us about your company</h3>
            <p className="mt-1 text-[13px] text-text-secondary">
              This helps us show only the compliance rules that apply to your situation.
            </p>
          </div>

          {/* Company name */}
          <Field label="Company name" hint="Optional" required={false}>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Corp"
              className="w-full rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
            />
          </Field>

          {/* Entity type */}
          <Field label="Entity type" hint="Determines QSBS eligibility, S-Corp restrictions, and tax treatment" required>
            <div className="flex flex-wrap gap-2">
              {ENTITY_TYPES.map((e) => (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => setEntityType(e.id)}
                  className={pill(entityType === e.id)}
                >
                  <span>{e.label}</span>
                  {e.hint && <span className={`block text-[10px] font-normal mt-0.5 ${entityType === e.id ? "text-text-invert/70" : "text-text-muted"}`}>{e.hint}</span>}
                </button>
              ))}
            </div>
          </Field>

          {/* Funding stage */}
          <Field label="Funding stage" hint="Unlocks stage-specific IRS compliance rules" required>
            <div className="flex flex-wrap gap-2">
              {STAGES.map((s) => (
                <button key={s.id} type="button" onClick={() => setSelectedStage(s.id)} className={pill(selectedStage === s.id)}>
                  {s.label}
                </button>
              ))}
            </div>
          </Field>

          {/* Company size */}
          <Field label="Team size" hint="Affects payroll deposit schedules and filing thresholds" required>
            <div className="flex flex-wrap gap-2">
              {COMPANY_SIZES.map((s) => (
                <button key={s.id} type="button" onClick={() => setCompanySize(s.id)} className={pill(companySize === s.id)}>
                  {s.label} <span className={`text-[11px] font-normal ${companySize === s.id ? "text-text-invert/70" : "text-text-muted"}`}>employees</span>
                </button>
              ))}
            </div>
          </Field>

          {/* Industry */}
          <Field label="Primary industry" hint="Contextualizes revenue recognition, R&D, and sector-specific rules" required>
            <div className="flex flex-wrap gap-2">
              {INDUSTRIES.map((ind) => (
                <button key={ind.id} type="button" onClick={() => setIndustry(ind.id)} className={pill(industry === ind.id)}>
                  {ind.label}
                </button>
              ))}
            </div>
            {industry === "other" && (
              <input
                type="text"
                value={otherIndustry}
                onChange={(e) => setOtherIndustry(e.target.value)}
                placeholder="Describe your industry (e.g. Climate tech, Robotics…)"
                className="mt-2 w-full rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
              />
            )}
          </Field>

          <div className="flex justify-end pt-1">
            <button
              disabled={!canStep2}
              onClick={() => setStep(2)}
              className={cta(!canStep2)}
            >
              Continue <ChevronRight className="h-3.5 w-3.5" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Operations ── */}
      {step === 2 && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-card space-y-7">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-[18px] font-bold tracking-tight">Where do you operate?</h3>
              <p className="mt-1 text-[13px] text-text-secondary">
                Used to identify state income tax nexus, payroll registration, and international reporting obligations.
              </p>
            </div>
            <button onClick={() => setStep(1)} className="text-[12px] text-text-muted hover:text-text-primary whitespace-nowrap">← Back</button>
          </div>

          {/* Incorporation state */}
          <Field label="State of incorporation" hint="Your legal home state for corporate returns" required>
            <select
              value={incorporationState}
              onChange={(e) => setIncorporationState(e.target.value)}
              className="w-full rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary focus:border-action-dark focus:outline-none"
            >
              <option value="">Select a state…</option>
              <option value="DE">Delaware — most common for VC-backed startups</option>
              <option value="CA">California</option>
              <option value="NY">New York</option>
              <option value="TX">Texas</option>
              <option disabled>──────────────</option>
              {US_STATES.filter(s => !["DE","CA","NY","TX"].includes(s.code)).map((s) => (
                <option key={s.code} value={s.code}>{s.name}</option>
              ))}
            </select>
          </Field>

          {/* Employee states */}
          <Field
            label="States where employees or remote workers are based"
            hint="Each state with employees creates a corporate tax nexus and payroll registration obligation"
            required={false}
          >
            <StateMultiSelect
              selected={employeeStates}
              onChange={setEmployeeStates}
              excludeCode={incorporationState}
            />
            {employeeStates.length === 0 && (
              <p className="mt-1.5 text-[11px] text-text-muted">Leave blank if all employees are in your incorporation state.</p>
            )}
          </Field>

          {/* International */}
          <Field
            label="Do you have operations or bank accounts outside the US?"
            hint="Triggers FBAR, GILTI §951A, and IRC §482 transfer pricing rules"
            required
          >
            <div className="flex gap-2">
              {[{ id: "no", label: "No — US only" }, { id: "yes", label: "Yes — international" }].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setInternational(opt.id)}
                  className={pill(international === opt.id)}
                >
                  {opt.id === "yes" && <Globe className={`h-3.5 w-3.5 ${international === "yes" ? "text-text-invert" : "text-text-muted"}`} strokeWidth={2.4} />}
                  {opt.label}
                </button>
              ))}
            </div>
          </Field>

          <div className="flex justify-between pt-1">
            <button onClick={() => setStep(1)} className="text-[13px] text-text-secondary hover:text-text-primary">← Back</button>
            <button disabled={!canStep3} onClick={() => setStep(3)} className={cta(!canStep3)}>
              Continue <ChevronRight className="h-3.5 w-3.5" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Documents ── */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-card">
            <div className="mb-1 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-[18px] font-bold tracking-tight">Upload your documents</h3>
                <p className="mt-1 text-[13px] text-text-secondary">
                  We&apos;ve filtered this list to the {docs.length} documents most relevant to a{" "}
                  <strong>{STAGES.find(s => s.id === selectedStage)?.label}</strong>{" "}
                  {ENTITY_TYPES.find(e => e.id === entityType)?.label}{" "}
                  {international === "yes" ? "with international operations" : "operating in the US"}.
                  Upload as many as possible for the most accurate scan.
                </p>
              </div>
              <button onClick={() => setStep(2)} className="text-[12px] text-text-muted hover:text-text-primary whitespace-nowrap">← Back</button>
            </div>

            {/* Context summary chips */}
            <div className="mt-3 mb-5 flex flex-wrap gap-1.5">
              {[
                STAGES.find(s => s.id === selectedStage)?.label,
                ENTITY_TYPES.find(e => e.id === entityType)?.label,
                COMPANY_SIZES.find(s => s.id === companySize)?.label + " employees",
                incorporationState && `Inc. in ${US_STATES.find(s => s.code === incorporationState)?.name || incorporationState}`,
                employeeStates.length > 0 && `${employeeStates.length} remote state${employeeStates.length > 1 ? "s" : ""}`,
                international === "yes" && "International",
              ].filter(Boolean).map((tag) => (
                <span key={tag} className="rounded-full border border-border bg-chip px-2.5 py-0.5 text-[11px] text-text-secondary">{tag}</span>
              ))}
            </div>

            <div className="space-y-3">
              {docs.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  uploaded={uploads[doc.id]}
                  fileRef={(el) => { fileRefs.current[doc.id] = el; }}
                  onFileChange={(file) => handleFileChange(doc.id, file)}
                  onRemove={() => removeUpload(doc.id)}
                />
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-[13px] font-semibold text-text-primary">
                  {uploadedIds.length} of {docs.length} documents uploaded
                </div>
                {requiredMissing.length > 0 ? (
                  <div className="text-[12px] text-orange-600 mt-0.5">
                    {requiredMissing.length} required document{requiredMissing.length !== 1 ? "s" : ""} missing — scan may be incomplete
                  </div>
                ) : uploadedIds.length > 0 ? (
                  <div className="text-[12px] text-green-600 mt-0.5">All required documents uploaded</div>
                ) : (
                  <div className="text-[12px] text-text-muted mt-0.5">Upload at least one document to run the scan</div>
                )}
              </div>
              <button disabled={!canScan || loading} onClick={runScan} className={cta(!canScan || loading)}>
                {loading
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <ShieldCheck className="h-3.5 w-3.5" strokeWidth={2.4} />}
                {loading ? "Analyzing…" : "Run compliance scan"}
              </button>
            </div>
            {error && (
              <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-[12px] text-red-700">
                {error}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Step 4: Results ── */}
      {step === 4 && result && (
        <AuditResult result={result} onReset={reset} />
      )}
    </section>
  );
}

// ── Shared style helpers ──────────────────────────────────────────────────────

function pill(active) {
  return `flex flex-col items-start rounded-xl border px-4 py-2 text-[13px] font-semibold text-left transition-all
    ${active
      ? "border-action-dark bg-action-dark text-text-invert shadow-card"
      : "border-border bg-card text-text-secondary hover:border-action-dark hover:text-text-primary"}`;
}

function cta(disabled) {
  return `flex items-center gap-2 rounded-full bg-action-dark px-5 py-2 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90 ${disabled ? "opacity-40 cursor-not-allowed" : ""}`;
}

function Field({ label, hint, required = true, children }) {
  return (
    <div className="space-y-2">
      <div>
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted">{label}</span>
          {required && <span className="text-red-400 text-[12px]">*</span>}
        </div>
        {hint && <p className="text-[11px] text-text-muted mt-0.5">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

// ── StateMultiSelect ──────────────────────────────────────────────────────────

function StateMultiSelect({ selected, onChange, excludeCode }) {
  const [query, setQuery] = useState("");
  const [open,  setOpen]  = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = US_STATES.filter(
    (s) =>
      s.code !== excludeCode &&
      !selected.includes(s.code) &&
      (s.name.toLowerCase().includes(query.toLowerCase()) ||
       s.code.toLowerCase().includes(query.toLowerCase()))
  ).slice(0, 8);

  function addState(code) {
    onChange([...selected, code]);
    setQuery("");
  }

  function removeState(code) {
    onChange(selected.filter((c) => c !== code));
  }

  return (
    <div ref={ref} className="space-y-2">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((code) => {
            const s = US_STATES.find((s) => s.code === code);
            return (
              <span key={code} className="flex items-center gap-1 rounded-full border border-border bg-chip px-2.5 py-0.5 text-[12px] text-text-secondary">
                <MapPin className="h-3 w-3 text-text-muted" strokeWidth={2} />
                {s?.name || code}
                <button type="button" onClick={() => removeState(code)} className="ml-0.5 hover:text-red-500">
                  <X className="h-3 w-3" strokeWidth={2.5} />
                </button>
              </span>
            );
          })}
        </div>
      )}

      <div className="relative">
        <input
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Search and add states…"
          className="w-full rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
        />
        {open && filtered.length > 0 && (
          <div className="absolute z-20 mt-1 w-full rounded-xl border border-border bg-card shadow-card overflow-hidden">
            {filtered.map((s) => (
              <button
                key={s.code}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); addState(s.code); }}
                className="flex w-full items-center gap-2 px-4 py-2.5 text-[13px] text-text-secondary hover:bg-chip text-left"
              >
                <span className="w-7 text-[11px] font-mono text-text-muted">{s.code}</span>
                {s.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── DocumentRow ───────────────────────────────────────────────────────────────

function DocumentRow({ doc, uploaded, fileRef, onFileChange, onRemove }) {
  return (
    <div className={`flex items-start gap-3 rounded-xl border p-4 transition-colors
      ${uploaded ? "border-green-200 bg-green-50/40" : "border-border bg-chip-alt/30 hover:border-border-muted"}`}>
      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-chip">
        <FileText className="h-4 w-4 text-text-secondary" strokeWidth={2} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-semibold text-text-primary">{doc.label}</span>
          {doc.required && (
            <span className="rounded-full bg-action-dark/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-action-dark">Required</span>
          )}
          {uploaded && (
            <span className="rounded-full border border-green-200 bg-green-50 px-2 py-0.5 text-[10px] font-semibold text-green-700">✓ Uploaded</span>
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
            <input ref={fileRef} type="file" accept={doc.accept} onChange={(e) => onFileChange(e.target.files?.[0] || null)} className="hidden" />
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className={`flex items-center gap-2 rounded-full border px-4 py-1.5 text-[14px] font-semibold ${RISK_BADGE[risk] || RISK_BADGE.Unknown}`}>
          {risk === "High"
            ? <AlertTriangle className={`h-4 w-4 ${RISK_TEXT[risk]}`} strokeWidth={2.4} />
            : <ShieldCheck className={`h-4 w-4 ${RISK_TEXT[risk]}`} strokeWidth={2.4} />}
          <span className={RISK_TEXT[risk]}>{risk} risk</span>
          {score != null && <span className="font-normal text-text-muted">· {score}/100</span>}
          {stage && <span className="font-normal text-text-muted">· {stage}</span>}
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card hover:text-text-primary"
        >
          <X className="h-3.5 w-3.5" strokeWidth={2.4} /> New scan
        </button>
      </div>

      <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">Summary</div>
        <p className="text-[14px] leading-relaxed text-text-primary">{result.summary}</p>
      </div>

      {issues.length > 0 ? (
        <div className="space-y-4">
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            {issues.length} compliance issue{issues.length !== 1 ? "s" : ""} identified
          </div>
          {[
            { label: "High severity", items: high,   color: "text-red-600",   dot: "bg-red-500" },
            { label: "Medium severity", items: medium, color: "text-orange-600", dot: "bg-orange-400" },
            { label: "Low severity",  items: low,    color: "text-green-700", dot: "bg-green-500" },
          ].map(({ label, items, color, dot }) =>
            items.length > 0 ? (
              <div key={label} className="space-y-2">
                <div className={`flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide ${color}`}>
                  <span className={`h-2 w-2 rounded-full ${dot}`} />
                  {label} · {items.length}
                </div>
                {items.map((issue, i) => <IssueCard key={i} issue={issue} />)}
              </div>
            ) : null
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-green-200 bg-green-50 p-5 text-[13px] text-green-700">
          No IRS compliance issues were identified in the provided documents.
        </div>
      )}

      {notes.length > 0 && (
        <div className="rounded-2xl border border-border-muted bg-chip-alt p-4">
          <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">Notes</div>
          <ul className="space-y-1">
            {notes.map((note, i) => <li key={i} className="text-[12px] text-text-secondary">· {note}</li>)}
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
            <span className="rounded-full bg-chip px-2.5 py-0.5 text-[11px] font-medium text-text-secondary">{issue.area}</span>
            {issue.irc_section && issue.irc_section !== "N/A" && (
              <span className="rounded-full border border-border px-2.5 py-0.5 text-[11px] font-mono text-text-muted">{issue.irc_section}</span>
            )}
            <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${SEV_BADGE[sev] || SEV_BADGE.low}`}>{sev}</span>
          </div>
          <p className="text-[13px] leading-relaxed text-text-primary">{issue.finding}</p>
        </div>
        <ChevronRight className={`h-4 w-4 flex-shrink-0 text-text-muted transition-transform ${open ? "rotate-90" : ""}`} />
      </div>
      {open && (
        <div className="mt-3 rounded-xl border border-border bg-chip-alt px-4 py-3 text-left">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-1">Recommended action</div>
          <p className="text-[12px] text-text-secondary">{issue.recommendation}</p>
        </div>
      )}
    </button>
  );
}
