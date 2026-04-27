import { useState } from "react";
import { Landmark } from "lucide-react";
import Sidebar from "./components/Sidebar";
import BillList from "./components/BillList";
import CompanyMatch from "./components/CompanyMatch";
import PlaceholderTab from "./components/PlaceholderTab";

export default function App() {
  const [activeTab, setActiveTab] = useState("bills");

  return (
    <div className="min-h-screen">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="ml-60 px-10 pb-20 pt-10">
        <div className="mx-auto max-w-[920px] animate-fade-in" key={activeTab}>
          {activeTab === "bills" && <BillList />}
          {activeTab === "legislators" && (
            <PlaceholderTab
              Icon={Landmark}
              title="Legislator Tracker"
              description="See how individual California legislators have voted on environmental bills over time, with AI-generated voting pattern summaries."
            />
          )}
          {activeTab === "company" && <CompanyMatch />}
        </div>
      </main>
    </div>
  );
}
