import { useState } from "react";
import { PrototypeLayout } from "./components/layout/PrototypeLayout";
import { LegislatorSearchPage } from "./pages/LegislatorSearchPage";
import { LegislatorProfilePage } from "./pages/LegislatorProfilePage";
import {
  legislators,
  recentVotes,
  voteTimelineRows,
  metricCards,
  companyImpact,
  matchedTopics,
  relatedVotes,
} from "./data/mockData";

export default function App() {
  const [activePage, setActivePage] = useState("search");
  const [activeLegislator, setActiveLegislator] = useState(legislators[0]);
  const [selectedBill, setSelectedBill] = useState(recentVotes[0]);

  const openProfile = (legislator) => {
    setActiveLegislator(legislator);
    setActivePage("profile");
  };

  return (
    <PrototypeLayout activePage={activePage} onNavigate={setActivePage}>
      {activePage === "search" ? (
        <LegislatorSearchPage
          legislators={legislators}
          recentVotes={recentVotes}
          onSelectLegislator={openProfile}
          onInspectVote={setSelectedBill}
        />
      ) : (
        <LegislatorProfilePage
          legislator={activeLegislator}
          summaryVote={recentVotes[1]}
          metrics={metricCards}
          timelineRows={voteTimelineRows}
          companyImpact={companyImpact}
          matchedTopics={matchedTopics}
          selectedBill={selectedBill}
          relatedVotes={relatedVotes}
          onBackToSearch={() => setActivePage("search")}
          onOpenBill={setSelectedBill}
        />
      )}
    </PrototypeLayout>
  );
}
