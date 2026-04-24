import { useState } from "react";
import { Landmark, Building2 } from "lucide-react";
import TopNav from "./components/TopNav";
import BillList from "./components/BillList";
import PlaceholderTab from "./components/PlaceholderTab";

export default function App() {
  const [activeTab, setActiveTab] = useState("bills");

  return (
    <>
      <TopNav activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="mx-auto max-w-[900px] px-6 pb-20 pt-10">
        {activeTab === "bills" && <BillList />}
        {activeTab === "legislators" && (
          <PlaceholderTab
            Icon={Landmark}
            title="Legislator Tracker"
            description="See how individual California legislators have voted on environmental bills over time, with AI-generated voting pattern summaries."
          />
        )}
        {activeTab === "company" && (
          <PlaceholderTab
            Icon={Building2}
            title="Company Match"
            description="Upload your 10-K or company description and get back a ranked list of environmental bills that affect your specific operations."
          />
        )}
      </main>
    </>
  );
}
