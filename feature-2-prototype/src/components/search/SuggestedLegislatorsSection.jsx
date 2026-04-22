import { LegislatorCard } from "./LegislatorCard";

export function SuggestedLegislatorsSection({ legislators, onSelectLegislator }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <h3>Suggested legislators</h3>
        <span>{legislators.length} matches</span>
      </div>
      <div className="card-grid">
        {legislators.map((legislator) => (
          <LegislatorCard
            key={legislator.id}
            legislator={legislator}
            onSelect={() => onSelectLegislator(legislator)}
          />
        ))}
      </div>
    </section>
  );
}
