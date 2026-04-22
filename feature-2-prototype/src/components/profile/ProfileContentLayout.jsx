import { VoteTimelinePanel } from "./VoteTimelinePanel";
import { CompanyImpactSidebar } from "./CompanyImpactSidebar";

export function ProfileContentLayout({
  timelineRows,
  companyImpact,
  matchedTopics,
  onOpenBill,
}) {
  return (
    <section className="profile-content-layout">
      <VoteTimelinePanel rows={timelineRows} onOpenBill={onOpenBill} />
      <CompanyImpactSidebar companyImpact={companyImpact} matchedTopics={matchedTopics} />
    </section>
  );
}
