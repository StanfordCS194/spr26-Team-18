import { CompanyImpactCard } from "./CompanyImpactCard";
import { MatchedTopicsList } from "./MatchedTopicsList";
import { DirectionalTakeawayCard } from "./DirectionalTakeawayCard";

export function CompanyImpactSidebar({ companyImpact, matchedTopics }) {
  return (
    <aside className="sidebar-stack">
      <CompanyImpactCard companyImpact={companyImpact} />
      <MatchedTopicsList topics={matchedTopics} />
      <DirectionalTakeawayCard />
    </aside>
  );
}
