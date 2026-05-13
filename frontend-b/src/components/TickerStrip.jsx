const ITEMS = [
  "4,821 CA bills tracked",
  "$47,000 avg legal fees automated",
  "350+ attorney hours saved",
  "50+ compliance rules",
  "Grades in under 30 seconds",
  "5 regulatory axes",
  "No law firm needed",
  "State-adjusted rates",
];

// Triplicate so the marquee feels truly infinite
const TICKER = [...ITEMS, ...ITEMS, ...ITEMS];

export default function TickerStrip() {
  return (
    <div className="fixed top-14 left-0 right-0 z-30 flex h-8 items-center overflow-hidden border-b border-[#d4e0ff] bg-[#eef3ff]">
      <div
        className="flex shrink-0 items-center gap-0 whitespace-nowrap scan-marquee"
        style={{ width: "max-content" }}
      >
        {TICKER.map((item, i) => (
          <span key={i} className="flex items-center text-[11px] font-semibold text-[#0052ff]">
            <span className="px-6">{item}</span>
            <span className="text-[#0052ff]/30">·</span>
          </span>
        ))}
      </div>
    </div>
  );
}
