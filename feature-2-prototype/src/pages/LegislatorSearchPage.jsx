import { PageHeader } from "../components/search/PageHeader";
import { LegislatorSearchBar } from "../components/search/LegislatorSearchBar";
import { LegislatorFilters } from "../components/search/LegislatorFilters";
import { SuggestedLegislatorsSection } from "../components/search/SuggestedLegislatorsSection";
import { RecentVoteActivitySection } from "../components/search/RecentVoteActivitySection";

export function LegislatorSearchPage({
  legislators,
  recentVotes,
  onSelectLegislator,
  onInspectVote,
}) {
  return (
    <section className="page-section">
      <PageHeader
        title="Find legislators by risk profile"
        subtitle="Browse members, compare topical alignment, and jump directly into vote activity."
      />
      <LegislatorSearchBar />
      <LegislatorFilters />
      <SuggestedLegislatorsSection
        legislators={legislators}
        onSelectLegislator={onSelectLegislator}
      />
      <RecentVoteActivitySection votes={recentVotes} onInspectVote={onInspectVote} />
    </section>
  );
}
