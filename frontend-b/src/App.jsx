import { useEffect, useState } from "react";
import TopNav from "./components/TopNav";
import TickerStrip from "./components/TickerStrip";
import HomePage from "./components/HomePage";
import GetStarted from "./components/GetStarted";
import StartupGrader from "./components/StartupGrader";
import ActiveRecommendations from "./components/ActiveRecommendations";
import LegalIntelligence from "./components/LegalIntelligence";
import FinancialCompliance from "./components/FinancialCompliance";

const TAB_IDS = ["home", "get-started", "startup", "legal", "recs", "financial"];

function tabFromHash() {
  const h = (typeof window !== "undefined" ? window.location.hash : "").slice(1);
  return TAB_IDS.includes(h) ? h : "home";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash);
  const [startupRecommendations, setStartupRecommendations] = useState(null);
  const [completedSteps, setCompletedSteps] = useState(new Set());

  useEffect(() => {
    const onHash = () => setActiveTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Mark "grade" complete when recommendations are produced
  useEffect(() => {
    if (startupRecommendations) {
      setCompletedSteps((prev) => new Set([...prev, "grade"]));
    }
  }, [startupRecommendations]);

  function changeTab(id) {
    setActiveTab(id);
    if (window.location.hash !== "#" + id) {
      window.history.replaceState(null, "", "#" + id);
    }
    // Mark "review" complete when visiting recs after grading
    if (id === "recs" && startupRecommendations) {
      setCompletedSteps((prev) => new Set([...prev, "review"]));
    }
    // Mark "fix" complete when visiting legal or financial after reviewing
    if ((id === "legal" || id === "financial") && completedSteps.has("review")) {
      setCompletedSteps((prev) => new Set([...prev, "fix"]));
    }
  }

  // Badge on Recs tab when grade exists but review step isn't done yet
  const recsBadge = !!startupRecommendations && !completedSteps.has("review");

  return (
    <div className="min-h-screen">
      <TopNav activeTab={activeTab} onTabChange={changeTab} recsBadge={recsBadge} />
      <TickerStrip />
      {/* pt accounts for: topnav (56px) + ticker (32px) = 88px */}
      <main style={{ paddingTop: "88px" }} className="px-10 pb-20">
        <div className="mx-auto max-w-[1080px] animate-fade-in pt-8" key={activeTab}>
          {activeTab === "home" && <HomePage onTabChange={changeTab} />}
          {activeTab === "get-started" && (
            <GetStarted completedSteps={completedSteps} onTabChange={changeTab} />
          )}
          {activeTab === "startup" && (
            <StartupGrader onRecommendationsUpdated={setStartupRecommendations} />
          )}
          {activeTab === "legal" && <LegalIntelligence />}
          {activeTab === "recs" && (
            <ActiveRecommendations
              snapshot={startupRecommendations}
              onGoToStartup={() => changeTab("startup")}
            />
          )}
          {activeTab === "financial" && <FinancialCompliance />}
        </div>
      </main>
    </div>
  );
}
