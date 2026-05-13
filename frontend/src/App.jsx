import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import StartupGrader from "./components/StartupGrader";
import ActiveRecommendations from "./components/ActiveRecommendations";
import LegalIntelligence from "./components/LegalIntelligence";
import FinancialCompliance from "./components/FinancialCompliance";

const TAB_IDS = ["startup", "legal", "recs", "financial"];

function tabFromHash() {
  const h = (typeof window !== "undefined" ? window.location.hash : "").slice(1);
  return TAB_IDS.includes(h) ? h : "startup";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash);
  const [startupRecommendations, setStartupRecommendations] = useState(null);

  useEffect(() => {
    const onHash = () => setActiveTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function changeTab(id) {
    setActiveTab(id);
    if (window.location.hash !== "#" + id) {
      window.history.replaceState(null, "", "#" + id);
    }
  }

  return (
    <div className="min-h-screen">
      <Sidebar activeTab={activeTab} onTabChange={changeTab} />
      <main className="ml-64 px-10 pb-20 pt-10">
        <div className="mx-auto max-w-[1080px] animate-fade-in" key={activeTab}>
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
