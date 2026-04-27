import { useState, useEffect } from "react";
import { Loader2, ExternalLink } from "lucide-react";

export default function BillDetail({ billNumber }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/bills/${billNumber}`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load bill");
        return r.json();
      })
      .then((d) => { setData(d); setLoading(false); })
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
  if (error) {
    return <div className="py-6 text-center text-sm text-text-muted">Error: {error}</div>;
  }
  if (!data) return null;

  return (
    <div className="mt-5 border-t border-border-muted pt-5">
      {data.summary ? (
        <>
          <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
            Plain-Language Summary
          </p>
          <p className="mb-5 text-[14px] leading-[1.7] text-text-secondary">{data.summary}</p>
        </>
      ) : (
        <>
          <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
            Description
          </p>
          <p className="mb-5 text-[14px] leading-[1.7] text-text-secondary">
            {data.description || "No summary available. Run summarize to generate one."}
          </p>
        </>
      )}

      {data.compliance_questions?.length > 0 && (
        <>
          <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.1em] text-text-muted">
            Compliance Questions
          </p>
          <ul className="mb-4 flex list-none flex-col gap-2.5">
            {data.compliance_questions.map((q, i) => (
              <li
                key={i}
                className="flex gap-2.5 text-[14px] leading-normal text-text-secondary"
              >
                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-accent-gold/40 text-[11px] font-bold text-text-primary">
                  {i + 1}
                </span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        </>
      )}

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
