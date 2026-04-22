import { VoteTimelineToolbar } from "./VoteTimelineToolbar";
import { VoteTable } from "./VoteTable";

export function VoteTimelinePanel({ rows, onOpenBill }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <h3>Vote timeline</h3>
        <span>Filter by topic, session, and committee context</span>
      </div>
      <VoteTimelineToolbar />
      <VoteTable rows={rows} onOpenBill={onOpenBill} />
    </section>
  );
}
