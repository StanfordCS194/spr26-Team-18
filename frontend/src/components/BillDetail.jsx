import { useState, useEffect } from "react";

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

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading...</span></div>;
  if (error) return <div className="loading">Error: {error}</div>;
  if (!data) return null;

  return (
    <div className="bill-detail">
      {data.summary ? (
        <>
          <p className="detail-section-label">Plain-Language Summary</p>
          <p className="detail-summary">{data.summary}</p>
        </>
      ) : (
        <>
          <p className="detail-section-label">Description</p>
          <p className="detail-summary">{data.description || "No summary available. Run summarize to generate one."}</p>
        </>
      )}

      {data.compliance_questions?.length > 0 && (
        <>
          <p className="detail-section-label">Compliance Questions</p>
          <ul className="compliance-list">
            {data.compliance_questions.map((q, i) => (
              <li key={i} className="compliance-item">
                <span className="compliance-num">{i + 1}.</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {data.url && (
        <a className="bill-link" href={data.url} target="_blank" rel="noopener noreferrer">
          View on leginfo.ca.gov ↗
        </a>
      )}
    </div>
  );
}
