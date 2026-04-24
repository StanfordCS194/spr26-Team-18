import { useState, useEffect, useCallback } from "react";
import { Search, Loader2 } from "lucide-react";
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
      <div className="mb-7">
        <h1 className="mb-1.5 text-[26px] font-bold text-text-primary">
          California Environmental Bills
        </h1>
        <p className="text-[15px] text-text-secondary">
          Browse scraped bills and their plain-language summaries. Click any bill to expand.
        </p>
      </div>

      <form onSubmit={handleSearch} className="mb-6 flex gap-2.5">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
            strokeWidth={2}
          />
          <input
            className="w-full rounded-[10px] border-[1.5px] border-border bg-card py-[11px] pl-10 pr-4 text-[15px] text-text-primary outline-none transition-colors focus:border-text-primary"
            placeholder="Search by title or keyword..."
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
          />
        </div>
        <button
          type="submit"
          className="rounded-[10px] bg-action-dark px-[22px] py-[11px] text-[15px] font-semibold text-white transition-opacity hover:opacity-85"
        >
          Search
        </button>
      </form>

      {loading ? (
        <div className="flex flex-col items-center py-16 text-[15px] text-text-muted">
          <Loader2 className="mb-3 h-7 w-7 animate-spin text-text-primary" />
          <span>Loading bills...</span>
        </div>
      ) : bills.length === 0 ? (
        <div className="rounded-[14px] bg-card px-6 py-16 text-center shadow-card">
          <h3 className="mb-2 text-lg font-semibold text-text-primary">
            {query ? "No bills matched your search." : "No bills in the database yet."}
          </h3>
          <p className="text-sm leading-relaxed text-text-muted">
            {query ? (
              "Try a different search term."
            ) : (
              <>
                Run{" "}
                <code className="rounded bg-chip-alt px-1.5 py-[1px] text-[13px] text-text-primary">
                  python -m legi_bill.cli scrape --session 2025
                </code>{" "}
                to populate the database.
              </>
            )}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {bills.map((bill) => (
            <BillCard key={bill.bill_number} bill={bill} />
          ))}
        </div>
      )}
    </div>
  );
}
