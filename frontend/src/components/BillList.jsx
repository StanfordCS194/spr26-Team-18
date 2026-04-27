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
      <div className="mb-8">
        <h1 className="mb-2 text-[28px] font-bold tracking-tight text-text-primary">
          California Environmental Bills
        </h1>
        <p className="text-[15px] text-text-secondary">
          Browse scraped bills and their plain-language summaries. Click any bill to expand.
        </p>
      </div>

      <form onSubmit={handleSearch} className="mb-6 flex gap-2.5">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-text-muted"
            strokeWidth={2}
          />
          <input
            className="w-full rounded-xl border border-border bg-card py-3 pl-11 pr-4 text-[14px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-action-dark focus:ring-2 focus:ring-action/40"
            placeholder="Search by title or keyword…"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
          />
        </div>
        <button
          type="submit"
          className="rounded-xl bg-action-dark px-6 py-3 text-[14px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
        >
          Search
        </button>
      </form>

      {loading ? (
        <div className="flex flex-col items-center py-20 text-[14px] text-text-muted">
          <Loader2 className="mb-3 h-7 w-7 animate-spin text-accent-gold" />
          <span>Loading bills…</span>
        </div>
      ) : bills.length === 0 ? (
        <div className="rounded-3xl border border-border-muted bg-card px-6 py-16 text-center shadow-card">
          <h3 className="mb-2 text-lg font-semibold text-text-primary">
            {query ? "No bills matched your search." : "No bills in the database yet."}
          </h3>
          <p className="text-sm leading-relaxed text-text-muted">
            {query ? (
              "Try a different search term."
            ) : (
              <>
                Run{" "}
                <code className="rounded-md bg-chip-alt px-1.5 py-[2px] text-[12px] text-text-primary">
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
