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
        <Loader2 className="mb-2 h-5 w-5 animate-spin text-text-primary" />
        <span>Loading...</span>
      </div>
    );
  }
  if (error) {
    return <div className="py-6 text-center text-sm text-text-muted">Error: {error}</div>;
  }
  if (!data) return null;

  return (
    <div className="mt-[18px] border-t border-border-muted pt-[18px]">
      {data.summary ? (
        <>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.08em] text-text-muted">
            Plain-Language Summary
          </p>
          <p className="mb-5 text-sm leading-[1.7] text-[#2a3a4a]">{data.summary}</p>
        </>
      ) : (
        <>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.08em] text-text-muted">
            Description
          </p>
          <p className="mb-5 text-sm leading-[1.7] text-[#2a3a4a]">
            {data.description || "No summary available. Run summarize to generate one."}
          </p>
        </>
      )}

      {data.compliance_questions?.length > 0 && (
        <>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.08em] text-text-muted">
            Compliance Questions
          </p>
          <ul className="mb-4 flex list-none flex-col gap-2">
            {data.compliance_questions.map((q, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-normal text-[#2a3a4a]">
                <span className="w-5 flex-shrink-0 font-bold text-accent-gold">{i + 1}.</span>
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
          className="mt-1.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-text-primary opacity-70 transition-opacity hover:opacity-100"
        >
          View on leginfo.ca.gov
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
    </div>
  );
}
