import { BillDetailHeader } from "./drawer/BillDetailHeader";
import { BillSummarySection } from "./drawer/BillSummarySection";
import { LegislatorVoteSection } from "./drawer/LegislatorVoteSection";
import { ComplianceRelevanceSection } from "./drawer/ComplianceRelevanceSection";
import { RelatedVotesSection } from "./drawer/RelatedVotesSection";

export function BillDetailDrawer({ bill, relatedVotes }) {
  return (
    <section className="drawer">
      <BillDetailHeader bill={bill} />
      <BillSummarySection bill={bill} />
      <LegislatorVoteSection bill={bill} />
      <ComplianceRelevanceSection bill={bill} />
      <RelatedVotesSection relatedVotes={relatedVotes} />
    </section>
  );
}
