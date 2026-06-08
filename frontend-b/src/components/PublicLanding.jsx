import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
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

function HeroIllustration() {
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
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[11px] font-bold text-[#0052ff]">Grade: A</span>
          <div className="rounded-full bg-[#ccfce7] px-2 py-0.5 text-[10px] font-bold text-[#00874a]">
            +92%
          </div>
        </div>
      </div>

      <div className="absolute bottom-8 left-0 rounded-2xl border-2 border-[#FF6B00]/30 bg-white px-4 py-3 shadow-card">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[#7a90b8]">
          Legal fees saved
        </div>
        <div className="text-[22px] font-bold text-[#FF6B00]">$47,000</div>
      </div>

      <div className="absolute left-4 top-16 flex items-center gap-1.5 rounded-full border border-[#ccfce7] bg-white px-3 py-1.5 shadow-card">
        <CheckCircle2 className="h-3.5 w-3.5 text-[#00c853]" strokeWidth={2.5} />
        <span className="text-[11px] font-semibold text-[#050a14]">Compliant</span>
      </div>

      <div className="absolute bottom-[72px] right-4 flex items-center gap-1.5 rounded-full border border-[#dbeafe] bg-white px-3 py-1.5 shadow-card">
        <Zap className="h-3.5 w-3.5 text-[#0052ff]" strokeWidth={2.5} />
        <span className="text-[11px] font-semibold text-[#050a14]">30 sec</span>
      </div>

      <div className="absolute right-[-8px] top-[100px] flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star key={i} className="h-3 w-3 fill-[#FF6B00] text-[#FF6B00]" />
        ))}
      </div>
    </div>
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

const STAGES = ["idea", "pre-seed", "seed", "series A+"];
const CUSTOMERS = ["consumer", "SMB", "mid-market", "enterprise", "developer"];
const SENSITIVE_DATA = ["none", "PII", "health (HIPAA)", "financial", "minors"];
const GTM = ["self-serve", "PLG", "sales-led", "marketplace", "API"];

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
  gtm: "PLG",
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
    body: "Paste a public repo link or use the demo repo. We run static scanners without executing code.",
    tags: ["Repo URL", "Static scan", "No code exec"],
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

function industryLabel(id) {
  return INDUSTRIES.find((item) => item.id === id)?.label || id || "-";
}

export default function PublicLanding({ onSignIn, onSignUpComplete }) {
  const [mode, setMode] = useState("landing");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const savings = useCountUp(47_000, 2000, 300);
  const repos = useCountUp(4_821, 1600, 500);
  const hours = useCountUp(350, 1400, 400);

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
    <main className="min-h-screen bg-page">
      <header className="mx-auto flex max-w-[1180px] items-center justify-between px-8 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0052ff]">
            <img src={logo} alt="" className="h-7 w-7 rounded object-contain" />
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

      <div className="mx-auto max-w-[1180px] space-y-20 px-8 pb-16 pt-4">
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
            </div>

            <div className="animate-slide-up hidden lg:flex" style={{ animationDelay: "0.1s" }}>
              <HeroIllustration />
            </div>
          </div>
        </section>

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

        <section className="space-y-6">
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
    options: STAGES.map((value) => ({ id: value, label: value })),
    validate: (value) => (value ? null : "Choose a stage."),
  },
  {
    key: "customers",
    short: "Customer",
    eyebrow: "Question 4",
    title: "Who do you sell to?",
    body: "This helps frame privacy, procurement, and enterprise readiness findings.",
    type: "select",
    options: CUSTOMERS.map((value) => ({ id: value, label: value })),
    validate: (value) => (value ? null : "Choose a customer type."),
  },
  {
    key: "sensitiveData",
    short: "Data",
    eyebrow: "Question 5",
    title: "What sensitive data do you handle?",
    body: "Pick the highest-risk category that applies. You can refine this later.",
    type: "select",
    options: SENSITIVE_DATA.map((value) => ({ id: value, label: value })),
    validate: (value) => (value ? null : "Choose a data profile."),
  },
  {
    key: "gtm",
    short: "GTM",
    eyebrow: "Question 6",
    title: "How do you go to market?",
    body: "Sales motion changes the compliance work that matters this week.",
    type: "select",
    options: GTM.map((value) => ({ id: value, label: value })),
    validate: (value) => (value ? null : "Choose a go-to-market motion."),
  },
  {
    key: "repoUrl",
    short: "Repo",
    eyebrow: "Question 7",
    title: "What repo should we scan?",
    body: "Use a public GitHub repo. We only run static analysis and never execute code.",
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
    <main className="min-h-screen bg-page px-8 py-8">
      <div className="mx-auto max-w-[1120px]">
        <button
          onClick={onBack}
          className="mb-6 inline-flex items-center gap-2 text-[13px] font-semibold text-text-secondary hover:text-text-primary"
        >
          <ArrowLeft className="h-4 w-4" strokeWidth={2.2} />
          Back to landing
        </button>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_330px]">
          <section className="rounded-3xl border border-border bg-card p-7 shadow-card">
            <div className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">Interactive sign up</div>
                <h1 className="mt-1 text-[30px] font-bold tracking-tight text-text-primary">
                  Build your scanner profile.
                </h1>
              </div>
              <button
                onClick={useDemoProfile}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-chip-alt px-4 py-2 text-[13px] font-semibold text-text-secondary hover:text-text-primary"
              >
                <Play className="h-3.5 w-3.5" strokeWidth={2.2} />
                Try demo repo
              </button>
            </div>

            <div className="mb-7">
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

            <div className="mt-8 flex items-center justify-between">
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
    <div className="mb-6 flex flex-wrap gap-2">
      {QUESTION_STEPS.map((item, index) => {
        const value = profile[item.key] || "";
        const done = isAnswered(profile, item);
        return (
          <span
            key={item.key}
            className={
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors " +
              (done
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : index === activeStep
                  ? "border-action-dark bg-[#0052ff]/10 text-action-dark"
                  : "border-border bg-chip-alt text-text-muted")
            }
          >
            {done && <CheckCircle2 className="h-3 w-3" strokeWidth={2.3} />}
            {item.short}
            {done && <span className="max-w-[120px] truncate opacity-80">· {labelFor(item, value)}</span>}
          </span>
        );
      })}
    </div>
  );
}

function QuestionCard({ item, value, error, onChange }) {
  const Icon = item.icon || SparkleDot;
  return (
    <div className="rounded-3xl border border-border-muted bg-chip-alt p-6 animate-fade-in">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-card shadow-card">
          <Icon className="h-5 w-5 text-action-dark" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">{item.eyebrow}</div>
          <h2 className="mt-1 text-[28px] font-bold leading-tight tracking-tight text-text-primary">{item.title}</h2>
          <p className="mt-2 max-w-[560px] text-[14px] leading-relaxed text-text-secondary">{item.body}</p>

          <div className="mt-6">
            {item.type === "select" ? (
              <SelectField
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
            <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[12px] font-semibold text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2.4} />
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

function SelectField({ label, value, error, options, onChange }) {
  return (
    <label className="block space-y-2">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-border bg-card px-4 py-3 text-[14px] text-text-primary shadow-card outline-none focus:border-action-dark"
      >
        <option value="">Select one</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <span className="text-[11px] text-red-600">{error}</span>}
    </label>
  );
}

function ProfilePreview({ profile, completeCount }) {
  return (
    <aside className="rounded-3xl border border-border bg-card p-5 shadow-card lg:sticky lg:top-8 lg:self-start">
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
  return (
    <div className="rounded-3xl border border-emerald-200 bg-emerald-50/70 p-6 animate-fade-in">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-emerald-700 shadow-card">
          <CheckCircle2 className="h-6 w-6" strokeWidth={2.4} />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-700">Ready to scan</div>
          <h2 className="text-[27px] font-bold tracking-tight text-text-primary">
            {profile.companyName || "Your company"} is queued up.
          </h2>
        </div>
      </div>
      <ProfileRows profile={profile} />
      <p className="mt-4 text-[12px] leading-relaxed text-text-secondary">
        Start scan will unlock the workspace, run the repo scanner, and keep these answers in this
        browser session for the rest of the demo.
      </p>
    </div>
  );
}

function ProfileRows({ profile, compact = false }) {
  const rows = [
    ["Company", profile.companyName],
    ["Industry", industryLabel(profile.industry)],
    ["Stage", profile.stage],
    ["Customer", profile.customers],
    ["Sensitive data", profile.sensitiveData],
    ["GTM", profile.gtm],
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
