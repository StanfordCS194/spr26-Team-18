import { useEffect, useState } from "react";
import { Landmark } from "lucide-react";
import Sidebar from "./components/Sidebar";
import Home from "./components/Home";
import BillList from "./components/BillList";
import CompanyMatch from "./components/CompanyMatch";
import FinancialCompliance from "./components/FinancialCompliance";
import GradeReveal from "./components/GradeReveal";
import PlaceholderTab from "./components/PlaceholderTab";

const TAB_IDS = ["home", "bills", "legislators", "company", "grade", "compliance"];

function tabFromHash() {
  const h = (typeof window !== "undefined" ? window.location.hash : "").slice(1);
  return TAB_IDS.includes(h) ? h : "home";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash);
  const [chatPreload, setChatPreload] = useState(null);

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

  function chatAboutBill(bill) {
    setChatPreload(bill);
    changeTab("company");
  }

  return (
    <div className="min-h-screen">
      <Sidebar activeTab={activeTab} onTabChange={changeTab} />
      <main className="ml-60 px-10 pb-20 pt-10">
        <div className="mx-auto max-w-[1080px] animate-fade-in" key={activeTab}>
          {activeTab === "home" && <Home onTabChange={changeTab} />}
          {activeTab === "bills" && <BillList />}
          {activeTab === "legislators" && (
            <PlaceholderTab
              Icon={Landmark}
              title="Legislator Tracker"
              description="See how individual California legislators have voted on environmental bills over time, with AI-generated voting pattern summaries."
            />
          )}
          {activeTab === "company" && (
            <CompanyMatch
              preloadBill={chatPreload}
              onPreloadConsumed={() => setChatPreload(null)}
            />
          )}
          {activeTab === "grade" && <GradeReveal onChatAboutBill={chatAboutBill} />}
          {activeTab === "compliance" && <FinancialCompliance />}
        </div>
      </main>
    </div>
  );
}
