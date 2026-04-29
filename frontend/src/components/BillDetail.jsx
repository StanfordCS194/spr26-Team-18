import { useState, useEffect } from "react";
import { Loader2, ExternalLink, CheckSquare, Calendar, Building2, AlertTriangle, ShieldOff } from "lucide-react";

const SECTION_LABELS = ["What it does", "Who it affects", "Key requirements", "Current status"];

function parseSummary(text) {
  if (!text) return null;

  const byNumber = text.split(/(?=\b[1-4][.)]\s)/);
  if (byNumber.length >= 2) {
    const sections = byNumber
      .map((chunk, i) => ({
        label: SECTION_LABELS[i] ?? `Section ${i + 1}`,
        text: chunk.replace(/^[(\d).\s]+/, "").trim(),
      }))
      .filter((s) => s.text.length > 0);
    if (sections.length >= 2) return sections;
  }

  const phraseRegex = /(What it does|Who it affects|Key requirements|Current status)/i;
  const parts = text.split(phraseRegex);
  if (parts.length >= 3) {
    const sections = [];
    for (let i = 1; i < parts.length; i += 2) {
      sections.push({
        label: parts[i],
        text: (parts[i + 1] || "").replace(/^[:\s–-]+/, "").trim(),
      });
    }
    if (sections.length >= 2) return sections;
  }

  return null;
}

const INDUSTRY_COLORS = {
  Agriculture:       "bg-green-100 text-green-800",
  Construction:      "bg-orange-100 text-orange-800",
  Energy:            "bg-yellow-100 text-yellow-800",
  Forestry:          "bg-emerald-100 text-emerald-800",
  Manufacturing:     "bg-blue-100 text-blue-800",
  Mining:            "bg-stone-100 text-stone-800",
  "Real Estate":     "bg-purple-100 text-purple-800",
  Retail:            "bg-pink-100 text-pink-800",
  Technology:        "bg-indigo-100 text-indigo-800",
  Transportation:    "bg-cyan-100 text-cyan-800",
  Utilities:         "bg-amber-100 text-amber-800",
  "Waste Management":"bg-red-100 text-red-800",
  Water:             "bg-sky-100 text-sky-800",
};

function QuickFacts({ metadata }) {
  if (!metadata || Object.keys(metadata).length === 0) return null;
  const facts = [
    { icon: Calendar,      label: "Effective Date",      value: metadata.effective_date },
    { icon: Building2,     label: "Enforcement Agency",  value: metadata.enforcement_agency },
    { icon: AlertTriangle, label: "Penalty",             value: metadata.penalty },
    { icon: ShieldOff,     label: "Exemptions",          value: metadata.exemptions },
  ].filter((f) => f.value && f.value !== "Unknown" && f.value !== "None stated");

  if (facts.length === 0) return null;

  return (
    <div className="mb-5 grid grid-cols-2 gap-2">
      {facts.map(({ icon: Icon, label, value }) => (
        <div key={label} className="rounded-xl bg-chip px-4 py-3">
          <div className="mb-1 flex items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 text-action-dark" strokeWidth={2} />
            <p className="text-[10.5px] font-bold uppercase tracking-[0.08em] text-action-dark">{label}</p>
          </div>
          <p className="text-[13px] leading-snug text-text-secondary">{value}</p>
        </div>
      ))}
    </div>
  );
}

function IndustryTags({ industries }) {
  if (!industries?.length) return null;
  return (
    <div className="mb-5">
      <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
        Affected Industries
      </p>
      <div className="flex flex-wrap gap-1.5">
        {industries.map((ind) => (
          <span
            key={ind}
            className={
              "rounded-full px-2.5 py-1 text-[11px] font-semibold " +
              (INDUSTRY_COLORS[ind] || "bg-chip text-text-secondary")
            }
          >
            {ind}
          </span>
        ))}
      </div>
    </div>
  );
}

function BillTimeline({ history }) {
  if (!history?.length) return null;

  return (
    <div className="mb-5">
      <p className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
        Legislative History
      </p>
      <div className="relative pl-5">
        {/* vertical line */}
        <div className="absolute left-[7px] top-2 bottom-2 w-[2px] bg-border-chip" />
        <div className="flex flex-col gap-3">
          {history.map((event, i) => {
            const isLast = i === history.length - 1;
            return (
              <div key={i} className="relative flex items-start gap-3">
                <div
                  className={
                    "absolute -left-5 mt-[3px] h-3.5 w-3.5 rounded-full border-2 " +
                    (isLast
                      ? "border-action-dark bg-action-dark"
                      : "border-action bg-card")
                  }
                />
                <div>
                  <p className="text-[11px] font-semibold text-text-muted">{event.date}</p>
                  <p className="text-[13px] leading-snug text-text-secondary">{event.action}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function BillDetail({ billNumber }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    setData(null);
    fetch(`/api/bills/${billNumber}`)
      .then((r) => {
        if (r.status === 404) {
          setNotFound(true);
          setLoading(false);
          return null;
        }
        if (!r.ok) throw new Error("Failed to load bill");
        return r.json();
      })
      .then((d) => {
        if (d) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [billNumber]);

  if (loading) {
    return (
      <div className="flex flex-col items-center py-8 text-sm text-text-muted">
        <Loader2 className="mb-2 h-5 w-5 animate-spin text-accent-gold" />
        <span>Loading…</span>
      </div>
    );
  }
  if (error) return <div className="py-6 text-center text-sm text-text-muted">Error: {error}</div>;
  if (!data) return null;

  const rawText = data.summary || data.description;
  const sections = rawText ? parseSummary(rawText) : null;

  return (
    <div className="mt-5 border-t border-border-muted pt-5">

      {/* Quick facts */}
      <QuickFacts metadata={data.metadata} />

      {/* Industry tags */}
      <IndustryTags industries={data.metadata?.industries} />

      {/* Summary */}
      {rawText && (
        <div className="mb-5">
          <p className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
            Plain-Language Summary
          </p>
          {sections ? (
            <div className="flex flex-col gap-2">
              {sections.map(({ label, text }) => (
                <div key={label} className="rounded-xl bg-chip px-4 py-3">
                  <p className="mb-1 text-[10.5px] font-bold uppercase tracking-[0.08em] text-action-dark">{label}</p>
                  <p className="text-[14px] leading-[1.7] text-text-secondary">{text}</p>
                </div>
              ))}
            </div>
          ) : (
            <blockquote className="rounded-xl border-l-4 border-action bg-chip py-3 pl-4 pr-4 text-[14px] italic leading-[1.7] text-text-secondary">
              {rawText}
            </blockquote>
          )}
        </div>
      )}

      {/* Compliance questions */}
      {data.compliance_questions?.length > 0 && (
        <div className="mb-5">
          <p className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
            Compliance Questions
          </p>
          <div className="flex flex-col gap-2">
            {data.compliance_questions.map((q, i) => (
              <div key={i} className="flex items-start gap-3 rounded-xl border-l-4 border-action bg-chip px-4 py-3">
                <CheckSquare className="mt-[2px] h-4 w-4 flex-shrink-0 text-action-dark" strokeWidth={1.75} />
                <span className="text-[14px] leading-[1.6] text-text-secondary">{q}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legislative timeline */}
      <BillTimeline history={data.history} />

      {/* External link */}
      {data.url && (
        <a
          href={data.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="mt-1.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-action-dark transition-opacity hover:opacity-80"
        >
          View on leginfo.ca.gov
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
    </div>
  );
}
