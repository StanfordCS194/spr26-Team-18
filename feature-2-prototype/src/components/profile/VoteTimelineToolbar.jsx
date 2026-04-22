import { TopicFilterChips } from "./TopicFilterChips";
import { SessionFilter } from "./SessionFilter";
import { CommitteeToggle } from "./CommitteeToggle";

export function VoteTimelineToolbar() {
  return (
    <div className="toolbar">
      <TopicFilterChips />
      <SessionFilter />
      <CommitteeToggle />
    </div>
  );
}
