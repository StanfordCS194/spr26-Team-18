import { useEffect, useState } from "react";
import { Landmark, MessageCircle, Gauge } from "lucide-react";
import Sidebar from "./components/Sidebar";
import StartupGrader from "./components/StartupGrader";
import PlaceholderTab from "./components/PlaceholderTab";

const TAB_IDS = ["startup", "legal", "recs", "financial"];

function tabFromHash() {
  const h = (typeof window !== "undefined" ? window.location.hash : "").slice(1);
  return TAB_IDS.includes(h) ? h : "startup";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash);

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
      <main className="ml-60 px-10 pb-20 pt-10">
        <div className="mx-auto max-w-[1080px] animate-fade-in" key={activeTab}>
          {activeTab === "startup" && <StartupGrader />}
          {activeTab === "legal" && (
            <PlaceholderTab
              Icon={Landmark}
              title="Legal Intelligence"
              description="Contract analyzer for SAFEs, term sheets, and customer MSAs. Compares clauses to YC standard, surfaces redlines, and tells you what a real lawyer would charge to find the same issues."
            />
          )}
          {activeTab === "recs" && (
            <PlaceholderTab
              Icon={MessageCircle}
              title="Active Recommendations"
              description="The five highest-leverage actions to take this week, ranked across legal, financial, and compliance. Updates as your grade and runway move."
            />
          )}
          {activeTab === "financial" && (
            <PlaceholderTab
              Icon={Gauge}
              title="Financial Compliance"
              description="Runway forecasting with calibrated uncertainty bands. Transaction categorization from Mercury, Stripe, and Gusto. R&D tax credit estimation and federal/state filing tracker."
            />
          )}
        </div>
      </main>
    </div>
  );
}
