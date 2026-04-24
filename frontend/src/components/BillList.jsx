import { useState, useEffect, useCallback } from "react";
import BillCard from "./BillCard";

export default function BillList() {
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [inputVal, setInputVal] = useState("");

  const fetchBills = useCallback((q) => {
    setLoading(true);
    const url = q ? `/api/bills/search?q=${encodeURIComponent(q)}` : "/api/bills";
    fetch(url)
      .then((r) => r.json())
      .then((d) => { setBills(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchBills(""); }, [fetchBills]);

  function handleSearch(e) {
    e.preventDefault();
    setQuery(inputVal);
    fetchBills(inputVal);
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">California Environmental Bills</h1>
        <p className="page-subtitle">Browse scraped bills and their plain-language summaries. Click any bill to expand.</p>
      </div>

      <form className="search-row" onSubmit={handleSearch}>
        <input
          className="search-input"
          placeholder="Search by title or keyword..."
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
        />
        <button className="search-btn" type="submit">Search</button>
      </form>

      {loading ? (
        <div className="loading">
          <div className="spinner" />
          <span>Loading bills...</span>
        </div>
      ) : bills.length === 0 ? (
        <div className="empty-state">
          <h3>{query ? "No bills matched your search." : "No bills in the database yet."}</h3>
          <p>
            {query
              ? "Try a different search term."
              : <>Run <code>python -m legi_bill.cli scrape --session 2025</code> to populate the database.</>}
          </p>
        </div>
      ) : (
        <div className="bill-list">
          {bills.map((bill) => (
            <BillCard key={bill.bill_number} bill={bill} />
          ))}
        </div>
      )}
    </div>
  );
}
