import { LegislatorProfileHeader } from "../components/profile/LegislatorProfileHeader";
import { VotingPatternSummaryCard } from "../components/profile/VotingPatternSummaryCard";
import { MetricsRow } from "../components/profile/MetricsRow";
import { ProfileContentLayout } from "../components/profile/ProfileContentLayout";
import { SaveExportActions } from "../components/profile/SaveExportActions";
import { BillDetailDrawer } from "../components/profile/BillDetailDrawer";

export function LegislatorProfilePage({
  legislator,
  summaryVote,
  metrics,
  timelineRows,
  companyImpact,
  matchedTopics,
  selectedBill,
  relatedVotes,
  onBackToSearch,
  onOpenBill,
}) {
  return (
    <section className="page-section">
      <LegislatorProfileHeader legislator={legislator} onBack={onBackToSearch} />
      <VotingPatternSummaryCard summaryVote={summaryVote} />
      <MetricsRow metrics={metrics} />
      <ProfileContentLayout
        timelineRows={timelineRows}
        companyImpact={companyImpact}
        matchedTopics={matchedTopics}
        onOpenBill={onOpenBill}
      />
      <SaveExportActions />
      <BillDetailDrawer bill={selectedBill} relatedVotes={relatedVotes} />
    </section>
  );
}
