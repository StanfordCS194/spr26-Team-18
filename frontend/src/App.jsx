import { useState } from "react";
import TopNav from "./components/TopNav";
import BillList from "./components/BillList";
import PlaceholderTab from "./components/PlaceholderTab";

export default function App() {
  const [activeTab, setActiveTab] = useState("bills");

  return (
    <>
      <TopNav activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="page">
        {activeTab === "bills" && <BillList />}
        {activeTab === "legislators" && (
          <PlaceholderTab
            icon="🏛️"
            title="Legislator Tracker"
            description="See how individual California legislators have voted on environmental bills over time, with AI-generated voting pattern summaries."
          />
        )}
        {activeTab === "company" && (
          <PlaceholderTab
            icon="🏢"
            title="Company Match"
            description="Upload your 10-K or company description and get back a ranked list of environmental bills that affect your specific operations."
          />
        )}
      </main>
    </>
  );
}
