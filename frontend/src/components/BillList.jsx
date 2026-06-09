import { useState, useEffect, useCallback } from "react";
import { Search, Loader2 } from "lucide-react";
import BillCard from "./BillCard";

const FILTER_DEFS = [
  { id: "all",       label: "All" },
  { id: "chaptered", label: "Chaptered" },
  { id: "committee", label: "In Committee" },
  { id: "other",     label: "Other" },
];

function matchesFilter(bill, activeFilter) {
  if (activeFilter === "all") return true;
  const s = (bill.status || "").toLowerCase();
  if (activeFilter === "chaptered") return s.includes("chaptered");
  if (activeFilter === "committee") return s.includes("committee") || s.includes("introduced");
  return !s.includes("chaptered") && !s.includes("committee") && !s.includes("introduced");
}

function BillSection({ title, subtitle, bills, activeFilter, setActiveFilter }) {
  const filtered = bills.filter((b) => matchesFilter(b, activeFilter));

  return (
    <div className="mb-10">
      <div className="mb-4">
        <h2 className="text-[20px] font-bold text-text-primary">{title}</h2>
        {subtitle && <p className="mt-1 text-[14px] text-text-secondary">{subtitle}</p>}
      </div>

      {bills.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {FILTER_DEFS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveFilter(id)}
              className={
                "rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-colors " +
                (activeFilter === id
                  ? "bg-action-dark text-white"
                  : "border border-border-chip bg-card text-text-secondary hover:border-action-dark hover:text-action-dark")
              }
            >
              {label}
            </button>
          ))}
          <span className="ml-1 text-[12px] font-medium text-text-muted">
            Showing {filtered.length}{filtered.length !== bills.length ? ` of ${bills.length}` : ""} bill{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>
      )}

      {bills.length === 0 ? (
        <div className="rounded-2xl border border-border-muted bg-card px-6 py-8 text-center text-sm text-text-muted">
          No bills in this category yet.
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-border-muted bg-card px-6 py-8 text-center text-sm text-text-muted">
          No bills match this filter.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((bill) => (
            <BillCard key={bill.bill_number} bill={bill} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function BillList() {
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inputVal, setInputVal] = useState("");
  const [searching, setSearching] = useState(false);
  const [budgetFilter, setBudgetFilter] = useState("all");
  const [envFilter, setEnvFilter] = useState("all");

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
    setBudgetFilter("all");
    setEnvFilter("all");
    setSearching(!!inputVal);
    fetchBills(inputVal);
  }

  function handleClear() {
    setInputVal("");
    setSearching(false);
    setBudgetFilter("all");
    setEnvFilter("all");
    fetchBills("");
  }

  const budgetBills = bills.filter((b) => b.category === "budget");
  const rawEnvBills = bills.filter((b) => b.category !== "budget");

  // chaptered bills float to the top
  const envBills = [...rawEnvBills].sort((a, b) => {
    const aChap = (a.status || "").toLowerCase().includes("chaptered") ? 0 : 1;
    const bChap = (b.status || "").toLowerCase().includes("chaptered") ? 0 : 1;
    return aChap - bChap;
  });

  const chapteredCount = bills.filter((b) => (b.status || "").toLowerCase().includes("chaptered")).length;
  const committeeCount = bills.filter((b) => {
    const s = (b.status || "").toLowerCase();
    return s.includes("committee") || s.includes("introduced");
  }).length;

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

      <form onSubmit={handleSearch} className="mb-8 flex gap-2.5">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-text-muted"
            strokeWidth={2}
          />
          <input
            className="w-full rounded-xl border border-border bg-card py-3 pl-11 pr-4 text-[14px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-action-dark focus:ring-2 focus:ring-action/40"
            placeholder="Search across all bills…"
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
        {searching && (
          <button
            type="button"
            onClick={handleClear}
            className="rounded-xl border border-border-chip px-4 py-3 text-[14px] font-semibold text-text-secondary transition-colors hover:border-action-dark hover:text-action-dark"
          >
            Clear
          </button>
        )}
      </form>

      {!loading && bills.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <span className="rounded-full border border-border-chip bg-card px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary">
            {bills.length} bill{bills.length !== 1 ? "s" : ""} total
          </span>
          {chapteredCount > 0 && (
            <span className="rounded-full bg-status-chaptered-bg px-3.5 py-1.5 text-[12px] font-semibold text-status-chaptered-text">
              {chapteredCount} chaptered
            </span>
          )}
          {committeeCount > 0 && (
            <span className="rounded-full bg-status-committee-bg px-3.5 py-1.5 text-[12px] font-semibold text-status-committee-text">
              {committeeCount} in committee
            </span>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center py-20 text-[14px] text-text-muted">
          <Loader2 className="mb-3 h-7 w-7 animate-spin text-accent-gold" />
          <span>Loading bills…</span>
        </div>
      ) : bills.length === 0 ? (
        <div className="rounded-3xl border border-border-muted bg-card px-6 py-16 text-center shadow-card">
          <h3 className="mb-2 text-lg font-semibold text-text-primary">
            {searching ? "No bills matched your search." : "No bills in the database yet."}
          </h3>
          <p className="text-sm leading-relaxed text-text-muted">
            {searching ? (
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
        <>
          {envBills.length > 0 && (
            <BillSection
              title="Environmental Bills"
              subtitle="Bills targeting emissions, water quality, clean energy, and other environmental obligations."
              bills={envBills}
              activeFilter={envFilter}
              setActiveFilter={setEnvFilter}
            />
          )}
          {budgetBills.length > 0 && (
            <BillSection
              title="Budget Bills"
              subtitle="State budget acts that may contain environmental funding provisions."
              bills={budgetBills}
              activeFilter={budgetFilter}
              setActiveFilter={setBudgetFilter}
            />
          )}
        </>
      )}
    </div>
  );
}
