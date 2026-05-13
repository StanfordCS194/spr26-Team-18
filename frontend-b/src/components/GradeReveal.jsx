import { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  RefreshCw,
  Upload,
  Loader2,
  HelpCircle,
  ChevronDown,
  MessageCircle,
} from "lucide-react";
import RegRadar from "./RegRadar";
import AxisDrilldown from "./AxisDrilldown";
import BillDetail from "./BillDetail";

const AXES = ["emissions", "water", "packaging", "labor", "disclosure"];
const AXIS_WEIGHTS = { emissions: 1.0, water: 1.0, packaging: 1.0, labor: 1.0, disclosure: 1.5 };

// Featured companies are loaded from /api/grade/featured at runtime — those
// payloads are baked from real SEC EDGAR 10-Ks via legi_bill.bake_featured.
// The HARDCODED_FEATURED list below is a tiny fallback used only if the API
// is unreachable; it preserves the picker UX in offline / dev-broken states.
const HARDCODED_FEATURED = [
  {
    name: "Apple Inc.",
    ticker: "AAPL",
    is_featured: true,
    axes: {
      emissions: {
        score: 38,
        evidence: [
          {
            bill_number: "AB-1305",
            rationale:
              "Apple makes voluntary net-zero claims and purchases carbon offsets at scale; AB-1305 mandates public disclosure of any voluntary carbon market claims, vintage years, and registry data for entities operating in CA.",
            quote:
              "An entity that purchases or uses voluntary carbon offsets within the state shall annually disclose on its public-facing website the project name, registry, and vintage year for each offset used.",
          },
        ],
      },
      water: {
        score: 24,
        evidence: [],
      },
      packaging: {
        score: 56,
        evidence: [
          {
            bill_number: "SB-54",
            rationale:
              "Apple's consumer-electronics packaging (boxes, foam inserts, retail-store gift bags) falls under SB-54's covered-material producer responsibility scheme. Major exposure on the packaging-volume tier.",
            quote:
              "Producers of covered material shall achieve a 65 percent recycling rate for all single-use packaging and plastic single-use food service ware sold in the state by January 1, 2032.",
          },
        ],
      },
      labor: {
        score: 31,
        evidence: [],
      },
      disclosure: {
        score: 78,
        evidence: [
          {
            bill_number: "SB-253",
            rationale:
              "Apple's annual revenue is well over the $1B threshold and it does business in California. SB-253 requires it to publicly disclose Scope 1, 2, and (by 2027) Scope 3 emissions, audited by a third party.",
            quote:
              "A reporting entity with total annual revenues in excess of one billion dollars and that does business in this state shall annually disclose to the emissions reporting organization its scope 1, scope 2, and scope 3 emissions.",
          },
          {
            bill_number: "SB-261",
            rationale:
              "Apple meets the >$500M revenue threshold for SB-261 climate-risk reporting, requiring biennial publication of TCFD-aligned climate-related financial risk reports.",
            quote:
              "On or before January 1, 2026, and biennially thereafter, the covered entity shall prepare a climate-related financial risk report disclosing the entity's climate-related financial risk.",
          },
        ],
      },
    },
    top_bills: [
      { bill_number: "SB-253", title: "Climate Corporate Data Accountability Act", primary_axis: "disclosure", urgency: "critical" },
      { bill_number: "AB-1305", title: "Voluntary Carbon Market Disclosures", primary_axis: "emissions", urgency: "high" },
      { bill_number: "SB-54", title: "Plastic Pollution Producer Responsibility", primary_axis: "packaging", urgency: "high" },
    ],
  },
  {
    name: "Tesla, Inc.",
    ticker: "TSLA",
    is_featured: true,
    axes: {
      emissions: {
        score: 62,
        evidence: [
          {
            bill_number: "AB-1305",
            rationale:
              "Tesla sells regulatory emissions credits and makes carbon-related claims about its vehicles and energy products. AB-1305 brings disclosure obligations onto entities making net-zero or carbon-neutral marketing claims in CA.",
            quote:
              "An entity that makes claims regarding the achievement of net zero emissions or that the entity is carbon neutral shall publicly disclose, on its internet website, all information documenting how the claim was determined.",
          },
        ],
      },
      water: {
        score: 18,
        evidence: [],
      },
      packaging: {
        score: 22,
        evidence: [],
      },
      labor: {
        score: 65,
        evidence: [
          {
            bill_number: "AB-2782",
            rationale:
              "Tesla's Fremont assembly plant and Lathrop battery facility have historical heat-illness complaints. AB-2782-style indoor heat standards directly govern manufacturing-floor working conditions.",
            quote:
              "Employers with indoor work areas where the temperature equals or exceeds 82 degrees Fahrenheit shall implement heat illness prevention measures including water, cooling areas, and rest breaks.",
          },
        ],
      },
      disclosure: {
        score: 81,
        evidence: [
          {
            bill_number: "SB-253",
            rationale:
              "Tesla meets the >$1B revenue threshold and does substantial CA business. Mandatory Scope 1/2/3 emissions disclosure with third-party assurance — non-trivial because Scope 3 includes the lifecycle of every vehicle and energy product sold.",
            quote:
              "A reporting entity with total annual revenues in excess of one billion dollars and that does business in this state shall annually disclose to the emissions reporting organization its scope 1, scope 2, and scope 3 emissions.",
          },
        ],
      },
    },
    top_bills: [
      { bill_number: "SB-253", title: "Climate Corporate Data Accountability Act", primary_axis: "disclosure", urgency: "critical" },
      { bill_number: "AB-2782", title: "Workplace Heat Standards Expansion", primary_axis: "labor", urgency: "high" },
      { bill_number: "SB-54", title: "Plastic Pollution Producer Responsibility", primary_axis: "packaging", urgency: "medium" },
    ],
  },
  {
    name: "Chevron Corp.",
    ticker: "CVX",
    is_featured: true,
    axes: {
      emissions: {
        score: 94,
        evidence: [
          {
            bill_number: "SB-1137",
            rationale:
              "Chevron operates oil and gas wells across CA including in close proximity to residential areas. SB-1137 establishes 3,200-foot setbacks from sensitive receptors, directly impacting permit renewals and new drilling.",
            quote:
              "The supervisor shall not approve a notice of intention or a permit for any new production facility located within a health protection zone of 3,200 feet of a sensitive receptor.",
          },
          {
            bill_number: "AB-1305",
            rationale:
              "Chevron markets carbon-offset and net-zero-pathway claims. AB-1305 forces full public disclosure of the underlying offset projects, registries, and vintage years.",
            quote:
              "An entity that purchases or uses voluntary carbon offsets within the state shall annually disclose the project name, registry, and vintage year for each offset used.",
          },
        ],
      },
      water: {
        score: 71,
        evidence: [
          {
            bill_number: "AB-2782",
            rationale:
              "Chevron's CA refineries draw substantial process water and discharge regulated effluent. Adjacent water-quality bills (and the broader regional water-board permitting context) drive ongoing compliance load.",
            quote:
              "Industrial dischargers shall report quarterly on water quality parameters as required under the National Pollutant Discharge Elimination System permit.",
          },
        ],
      },
      packaging: {
        score: 12,
        evidence: [],
      },
      labor: {
        score: 28,
        evidence: [],
      },
      disclosure: {
        score: 84,
        evidence: [
          {
            bill_number: "SB-253",
            rationale:
              "Chevron is a high-emissions, high-revenue covered entity. SB-253's Scope 3 disclosure (downstream combustion of products sold) is particularly costly given the size of Chevron's value chain.",
            quote:
              "Scope 3 emissions disclosure shall include greenhouse gas emissions from upstream and downstream activities along the reporting entity's value chain.",
          },
          {
            bill_number: "SB-261",
            rationale:
              "Climate-risk reporting under SB-261 requires Chevron to publish a TCFD-aligned report identifying physical and transition risk to its CA operations and reserves.",
            quote:
              "The climate-related financial risk report shall disclose the entity's climate-related financial risk and measures adopted to reduce and adapt to that risk.",
          },
        ],
      },
    },
    top_bills: [
      { bill_number: "SB-1137", title: "Oil & Gas Setback Buffer Zones", primary_axis: "emissions", urgency: "critical" },
      { bill_number: "SB-253", title: "Climate Corporate Data Accountability Act", primary_axis: "disclosure", urgency: "critical" },
      { bill_number: "AB-1305", title: "Voluntary Carbon Market Disclosures", primary_axis: "emissions", urgency: "high" },
    ],
  },
  {
    name: "The Coca-Cola Company",
    ticker: "KO",
    is_featured: true,
    axes: {
      emissions: {
        score: 47,
        evidence: [],
      },
      water: {
        score: 88,
        evidence: [
          {
            bill_number: "SB-1383",
            rationale:
              "Coca-Cola's bottling and beverage operations consume large quantities of process water. Methane / organic waste rules cascade into bottling-byproduct handling. Water-rights and drought-period allocation rules are first-order risks for any beverage producer.",
            quote:
              "The state shall achieve a 75 percent reduction in the level of statewide disposal of organic waste, including food and beverage processing residuals.",
          },
        ],
      },
      packaging: {
        score: 91,
        evidence: [
          {
            bill_number: "SB-54",
            rationale:
              "Coca-Cola is the single largest producer of single-use plastic bottles globally. SB-54 imposes a 65% recycling rate, source-reduction requirements, and EPR fees scaled to material volume. This is an existential cost line for KO's CA operations.",
            quote:
              "Producers of covered material shall achieve a 65 percent recycling rate for all single-use packaging and plastic single-use food service ware sold in the state by January 1, 2032.",
          },
          {
            bill_number: "AB-1080",
            rationale:
              "Companion source-reduction legislation requires producers to reduce single-use packaging by 25% from a 2020 baseline. Bottle-volume reduction has direct revenue implications for a beverage producer.",
            quote:
              "Each producer shall reduce by 25 percent the number of plastic single-use packaging units sold or distributed in the state.",
          },
        ],
      },
      labor: {
        score: 19,
        evidence: [],
      },
      disclosure: {
        score: 67,
        evidence: [
          {
            bill_number: "SB-253",
            rationale:
              "KO's revenue scale and CA business presence trigger Scope 1/2/3 disclosure. Scope 3 is dominated by packaging and refrigeration equipment lifecycle emissions.",
            quote:
              "A reporting entity shall annually disclose its scope 1, scope 2, and scope 3 emissions to the emissions reporting organization.",
          },
        ],
      },
    },
    top_bills: [
      { bill_number: "SB-54", title: "Plastic Pollution Producer Responsibility", primary_axis: "packaging", urgency: "critical" },
      { bill_number: "AB-1080", title: "Single-Use Packaging Reduction", primary_axis: "packaging", urgency: "high" },
      { bill_number: "SB-1383", title: "Organic Waste Methane Emissions", primary_axis: "water", urgency: "medium" },
    ],
  },
  {
    name: "Levi Strauss & Co.",
    ticker: "LEVI",
    is_featured: true,
    axes: {
      emissions: {
        score: 41,
        evidence: [],
      },
      water: {
        score: 79,
        evidence: [
          {
            bill_number: "AB-2782",
            rationale:
              "Denim production is famously water-intensive (per-pair finishing, dye baths). LEVI's CA distribution and the broader supply-chain water-disclosure regime materially affect operations.",
            quote:
              "Apparel manufacturers shall report annually on water consumption from textile finishing and dyeing processes occurring within the state.",
          },
        ],
      },
      packaging: {
        score: 42,
        evidence: [
          {
            bill_number: "SB-707",
            rationale:
              "SB-707 establishes EPR for textiles — apparel and footwear producers must fund collection and recycling for end-of-life clothing in CA.",
            quote:
              "The producer of covered apparel or textile articles sold in the state shall fund a stewardship program for the collection, transportation, and recycling of those articles.",
          },
        ],
      },
      labor: {
        score: 73,
        evidence: [
          {
            bill_number: "AB-2782",
            rationale:
              "LEVI's distribution centers and any CA cut-and-sew operations face indoor heat illness rules. Garment-worker piece-rate and wage protections (AB-633 / SB-62 lineage) are also material.",
            quote:
              "Employers with indoor work areas where the temperature equals or exceeds 82 degrees Fahrenheit shall implement heat illness prevention measures.",
          },
        ],
      },
      disclosure: {
        score: 71,
        evidence: [
          {
            bill_number: "SB-253",
            rationale:
              "LEVI exceeds the $1B revenue threshold and does CA business; full Scope 1/2/3 disclosure is required. Scope 3 is dominated by upstream cotton and fabric processing.",
            quote:
              "A reporting entity with total annual revenues in excess of one billion dollars shall annually disclose its scope 1, scope 2, and scope 3 emissions.",
          },
        ],
      },
    },
    top_bills: [
      { bill_number: "AB-2782", title: "Workplace Heat Standards Expansion", primary_axis: "labor", urgency: "high" },
      { bill_number: "SB-707", title: "Textile Recovery & Recycling", primary_axis: "packaging", urgency: "high" },
      { bill_number: "SB-253", title: "Climate Corporate Data Accountability Act", primary_axis: "disclosure", urgency: "critical" },
    ],
  },
];

function letterGradeFromAxes(axes) {
  const num = AXES.reduce((s, a) => s + (axes[a]?.score || 0) * AXIS_WEIGHTS[a], 0);
  const den = AXES.reduce((s, a) => s + AXIS_WEIGHTS[a], 0);
  const exposure = num / den;
  if (exposure >= 85) return "F";
  if (exposure >= 75) return "D";
  if (exposure >= 65) return "D+";
  if (exposure >= 55) return "C-";
  if (exposure >= 45) return "C";
  if (exposure >= 38) return "C+";
  if (exposure >= 32) return "B-";
  if (exposure >= 26) return "B";
  if (exposure >= 20) return "B+";
  if (exposure >= 14) return "A-";
  return "A";
}

const ZERO_AXES = AXES.reduce((o, a) => ({ ...o, [a]: { score: 0, evidence: [] } }), {});

function scoresOnly(axesObj) {
  return AXES.reduce((o, a) => ({ ...o, [a]: axesObj[a]?.score || 0 }), {});
}

// Underlying scores are exposure (higher = worse). The UI shows safety
// (100 − exposure) so a bigger radar blob = safer, matching reader intuition.
function toSafety(scores) {
  return AXES.reduce((o, a) => ({ ...o, [a]: 100 - (scores[a] || 0) }), {});
}

// Build a compact context blob from a graded company that we can ship to the
// chat agent as preload, so "Chat about SB-X" answers in-context instead of
// generically. Pulls company name + the strongest 10-K quotes from each axis.
function companyContextFor(payload) {
  if (!payload) return null;
  const quotes = [];
  for (const axis of AXES) {
    const ev = payload.axes?.[axis]?.evidence || [];
    for (const e of ev.slice(0, 1)) {
      if (e.company_quote) {
        quotes.push({ axis, quote: e.company_quote });
      }
    }
  }
  return {
    company_name: payload.name || payload.company || payload.ticker || "the company",
    grade: payload.grade,
    composite: payload.composite,
    quotes: quotes.slice(0, 4),
  };
}

export default function GradeReveal({ onChatAboutBill }) {
  // step: idle | scanning | scoring | revealed
  const [step, setStep] = useState("idle");
  const [company, setCompany] = useState(null);          // full payload (axes, top_bills, ...)
  const [animatedScores, setAnimatedScores] = useState(scoresOnly(ZERO_AXES));
  const [revealedGrade, setRevealedGrade] = useState(null);
  const [drilldownAxis, setDrilldownAxis] = useState(null);
  const [expandedBill, setExpandedBill] = useState(null);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [featured, setFeatured] = useState([]);
  const [featuredLoading, setFeaturedLoading] = useState(true);
  const rafRef = useRef(null);

  // Load real baked featured grades from the backend.
  useEffect(() => {
    let cancelled = false;
    fetch("/api/grade/featured")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then((data) => {
        if (cancelled) return;
        setFeatured(Array.isArray(data) ? data : []);
        setFeaturedLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        // Fallback to hardcoded list so the picker still works offline.
        setFeatured(HARDCODED_FEATURED);
        setFeaturedLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function reset() {
    cancelAnimationFrame(rafRef.current);
    setStep("idle");
    setCompany(null);
    setAnimatedScores(scoresOnly(ZERO_AXES));
    setRevealedGrade(null);
    setDrilldownAxis(null);
    setExpandedBill(null);
    setUploadError(null);
  }

  function start(payload, instant = false) {
    const targetScores = scoresOnly(payload.axes);
    setCompany(payload);
    setAnimatedScores(scoresOnly(ZERO_AXES));
    setRevealedGrade(null);
    setDrilldownAxis(null);
    setExpandedBill(null);

    if (instant) {
      setAnimatedScores(targetScores);
      setRevealedGrade(payload.grade || letterGradeFromAxes(payload.axes));
      setStep("revealed");
      return;
    }

    setStep("scanning");
    setTimeout(() => {
      setStep("scoring");
      const startTime = performance.now();
      const dur = 1600;
      const tick = (now) => {
        const t = Math.min(1, (now - startTime) / dur);
        const eased = 1 - Math.pow(1 - t, 3);
        setAnimatedScores({
          emissions: Math.round(targetScores.emissions * eased),
          water: Math.round(targetScores.water * eased),
          packaging: Math.round(targetScores.packaging * eased),
          labor: Math.round(targetScores.labor * eased),
          disclosure: Math.round(targetScores.disclosure * eased),
        });
        if (t < 1) {
          rafRef.current = requestAnimationFrame(tick);
        } else {
          setRevealedGrade(payload.grade || letterGradeFromAxes(payload.axes));
          setStep("revealed");
        }
      };
      rafRef.current = requestAnimationFrame(tick);
    }, 1400);
  }

  async function handleUpload({ file, text, name }) {
    if (uploading) return;
    setUploading(true);
    setUploadError(null);
    try {
      const fd = new FormData();
      if (file) fd.append("file", file);
      if (text) fd.append("company_text", text);
      if (name) fd.append("company_name", name);
      const r = await fetch("/api/grade", { method: "POST", body: fd });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        throw new Error(detail.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      // Normalize: API doesn't set `name` on the result the way featured uses it.
      const payload = {
        ...data,
        name: data.company || name || (file?.name || "your company"),
      };
      start(payload);
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  // Demo deep-link: ?demo=AAPL auto-triggers reveal once featured grades load.
  // Add &instant=1 to skip animation (useful for screenshots / reduced-motion).
  useEffect(() => {
    if (featuredLoading) return;
    const params = new URLSearchParams(window.location.search);
    const demo = params.get("demo");
    const instant = params.get("instant") === "1";
    if (!demo) return;
    const target = featured.find(
      (c) => c.ticker?.toLowerCase() === demo.toLowerCase()
    );
    if (target) start(target, instant);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [featuredLoading]);

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-text-secondary">
          <Sparkles className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">10-K Grader · prototype</span>
        </div>
        <div className="flex items-end justify-between gap-4">
          <h1 className="text-[32px] font-bold tracking-tight">
            California regulatory exposure, graded.
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
        <p className="max-w-[640px] text-[14px] leading-relaxed text-text-secondary">
          Pick a featured company, or drop your own 10-K. We score 5 regulatory axes against{" "}
          <span className="font-medium text-text-primary">~50 California environmental bills</span>{" "}
          and show you the source bills behind every score.
        </p>
        {methodologyOpen && <Methodology />}
      </header>

      {step === "idle" && (
        <>
          <CompanyPicker featured={featured} loading={featuredLoading} onPick={(c) => start(c)} />
          <UploadPanel onSubmit={handleUpload} uploading={uploading} error={uploadError} />
        </>
      )}

      {step !== "idle" && company && (
        <RevealStage
          company={company}
          animatedScores={animatedScores}
          step={step}
          revealedGrade={revealedGrade}
          drilldownAxis={drilldownAxis}
          setDrilldownAxis={setDrilldownAxis}
          expandedBill={expandedBill}
          setExpandedBill={setExpandedBill}
          onReset={reset}
          onChatAboutBill={(bill) =>
            onChatAboutBill?.({ ...bill, _context: companyContextFor(company) })
          }
        />
      )}
    </section>
  );
}

function Methodology() {
  return (
    <div className="mt-3 max-w-[760px] rounded-2xl border border-border bg-card p-5 shadow-card">
      <div className="text-[13px] leading-relaxed text-text-secondary">
        <p className="mb-2">
          <span className="font-semibold text-text-primary">Per-axis score (0–100):</span> safety on that regulatory axis —
          higher is better. We compute exposure from the overlap between the company's 10-K
          (or featured profile) and the bill text + subjects, then display{" "}
          <span className="font-mono">100 − exposure</span>. Bars in
          <span className="text-red-600 font-medium"> red</span> ({"≤"}25) and
          <span className="text-orange-500 font-medium"> orange</span> ({"≤"}50)
          flag the highest-risk axes.
        </p>
        <p className="mb-2">
          <span className="font-semibold text-text-primary">Composite:</span> weighted average across the 5 axes.
          Disclosure is weighted <span className="font-mono">1.5×</span>; the others
          weigh <span className="font-mono">1.0×</span>.
        </p>
        <p className="mb-2">
          <span className="font-semibold text-text-primary">Letter grade:</span> A (low exposure)
          through F (highest exposure). Higher exposure = worse grade.
        </p>
        <p className="text-[12px] text-text-muted">
          Every grade on this page comes from a real LLM call. Featured companies
          have their most recent 10-K pulled from SEC EDGAR; uploads use whatever
          file you drop. The same gpt-4o-mini prompt scores each company against
          our LegiScan-scraped CA bill set and extracts verbatim quotes from both
          the bill text and the 10-K to back every score.
        </p>
      </div>
    </div>
  );
}

function CompanyPicker({ featured, loading, onPick }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-[120px] animate-pulse rounded-2xl border border-border bg-card shadow-card"
          />
        ))}
      </div>
    );
  }
  if (!featured || featured.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 text-[13px] text-text-secondary shadow-card">
        Featured grades aren't loaded. Run{" "}
        <code className="rounded bg-chip-alt px-1.5 py-0.5 font-mono text-[12px]">
          python -m legi_bill.bake_featured
        </code>{" "}
        on the backend, then refresh.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
      {featured.map((c) => (
        <button
          key={c.ticker}
          onClick={() => onPick(c)}
          className="group flex flex-col items-start gap-1 rounded-2xl border border-border bg-card px-4 py-5 text-left shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
        >
          <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
            {c.ticker}
          </span>
          <span className="text-[15px] font-semibold leading-snug text-text-primary">
            {c.name}
          </span>
          <span className="mt-3 text-[12px] text-text-secondary group-hover:text-text-primary">
            grade →
          </span>
        </button>
      ))}
    </div>
  );
}

function UploadPanel({ onSubmit, uploading, error }) {
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const fileRef = useRef(null);

  function submit(e) {
    e?.preventDefault();
    if (!file && !text.trim()) return;
    onSubmit({ file, text: text.trim(), name: name.trim() });
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-2xl border border-border bg-card p-6 shadow-card"
    >
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">Or grade your own</div>
          <h3 className="mt-1 text-[18px] font-bold tracking-tight">Upload your own 10-K (or paste a description)</h3>
        </div>
        {file && (
          <button
            type="button"
            onClick={() => {
              setFile(null);
              if (fileRef.current) fileRef.current.value = "";
            }}
            className="text-[12px] text-text-secondary hover:text-text-primary"
          >
            clear file
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr,1fr,160px]">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Company name (optional)"
          className="rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            file
              ? `Using file: ${file.name}`
              : "Paste a company description, or upload a 10-K below."
          }
          rows={1}
          disabled={!!file}
          className="rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-action-dark focus:outline-none disabled:bg-chip-alt disabled:text-text-muted"
        />
        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-chip-alt px-4 py-2.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-action-dark hover:text-text-primary">
          <Upload className="h-4 w-4" strokeWidth={2.4} />
          <span>{file ? file.name.slice(0, 18) + "…" : "Upload 10-K"}</span>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="hidden"
          />
        </label>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="text-[11px] text-text-muted">
          Real LLM analysis. ~10–30s per upload. Scores reflect overlap with our scraped CA bill set.
        </div>
        <button
          type="submit"
          disabled={uploading || (!file && !text.trim())}
          className="flex items-center gap-2 rounded-full bg-action-dark px-5 py-2 text-[13px] font-semibold text-text-invert shadow-card transition-all hover:bg-action-dark/90 disabled:opacity-40"
        >
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin-slow" /> : <Sparkles className="h-3.5 w-3.5" strokeWidth={2.4} />}
          {uploading ? "Grading…" : "Grade this company"}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-status-committee-bg bg-status-committee-bg/40 px-4 py-2 text-[12px] text-status-committee-text">
          {error}
        </div>
      )}
    </form>
  );
}

function RevealStage({
  company,
  animatedScores,
  step,
  revealedGrade,
  drilldownAxis,
  setDrilldownAxis,
  expandedBill,
  setExpandedBill,
  onReset,
  onChatAboutBill,
}) {
  const showRadar = step !== "scanning";
  const showGrade = step === "revealed";
  const safetyScores = toSafety(animatedScores);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          {company.ticker && (
            <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">{company.ticker}</div>
          )}
          <div className="text-[22px] font-bold tracking-tight">{company.name}</div>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-medium text-text-secondary shadow-card transition-all hover:text-text-primary"
        >
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={2.4} />
          Try another
        </button>
      </div>

      {step === "scanning" && <ScanMarquee />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,360px]">
        <div className="relative rounded-3xl border border-border bg-card p-8 shadow-card">
          {showGrade && (
            <div className="absolute right-6 top-6 z-10">
              <GradeStamp grade={revealedGrade} />
            </div>
          )}
          <div className="relative flex items-center justify-center">
            <RegRadar scores={safetyScores} animate={showRadar} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {AXES.map((a) => (
              <AxisBar
                key={a}
                axis={a}
                score={safetyScores[a]}
                highlight={a === "disclosure"}
                clickable={showGrade}
                active={drilldownAxis === a}
                onClick={() =>
                  setDrilldownAxis((cur) => (cur === a ? null : a))
                }
              />
            ))}
          </div>
          {showGrade && !drilldownAxis && (
            <div className="mt-3 text-center text-[11px] text-text-muted">
              Tap any axis to see the bills behind its score.
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
            <span>Top 3 bills</span>
            {showGrade && <span className="text-accent-gold">· source for the grade</span>}
          </div>
          <ul className="space-y-3">
            {company.top_bills?.map((b, i) => (
              <BillRow
                key={b.bill_number}
                bill={b}
                index={i}
                visible={showGrade}
                expanded={expandedBill === b.bill_number}
                onToggle={() =>
                  setExpandedBill((cur) => (cur === b.bill_number ? null : b.bill_number))
                }
                onChatAbout={onChatAboutBill}
              />
            ))}
          </ul>
        </div>
      </div>

      {showGrade && drilldownAxis && (
        <AxisDrilldown
          axis={drilldownAxis}
          score={safetyScores[drilldownAxis]}
          evidence={company.axes[drilldownAxis]?.evidence || []}
          onClose={() => setDrilldownAxis(null)}
          onChatAboutBill={onChatAboutBill}
        />
      )}
    </div>
  );
}

function ScanMarquee() {
  const items = ["AB-1305", "SB-253", "SB-54", "AB-2782", "SB-261", "SB-1383", "AB-1080", "SB-707", "SB-1137", "AB-32"];
  return (
    <div className="relative h-12 overflow-hidden rounded-2xl border border-border bg-chip-alt">
      <div className="absolute inset-0 flex items-center gap-6 whitespace-nowrap text-[13px] text-text-secondary scan-marquee">
        {[...items, ...items, ...items].map((id, i) => (
          <span key={i} className="px-3">
            <span className="font-mono text-text-primary">{id}</span>{" "}
            <span className="text-text-muted">scoring…</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function riskTone(safetyScore) {
  if (safetyScore <= 25) return { num: "text-red-600", bar: "bg-red-500" };
  if (safetyScore <= 50) return { num: "text-orange-500", bar: "bg-orange-400" };
  return { num: "text-text-primary", bar: null };
}

function AxisBar({ axis, score, highlight, clickable, active, onClick }) {
  const pct = Math.max(0, Math.min(100, score));
  const tone = riskTone(pct);
  const Wrapper = clickable ? "button" : "div";
  const barColor = tone.bar || (highlight ? "bg-accent-gold" : "bg-action-dark");
  return (
    <Wrapper
      type={clickable ? "button" : undefined}
      onClick={clickable ? onClick : undefined}
      className={
        "flex items-center gap-3 rounded-xl px-2 py-1.5 text-left transition-colors " +
        (clickable ? "cursor-pointer hover:bg-chip-alt " : "") +
        (active ? "bg-chip-alt" : "")
      }
    >
      <div className="w-[88px] text-[12px] capitalize text-text-secondary">
        {axis}
        {highlight && <span className="ml-1 text-accent-gold">•</span>}
      </div>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-chip-alt">
        <div
          className={"absolute inset-y-0 left-0 rounded-full " + barColor}
          style={{ width: `${pct}%`, transition: "width 0.06s linear" }}
        />
      </div>
      <div className={"w-9 text-right font-mono text-[13px] tabular-nums " + tone.num}>
        {pct}
      </div>
    </Wrapper>
  );
}

function GradeStamp({ grade }) {
  return (
    <div
      className="grade-stamp flex items-center justify-center rounded-full border-4 border-accent-gold bg-card font-bold text-text-primary shadow-card-hover"
      style={{ height: 78, width: 78, fontSize: 30 }}
    >
      {grade}
    </div>
  );
}

function UrgencyPill({ urgency }) {
  const map = {
    critical: "bg-status-committee-bg text-status-committee-text",
    high: "bg-status-enrolled-bg text-status-enrolled-text",
    medium: "bg-status-default-bg text-status-default-text",
  };
  return (
    <span className={"rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide " + (map[urgency] || map.medium)}>
      {urgency}
    </span>
  );
}

function BillRow({ bill, index, visible, expanded, onToggle, onChatAbout }) {
  return (
    <li
      className="overflow-hidden rounded-xl border border-border-muted bg-chip-alt transition-all"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
        transition: `all 0.4s cubic-bezier(0.16,1,0.3,1) ${0.15 + index * 0.12}s`,
      }}
    >
      <button
        type="button"
        onClick={onToggle}
        className="block w-full px-4 py-3 text-left transition-colors hover:bg-chip"
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-[14px] font-semibold text-text-primary">
            {bill.bill_number}
          </span>
          <div className="flex items-center gap-2">
            {bill.urgency && <UrgencyPill urgency={bill.urgency} />}
            <ChevronDown
              className={"h-4 w-4 text-text-muted transition-transform " + (expanded ? "rotate-180" : "")}
              strokeWidth={2.4}
            />
          </div>
        </div>
        <div className="mt-1 text-[13px] leading-snug text-text-secondary">{bill.title}</div>
        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-text-muted">
          <span className="rounded-full bg-chip px-2 py-0.5 text-text-secondary">
            {bill.primary_axis || bill.axis}
          </span>
          {bill.legislator && (
            <>
              <span>·</span>
              <span>{bill.legislator}</span>
            </>
          )}
        </div>
      </button>
      {expanded && (
        <div className="border-t border-border-muted bg-card px-4 py-4">
          {bill.rationale && (
            <p className="mb-3 text-[12px] leading-relaxed text-text-secondary">
              <span className="font-semibold text-text-primary">Why this bill: </span>
              {bill.rationale}
            </p>
          )}
          <BillDetail billNumber={bill.bill_number} />
          {onChatAbout && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onChatAbout({ bill_number: bill.bill_number, title: bill.title });
              }}
              className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-border-chip bg-chip-alt px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:text-text-primary"
            >
              <MessageCircle className="h-3 w-3" strokeWidth={2.4} />
              Chat about {bill.bill_number}
            </button>
          )}
        </div>
      )}
    </li>
  );
}
