import { RecentVoteCard } from "./RecentVoteCard";

export function RecentVoteActivitySection({ votes, onInspectVote }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <h3>Recent vote activity</h3>
        <span>Most relevant bills this month</span>
      </div>
      <div className="stack">
        {votes.map((vote) => (
          <RecentVoteCard key={vote.id} vote={vote} onInspect={() => onInspectVote(vote)} />
        ))}
      </div>
    </section>
  );
}
