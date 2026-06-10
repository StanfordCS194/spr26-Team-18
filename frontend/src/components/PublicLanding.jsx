import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  ChevronDown,
  CheckCircle2,
  DollarSign,
  GitBranch,
  LockKeyhole,
  Play,
  Scale,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Star,
  UserRound,
  Zap,
} from "lucide-react";
import logo from "../assets/logo.png";

function fmt(n) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function useCountUp(target, duration = 1800, delay = 0) {
  const [count, setCount] = useState(0);
  const rafRef = useRef(null);
  useEffect(() => {
    const timeout = setTimeout(() => {
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        setCount(Math.round(target * eased));
        if (t < 1) rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    }, delay);
    return () => {
      clearTimeout(timeout);
      cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration, delay]);
  return count;
}

const SCENARIOS = {
  devtools: {
    label: "DevTools",
    repo: "cli/core",
    grade: "A-",
    saved: "$47,000",
    risk: "License risk",
    scan: "OSS scan",
    accent: "#0052ff",
  },
  health: {
    label: "Health",
    repo: "patient-portal",
    grade: "B+",
    saved: "$62,000",
    risk: "PHI review",
    scan: "HIPAA pass",
    accent: "#00C853",
  },
  fintech: {
    label: "Fintech",
    repo: "checkout-api",
    grade: "A",
    saved: "$58,000",
    risk: "PCI check",
    scan: "Controls",
    accent: "#FF6B00",
  },
};

function HeroIllustration({ scenario = "devtools" }) {
  const active = SCENARIOS[scenario] ?? SCENARIOS.devtools;
  return (
    <div className="relative h-[280px] w-[340px] flex-shrink-0">
      <div className="absolute right-0 top-0 w-[200px] rounded-2xl border-2 border-[#0052ff]/20 bg-white p-4 shadow-card animate-float">
        <div className="mb-3 flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-[#FF6B00]" />
          <div className="h-1.5 flex-1 rounded bg-[#d4e0ff]" />
        </div>
        <div className="space-y-1.5">
          <div className="h-2 w-full rounded bg-[#d4e0ff]" />
          <div className="h-2 w-4/5 rounded bg-[#d4e0ff]" />
          <div className="h-2 w-3/4 rounded bg-[#d4e0ff]" />
        </div>
        <div className="mt-3 rounded-xl border border-border bg-chip-alt px-3 py-2">
          <div className="text-[9px] font-bold uppercase tracking-[0.16em] text-text-muted">Repo</div>
          <div className="mt-0.5 truncate font-mono text-[12px] font-bold text-text-primary">{active.repo}</div>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[11px] font-bold text-[#0052ff]">Grade: {active.grade}</span>
          <div className="rounded-full bg-[#ccfce7] px-2 py-0.5 text-[10px] font-bold text-[#00874a]">
            +92%
          </div>
        </div>
      </div>

      <div className="absolute bottom-8 left-0 rounded-2xl border-2 border-[#FF6B00]/30 bg-white px-4 py-3 shadow-card">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[#7a90b8]">
          Legal fees saved
        </div>
        <div className="text-[22px] font-bold text-[#FF6B00]">{active.saved}</div>
      </div>

      <div className="absolute left-4 top-16 flex items-center gap-1.5 rounded-full border border-[#ccfce7] bg-white px-3 py-1.5 shadow-card">
        <CheckCircle2 className="h-3.5 w-3.5 text-[#00c853]" strokeWidth={2.5} />
        <span className="text-[11px] font-semibold text-[#050a14]">Compliant</span>
      </div>

      <div className="absolute bottom-[72px] right-4 flex items-center gap-1.5 rounded-full border border-[#dbeafe] bg-white px-3 py-1.5 shadow-card">
        <Zap className="h-3.5 w-3.5 text-[#0052ff]" strokeWidth={2.5} />
        <span className="text-[11px] font-semibold text-[#050a14]">{active.scan}</span>
      </div>

      <div className="absolute left-16 top-[132px] rounded-full border bg-white px-3 py-1.5 text-[11px] font-bold shadow-card" style={{ borderColor: `${active.accent}40`, color: active.accent }}>
        {active.risk}
      </div>

      <div className="absolute right-[-8px] top-[100px] flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star key={i} className="h-3 w-3 fill-[#FF6B00] text-[#FF6B00]" />
        ))}
      </div>
    </div>
  );
}

function ScenarioSwitcher({ scenario, onChange }) {
  return (
    <div className="animate-slide-up rounded-2xl border border-border bg-white/70 p-3 shadow-card" style={{ animationDelay: "0.24s" }}>
      <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-text-muted">
        <ScanSearch className="h-3.5 w-3.5" strokeWidth={2.2} />
        Try a startup profile
      </div>
      <div className="grid grid-cols-3 gap-2">
        {Object.entries(SCENARIOS).map(([id, item]) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={`rounded-xl border px-3 py-2 text-left transition-all ${
              scenario === id
                ? "border-[#0052ff] bg-[#0052ff]/10 shadow-card"
                : "border-border bg-card hover:-translate-y-0.5 hover:border-action-dark/50"
            }`}
          >
            <div className="text-[12px] font-bold leading-tight text-text-primary">{item.label}</div>
            <div className="mt-0.5 text-[10px] leading-tight text-text-muted">{item.risk}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function LandingPulse({ scenario }) {
  const active = SCENARIOS[scenario] ?? SCENARIOS.devtools;
  const events = [
    ["Repo queued", active.repo],
    ["Scanner routing", active.label],
    ["Signal found", active.risk],
    ["Workspace ready", active.grade],
  ];
  return (
    <section className="animate-slide-up overflow-hidden rounded-2xl border border-border bg-white p-4 shadow-card" style={{ animationDelay: "0.28s" }}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#0052ff]">Live demo pulse</div>
          <div className="mt-0.5 text-[13px] text-text-secondary">Switch profiles above and watch the scanner path update.</div>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          Ready
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {events.map(([label, value], index) => (
          <div key={label} className="rounded-xl border border-border bg-chip-alt px-4 py-3">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-[10px] text-action-dark">{index + 1}</span>
              {label}
            </div>
            <div className="mt-2 truncate text-[13px] font-bold text-text-primary">{value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function MiniIllustration({ kind }) {
  const config = {
    doc: ["#EEF3FF", "#0052FF", "Profile"],
    grade: ["#CCFCE7", "#00C853", "Repo"],
    money: ["#FFEDD5", "#FF6B00", "Plan"],
  }[kind];
  return (
    <div
      className="flex h-[72px] w-[72px] items-center justify-center rounded-[20px]"
      style={{ backgroundColor: config[0] }}
    >
      <div
        className="flex h-11 w-11 items-center justify-center rounded-2xl border bg-white/60 text-[12px] font-bold"
        style={{ borderColor: config[1], color: config[1] }}
      >
        {config[2]}
      </div>
    </div>
  );
}

const INDUSTRIES = [
  { id: "health", label: "Health & MedTech" },
  { id: "fintech", label: "Fintech" },
  { id: "saas", label: "Consumer SaaS" },
  { id: "edtech", label: "EdTech" },
  { id: "devtools", label: "Developer Tools" },
  { id: "ai", label: "AI / ML" },
  { id: "enterprise", label: "Enterprise B2B" },
  { id: "other", label: "Other / General" },
];

const STAGES = [
  { id: "idea", label: "Idea" },
  { id: "pre-seed", label: "Pre-Seed" },
  { id: "seed", label: "Seed" },
  { id: "series-a", label: "Series A+" },
];
const CUSTOMERS = [
  { id: "consumer", label: "Consumers" },
  { id: "smb", label: "SMB" },
  { id: "mid-market", label: "Mid-Market" },
  { id: "enterprise", label: "Enterprise" },
  { id: "developer", label: "Developers" },
];
const SENSITIVE_DATA = [
  { id: "none", label: "None" },
  { id: "pii", label: "PII" },
  { id: "health-data", label: "Health Data" },
  { id: "financial", label: "Financial Data" },
  { id: "minors", label: "Minors" },
];
const GTM = [
  { id: "self-serve", label: "Self-Serve" },
  { id: "plg", label: "PLG" },
  { id: "sales-led", label: "Sales-Led" },
  { id: "marketplace", label: "Marketplace" },
  { id: "api", label: "API" },
];

const EMPTY_PROFILE = {
  companyName: "",
  industry: "",
  stage: "",
  customers: "",
  sensitiveData: "",
  gtm: "",
  repoUrl: "",
};

const DEMO_PROFILE = {
  companyName: "Octo Labs",
  industry: "other",
  stage: "seed",
  customers: "developer",
  sensitiveData: "none",
  gtm: "plg",
  repoUrl: "https://github.com/octocat/Hello-World",
};

const LANDING_STEPS = [
  {
    n: "01",
    kind: "doc",
    title: "Set your company context",
    body: "Answer a few guided questions about your industry, stage, customers, and data profile.",
    tags: ["Company", "Industry", "Data"],
    color: "#0052FF",
    bgColor: "#EEF3FF",
  },
  {
    n: "02",
    kind: "grade",
    title: "Connect a public repo",
    body: "Paste a public repo link or use the demo repo. Our AI agents review your code without executing it.",
    tags: ["Repo URL", "AI agents", "No code exec"],
    color: "#00C853",
    bgColor: "#CCFCE7",
  },
  {
    n: "03",
    kind: "money",
    title: "Review your action plan",
    body: "Get evidence-backed findings, benchmarks, startup health, and prioritized next steps.",
    tags: ["Findings", "Benchmarks", "Next steps"],
    color: "#FF6B00",
    bgColor: "#FFEDD5",
  },
];

function validGithubUrl(value) {
  return /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(value.trim());
}

function displayValue(key, value) {
  if (!value) return "-";
  const optionsByKey = {
    industry: INDUSTRIES,
    stage: STAGES,
    customers: CUSTOMERS,
    sensitiveData: SENSITIVE_DATA,
    gtm: GTM,
  };
  return optionsByKey[key]?.find((item) => item.id === value)?.label || value;
}

export default function PublicLanding({ onSignIn, onSignUpComplete }) {
  const [mode, setMode] = useState("landing");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [scenario, setScenario] = useState("devtools");
  const howItWorksRef = useRef(null);
  const savings = useCountUp(47_000, 2000, 300);
  const repos = useCountUp(4_821, 1600, 500);
  const hours = useCountUp(350, 1400, 400);

  useLayoutEffect(() => {
    const frame = requestAnimationFrame(() => {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    });
    return () => cancelAnimationFrame(frame);
  }, [mode]);

  function openSignUp(nextProfile = EMPTY_PROFILE) {
    setProfile(nextProfile);
    setMode("signup");
  }

  if (mode === "signup") {
    return (
      <OnboardingFlow
        profile={profile}
        setProfile={setProfile}
        onBack={() => setMode("landing")}
        onStartScan={() => onSignUpComplete(profile)}
      />
    );
  }

  return (
    <main className="min-h-screen overflow-x-hidden scroll-smooth bg-page">
      <header className="mx-auto flex max-w-[1180px] items-center justify-between px-8 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-white shadow-card">
            <img src={logo} alt="" className="h-7 w-7 object-contain" />
          </div>
          <span className="text-[19px] font-bold tracking-tight text-text-primary">Legi-Bill</span>
        </div>
        <nav className="flex items-center gap-2">
          <button
            onClick={onSignIn}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-semibold text-text-secondary shadow-card transition-colors hover:text-text-primary"
          >
            <LockKeyhole className="h-3.5 w-3.5" strokeWidth={2.2} />
            Sign in
          </button>
          <button
            onClick={() => openSignUp()}
            className="inline-flex items-center gap-2 rounded-full bg-action-dark px-4 py-2 text-[13px] font-semibold text-white shadow-card transition-opacity hover:opacity-90"
          >
            <UserRound className="h-3.5 w-3.5" strokeWidth={2.2} />
            Sign up
          </button>
        </nav>
      </header>

      <div className="mx-auto max-w-[1180px] space-y-20 px-8 pb-40 pt-4 lg:pb-56">
        <section className="pt-4">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-[590px] space-y-6">
              <div className="animate-slide-up flex items-center gap-2" style={{ animationDelay: "0s" }}>
                <div className="flex items-center gap-1.5 rounded-full bg-[#0052ff]/10 px-3 py-1 text-[12px] font-semibold text-[#0052ff]">
                  <Zap className="h-3.5 w-3.5" strokeWidth={2.5} />
                  <span>AI-powered · Founder Copilot</span>
                </div>
              </div>

              <div className="animate-slide-up space-y-3" style={{ animationDelay: "0.06s" }}>
                <h1 className="animate-shimmer-text text-[52px] font-bold leading-[1.05] tracking-tight">
                  Your startup's<br />compliance HQ.
                </h1>
                <p className="text-[18px] font-medium leading-relaxed text-text-secondary">
                  Step through a quick company profile, paste your repo, and scan compliance risk in{" "}
                  <span className="font-bold text-text-primary">30 seconds.</span>{" "}
                  Then unlock the workspace behind sign in.
                </p>
              </div>

              <div
                className="animate-slide-up w-fit rounded-2xl border-2 border-[#FF6B00]/30 bg-gradient-to-br from-[#fff7ed] to-white p-5 shadow-card"
                style={{ animationDelay: "0.12s" }}
              >
                <div className="text-[11px] font-bold uppercase tracking-widest text-[#FF6B00]/70">
                  Average legal fees automated
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-[52px] font-bold tabular-nums leading-none text-[#FF6B00]">
                    {fmt(savings)}
                  </span>
                  <span className="text-[15px] font-medium text-text-muted">/ startup</span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-text-secondary">
                  <span className="font-bold text-text-primary">{repos.toLocaleString()}</span>
                  <span className="text-text-muted">repos and bills scanned</span>
                  <span className="text-text-muted">·</span>
                  <span className="font-bold text-text-primary">{hours}+</span>
                  <span className="text-text-muted">attorney hours automated</span>
                </div>
              </div>

              <div className="animate-slide-up flex flex-wrap items-center gap-3" style={{ animationDelay: "0.18s" }}>
                <button
                  onClick={() => openSignUp()}
                  className="flex items-center gap-2 rounded-xl bg-[#0052ff] px-6 py-3 text-[14px] font-bold text-white shadow-glow transition-all hover:bg-[#0041cc] hover:shadow-glow active:scale-95"
                >
                  Sign up and scan
                  <ArrowRight className="h-4 w-4" strokeWidth={2.5} />
                </button>
                <button
                  onClick={() => {
                    setProfile(DEMO_PROFILE);
                    setMode("signup");
                  }}
                  className="flex items-center gap-2 rounded-xl border-2 border-[#FF6B00]/30 bg-white px-6 py-3 text-[14px] font-bold text-[#FF6B00] transition-all hover:border-[#FF6B00]/60 hover:shadow-card active:scale-95"
                >
                  <Play className="h-4 w-4" strokeWidth={2.2} />
                  Try demo repo
                </button>
              </div>

              <ScenarioSwitcher scenario={scenario} onChange={setScenario} />
            </div>

            <div className="animate-slide-up hidden lg:flex" style={{ animationDelay: "0.1s" }}>
              <HeroIllustration scenario={scenario} />
            </div>
          </div>
        </section>

        <LandingPulse scenario={scenario} />

        <div className="flex justify-center">
          <button
            onClick={() => howItWorksRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-white/80 px-4 py-2 text-[12px] font-semibold text-text-secondary shadow-card transition-all hover:-translate-y-0.5 hover:text-text-primary"
          >
            See the demo flow
            <ChevronDown className="h-3.5 w-3.5" strokeWidth={2.3} />
          </button>
        </div>

        <div
          className="animate-slide-up -mx-2 flex items-center gap-6 overflow-hidden rounded-2xl border-2 border-[#d4e0ff] bg-white px-6 py-4"
          style={{ animationDelay: "0.22s" }}
        >
          {[
            { icon: ShieldCheck, label: "50+ compliance rules", color: "#0052ff" },
            { icon: Zap, label: "Under 30 seconds", color: "#00C853" },
            { icon: DollarSign, label: "No law firm needed", color: "#FF6B00" },
            { icon: Star, label: "Evidence-backed scans", color: "#7c3aed" },
          ].map(({ icon: Icon, label, color }) => (
            <div key={label} className="flex items-center gap-2 text-[13px] font-semibold text-text-secondary">
              <Icon className="h-4 w-4 shrink-0" style={{ color }} strokeWidth={2.4} />
              {label}
            </div>
          ))}
        </div>

        <section ref={howItWorksRef} className="scroll-mt-8 space-y-6">
          <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
            <div className="mb-1 text-[12px] font-bold uppercase tracking-[0.2em] text-[#0052ff]">
              How it works
            </div>
            <h2 className="text-[28px] font-bold text-text-primary">
              Three steps to compliance clarity
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {LANDING_STEPS.map((step, i) => (
              <div
                key={step.n}
                className="animate-slide-up relative flex flex-col rounded-2xl border-2 bg-white p-6 shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
                style={{
                  animationDelay: `${0.12 + i * 0.08}s`,
                  borderColor: step.color + "33",
                }}
              >
                {i < LANDING_STEPS.length - 1 && (
                  <div className="absolute -right-[16px] top-1/2 z-10 hidden -translate-y-1/2 lg:block">
                    <div
                      className="flex h-8 w-8 items-center justify-center rounded-full border-2 bg-white shadow-card"
                      style={{ borderColor: step.color + "40" }}
                    >
                      <ArrowRight className="h-4 w-4" style={{ color: step.color }} strokeWidth={2.5} />
                    </div>
                  </div>
                )}

                <div className="mb-4">
                  <MiniIllustration kind={step.kind} />
                </div>

                <div
                  className="mb-1 text-[11px] font-bold uppercase tracking-[0.2em]"
                  style={{ color: step.color }}
                >
                  Step {step.n}
                </div>
                <div className="text-[16px] font-bold text-text-primary">{step.title}</div>
                <div className="mt-2 text-[13px] leading-relaxed text-text-secondary">{step.body}</div>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  {step.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded-full border px-2.5 py-0.5 text-[11px] font-semibold"
                      style={{
                        borderColor: step.color + "40",
                        backgroundColor: step.bgColor,
                        color: step.color,
                      }}
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

const QUESTION_STEPS = [
  {
    key: "companyName",
    short: "Company",
    eyebrow: "Question 1",
    title: "What's your company called?",
    body: "This labels the workspace, reports, and scanner summary.",
    type: "text",
    placeholder: "Octo Labs",
    icon: Building2,
    validate: (value) => (value.trim() ? null : "Company name is required."),
  },
  {
    key: "industry",
    short: "Industry",
    eyebrow: "Question 2",
    title: "What industry do you work in?",
    body: "We use this to route the scanner toward the right risk patterns.",
    type: "select",
    options: INDUSTRIES,
    validate: (value) => (value ? null : "Choose an industry."),
  },
  {
    key: "stage",
    short: "Stage",
    eyebrow: "Question 3",
    title: "What stage are you at?",
    body: "A seed-stage startup and an enterprise vendor should not get the same advice.",
    type: "select",
    options: STAGES,
    validate: (value) => (value ? null : "Choose a stage."),
  },
  {
    key: "customers",
    short: "Customer",
    eyebrow: "Question 4",
    title: "Who do you sell to?",
    body: "This helps frame privacy, procurement, and enterprise readiness findings.",
    type: "select",
    options: CUSTOMERS,
    validate: (value) => (value ? null : "Choose a customer type."),
  },
  {
    key: "sensitiveData",
    short: "Data",
    eyebrow: "Question 5",
    title: "What sensitive data do you handle?",
    body: "Pick the highest-risk category that applies. You can refine this later.",
    type: "select",
    options: SENSITIVE_DATA,
    validate: (value) => (value ? null : "Choose a data profile."),
  },
  {
    key: "gtm",
    short: "GTM",
    eyebrow: "Question 6",
    title: "How do you go to market?",
    body: "Sales motion changes the compliance work that matters this week.",
    type: "select",
    options: GTM,
    validate: (value) => (value ? null : "Choose a go-to-market motion."),
  },
  {
    key: "repoUrl",
    short: "Repo",
    eyebrow: "Question 7",
    title: "What repo should we scan?",
    body: "Use a public GitHub repo. Our agents only read your code and never execute it.",
    type: "text",
    placeholder: "https://github.com/owner/repo",
    icon: GitBranch,
    validate: (value) => (validGithubUrl(value) ? null : "Use https://github.com/owner/repo."),
  },
];

const FINAL_STEP = QUESTION_STEPS.length;

function OnboardingFlow({ profile, setProfile, onBack, onStartScan }) {
  const [step, setStep] = useState(profile.repoUrl ? FINAL_STEP : 0);
  const [errors, setErrors] = useState({});
  const current = QUESTION_STEPS[step];
  const completeCount = QUESTION_STEPS.filter((item) => isAnswered(profile, item)).length;
  const progress = Math.round((Math.min(step, FINAL_STEP) / FINAL_STEP) * 100);

  function setField(key, value) {
    setProfile({ ...profile, [key]: value });
    setErrors({ ...errors, [key]: null });
  }

  function validateStep(index = step) {
    const item = QUESTION_STEPS[index];
    if (!item) return true;
    const error = item.validate(profile[item.key] || "");
    setErrors(error ? { [item.key]: error } : {});
    return !error;
  }

  function firstInvalidStep() {
    return QUESTION_STEPS.findIndex((item) => item.validate(profile[item.key] || ""));
  }

  function next() {
    if (!validateStep()) return;
    setStep((value) => Math.min(FINAL_STEP, value + 1));
  }

  function submit() {
    const invalid = firstInvalidStep();
    if (invalid >= 0) {
      setStep(invalid);
      validateStep(invalid);
      return;
    }
    onStartScan();
  }

  function useDemoProfile() {
    setProfile({ ...DEMO_PROFILE });
    setErrors({});
    setStep(FINAL_STEP);
  }

  return (
    <main className="h-screen overflow-hidden bg-page px-4 py-4 lg:px-6 lg:py-5">
      <div className="mx-auto flex h-full max-w-[1120px] flex-col">
        <div>
          <button
            onClick={onBack}
            className="mb-3 inline-flex items-center gap-2 text-[13px] font-semibold text-text-secondary hover:text-text-primary"
          >
            <ArrowLeft className="h-4 w-4" strokeWidth={2.2} />
            Back to landing
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[1fr_280px] lg:grid-cols-[1fr_300px]">
          <section className="flex min-h-0 flex-col rounded-3xl border border-border bg-card p-4 shadow-card sm:p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">Startup Setup</div>
                <h1 className="mt-0.5 text-[22px] font-bold tracking-tight text-text-primary">
                  Build your scanner profile
                </h1>
              </div>
              <button
                onClick={useDemoProfile}
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full border border-border bg-chip-alt px-3 py-2 text-[12px] font-semibold text-text-secondary hover:text-text-primary"
              >
                <Play className="h-3.5 w-3.5" strokeWidth={2.2} />
                Try demo repo
              </button>
            </div>

            <div className="mb-3">
              <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                <span>Step {Math.min(step + 1, FINAL_STEP + 1)} of {FINAL_STEP + 1}</span>
                <span>{completeCount}/{QUESTION_STEPS.length} answered</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-chip-alt">
                <div
                  className="h-full rounded-full bg-action-dark transition-all duration-300"
                  style={{ width: `${step === FINAL_STEP ? 100 : progress}%` }}
                />
              </div>
            </div>

            <CompletedChips profile={profile} activeStep={step} />
            <ScannerEnergy step={step} completeCount={completeCount} />

            <div className="min-h-0">
              {step < FINAL_STEP ? (
                <QuestionCard
                  item={current}
                  value={profile[current.key] || ""}
                  error={errors[current.key]}
                  onChange={(value) => setField(current.key, value)}
                />
              ) : (
                <ReadySummary profile={profile} />
              )}
            </div>

            <div className="mt-3 flex items-center justify-between">
              <button
                onClick={() => setStep((value) => Math.max(0, value - 1))}
                disabled={step === 0}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-semibold text-text-secondary shadow-card hover:text-text-primary disabled:opacity-40"
              >
                <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2.2} />
                Back
              </button>
              {step < FINAL_STEP ? (
                <button
                  onClick={next}
                  className="inline-flex items-center gap-2 rounded-full bg-action-dark px-5 py-2.5 text-[13px] font-semibold text-white shadow-card hover:opacity-90"
                >
                  Continue
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={2.2} />
                </button>
              ) : (
                <button
                  onClick={submit}
                  className="inline-flex items-center gap-2 rounded-full bg-action-dark px-5 py-2.5 text-[13px] font-semibold text-white shadow-glow hover:opacity-90"
                >
                  <ScanSearch className="h-3.5 w-3.5" strokeWidth={2.2} />
                  Start scan
                </button>
              )}
            </div>
          </section>

          <ProfilePreview profile={profile} completeCount={completeCount} />
        </div>
      </div>
    </main>
  );
}

function ScannerEnergy({ step, completeCount }) {
  const pct = Math.round((completeCount / QUESTION_STEPS.length) * 100);
  const labels = ["Context", "Risk routing", "Customer lens", "Data profile", "Launch motion"];
  return (
    <div className="mb-3 rounded-2xl border border-[#0052ff]/15 bg-white px-3 py-2 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#0052ff]">Scanner charge</div>
          <div className="mt-0.5 text-[12px] font-semibold text-text-primary">
            {step >= FINAL_STEP ? "Profile locked. Ready to scan." : `${labels[Math.min(step, labels.length - 1)]} is powering up.`}
          </div>
        </div>
        <div className="rounded-full border border-border bg-chip-alt px-3 py-1 text-[11px] font-bold text-text-secondary">
          {pct}% ready
        </div>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-chip-alt">
        <div
          className="h-full rounded-full bg-blue-gradient transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function isAnswered(profile, item) {
  const value = profile[item.key] || "";
  return !item.validate(value);
}

function labelFor(item, value) {
  if (!value) return "";
  return item.options?.find((option) => option.id === value)?.label || value;
}

function CompletedChips({ profile, activeStep }) {
  return (
    <div className="mb-3 grid grid-cols-7 gap-1.5">
      {QUESTION_STEPS.map((item, index) => {
        const value = profile[item.key] || "";
        const done = isAnswered(profile, item);
        return (
          <span
            key={item.key}
            className={
              "inline-flex min-w-0 items-center justify-center gap-1 rounded-full border px-2 py-1 text-[10px] font-semibold transition-colors " +
              (done
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : index === activeStep
                  ? "border-action-dark bg-[#0052ff]/10 text-action-dark"
                  : "border-border bg-chip-alt text-text-muted")
            }
          >
            {done && <CheckCircle2 className="h-3 w-3" strokeWidth={2.3} />}
            {item.short}
            {done && <span className="hidden max-w-[120px] truncate opacity-80 lg:inline">· {labelFor(item, value)}</span>}
          </span>
        );
      })}
    </div>
  );
}

function QuestionCard({ item, value, error, onChange }) {
  const Icon = item.icon || SparkleDot;
  return (
    <div className="rounded-3xl border border-border-muted bg-chip-alt p-3.5 animate-fade-in">
      <div className="flex items-start gap-3">
        <div className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-card shadow-card sm:flex">
          <Icon className="h-5 w-5 text-action-dark" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">{item.eyebrow}</div>
          <h2 className="mt-0.5 text-[21px] font-bold leading-tight tracking-tight text-text-primary">{item.title}</h2>
          <p className="mt-1 max-w-[560px] text-[12px] leading-relaxed text-text-secondary">{item.body}</p>

          <div className="mt-3">
            {item.type === "select" ? (
              <OptionPicker
                label={item.title}
                value={value}
                error={error}
                options={item.options}
                onChange={onChange}
              />
            ) : (
              <TextField
                label={item.title}
                value={value}
                error={error}
                icon={item.icon || Building2}
                placeholder={item.placeholder}
                onChange={onChange}
              />
            )}
          </div>

          {value && !error && (
            <div className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <CheckCircle2 className="h-3 w-3" strokeWidth={2.4} />
              Locked in: {labelFor(item, value)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SparkleDot(props) {
  return <ScanSearch {...props} />;
}

function TextField({ label, value, error, icon: Icon, placeholder, onChange }) {
  return (
    <label className="block space-y-2">
      <span className="sr-only">{label}</span>
      <div className="relative">
        <Icon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" strokeWidth={2} />
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="w-full rounded-2xl border border-border bg-card py-3 pl-10 pr-4 text-[14px] text-text-primary shadow-card outline-none placeholder:text-text-muted focus:border-action-dark"
        />
      </div>
      {error && <span className="text-[11px] text-red-600">{error}</span>}
    </label>
  );
}

function OptionPicker({ label, value, error, options, onChange }) {
  const selected = options.find((option) => option.id === value);
  return (
    <div className="space-y-2">
      <span className="sr-only">{label}</span>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {options.map((option) => {
          const isSelected = option.id === value;
          return (
            <button
              type="button"
              key={option.id}
              onClick={() => onChange(option.id)}
              className={`group flex min-h-[54px] items-center gap-2 rounded-2xl border p-2.5 text-left shadow-card transition-all sm:min-h-[62px] sm:gap-2.5 ${
                isSelected
                  ? "border-[#0052ff] bg-[#0052ff]/10 ring-4 ring-[#0052ff]/10"
                  : "border-border bg-card hover:-translate-y-0.5 hover:border-action-dark/60 hover:shadow-card-hover"
              }`}
              aria-pressed={isSelected}
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-all ${
                  isSelected
                    ? "border-[#0052ff] bg-[#0052ff] text-white"
                    : "border-border bg-chip-alt text-transparent group-hover:border-action-dark/50"
                }`}
              >
                <CheckCircle2 className="h-3 w-3 sm:h-3.5 sm:w-3.5" strokeWidth={2.6} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block whitespace-normal break-words text-[12px] font-bold leading-snug text-text-primary sm:text-[13px]">
                  {option.label}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      {selected && (
        <div className="rounded-xl border border-border bg-white/70 px-3 py-2 text-[11px] leading-relaxed text-text-secondary">
          <span className="font-semibold text-text-primary">{selected.label}:</span> {optionHint(selected)}
        </div>
      )}
      {error && <span className="text-[11px] text-red-600">{error}</span>}
    </div>
  );
}

function optionHint(option) {
  const hints = {
    health: "HIPAA, PHI, patient workflows, and clinical diligence.",
    fintech: "PCI, transaction risk, financial data, and vendor review.",
    saas: "Privacy, consent, analytics, and consumer data obligations.",
    edtech: "Student data, minors, FERPA, and COPPA-style checks.",
    devtools: "Open-source licenses, supply chain, and developer distribution.",
    ai: "Training data, model behavior, and AI data-use controls.",
    enterprise: "SOC 2 readiness, access control, procurement, and audit trails.",
    other: "General security, privacy, and repository hygiene.",
    idea: "Pre-product or prototype stage.",
    "pre-seed": "Early team, early users, and light process.",
    seed: "Customer traction with growing diligence needs.",
    "series-a": "Scaling operations, sales, and compliance obligations.",
    consumer: "Individuals, app users, or public self-serve customers.",
    smb: "Small business buyers with lighter procurement.",
    "mid-market": "Larger customers and more structured review cycles.",
    developer: "Technical users, SDKs, CLIs, APIs, or open-source users.",
    none: "No sensitive data expected in normal use.",
    pii: "Names, emails, identifiers, profiles, or account data.",
    "health-data": "Health, patient, clinical, or insurance information.",
    financial: "Payments, banking, accounting, payroll, or tax data.",
    minors: "Children, students, age-gated users, or education records.",
    "self-serve": "Customers sign up and buy without sales support.",
    plg: "Product-led growth with usage driving expansion.",
    "sales-led": "Sales calls, procurement, security review, and contracts.",
    marketplace: "Distribution through app stores, cloud, or partner channels.",
    api: "API-first product, integrations, or developer platform.",
  };
  return hints[option.id] || hints[option.label] || "Recommended scanner context.";
}

function ProfilePreview({ profile, completeCount }) {
  return (
    <aside className="hidden rounded-3xl border border-border bg-card p-4 shadow-card md:block lg:sticky lg:top-8 lg:self-start">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-text-muted">Live profile</div>
          <div className="mt-1 text-[17px] font-bold text-text-primary">
            {profile.companyName || "Unnamed startup"}
          </div>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0052ff]/10 text-[13px] font-bold text-action-dark">
          {completeCount}/7
        </div>
      </div>
      <ProfileRows profile={profile} compact />
    </aside>
  );
}

function ReadySummary({ profile }) {
  const summaryRows = [
    ["Company", profile.companyName],
    ["Industry", displayValue("industry", profile.industry)],
    ["Stage", displayValue("stage", profile.stage)],
    ["Customer", displayValue("customers", profile.customers)],
    ["Data", displayValue("sensitiveData", profile.sensitiveData)],
    ["Repo", profile.repoUrl],
  ];
  return (
    <div className="rounded-3xl border border-emerald-200 bg-emerald-50/70 p-4 animate-fade-in">
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-emerald-700 shadow-card">
          <CheckCircle2 className="h-5 w-5" strokeWidth={2.4} />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-700">Ready to scan</div>
          <h2 className="text-[22px] font-bold tracking-tight text-text-primary">
            {profile.companyName || "Your company"} is queued up.
          </h2>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {summaryRows.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-emerald-200 bg-white/80 px-3 py-2">
            <div className="text-[9px] uppercase tracking-[0.14em] text-emerald-700">{label}</div>
            <div className="mt-0.5 truncate text-[12px] font-semibold text-text-primary">{value || "-"}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[12px] leading-relaxed text-text-secondary">
        Start scan unlocks the workspace and keeps this profile in the demo session.
      </p>
    </div>
  );
}

function ProfileRows({ profile, compact = false }) {
  const rows = [
    ["Company", profile.companyName],
    ["Industry", displayValue("industry", profile.industry)],
    ["Stage", displayValue("stage", profile.stage)],
    ["Customer", displayValue("customers", profile.customers)],
    ["Sensitive data", displayValue("sensitiveData", profile.sensitiveData)],
    ["GTM", displayValue("gtm", profile.gtm)],
    ["Repo", profile.repoUrl],
  ];
  return (
    <div className={compact ? "space-y-2" : "grid grid-cols-1 gap-3 md:grid-cols-2"}>
      {rows.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-border-muted bg-card px-4 py-3">
            <div className="text-[10px] uppercase tracking-[0.14em] text-text-muted">{label}</div>
            <div className="mt-1 break-words text-[13px] font-semibold text-text-primary">{value || "-"}</div>
          </div>
      ))}
    </div>
  );
}
