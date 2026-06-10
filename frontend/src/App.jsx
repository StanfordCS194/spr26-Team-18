import { useEffect, useState } from "react";
import ErrorBoundary from "./components/ErrorBoundary";
import Sidebar from "./components/Sidebar";
import HomePage from "./components/HomePage";
import PublicLanding from "./components/PublicLanding";
import RepoScanner from "./components/RepoScanner";
import IssueCodeReview from "./components/IssueCodeReview";
import Benchmark from "./components/Benchmark";
import StartupGrader from "./components/StartupGrader";
import ActiveRecommendations from "./components/ActiveRecommendations";
import LegalIntelligence from "./components/LegalIntelligence";
import FinancialCompliance from "./components/FinancialCompliance";

const TAB_IDS = ["home", "scanner", "issues", "benchmark", "startup", "legal", "recs", "financial"];
const SESSION_KEY = "legiBill.demoSession.v1";

function tabFromHash() {
  const h = (typeof window !== "undefined" ? window.location.hash : "").slice(1);
  return TAB_IDS.includes(h) ? h : "home";
}

function loadSession() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session) {
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

function clearSession() {
  window.sessionStorage.removeItem(SESSION_KEY);
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash);
  const [startupRecommendations, setStartupRecommendations] = useState(null);
  const [latestRepoScan, setLatestRepoScan] = useState(null);
  const [session, setSession] = useState(loadSession);
  const [scannerHandoff, setScannerHandoff] = useState(null);

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

  function unlockDashboard(nextSession, nextTab = "scanner") {
    saveSession(nextSession);
    setSession(nextSession);
    changeTab(nextTab);
  }

  function handleSignIn() {
    setLatestRepoScan(null);
    setScannerHandoff(null);
    unlockDashboard({ kind: "signin", createdAt: Date.now(), profile: null }, "scanner");
  }

  function handleSignUpComplete(profile) {
    const normalized = {
      ...profile,
      companyName: profile.companyName.trim(),
      repoUrl: profile.repoUrl.trim(),
    };
    const nextSession = { kind: "signup", createdAt: Date.now(), profile: normalized };
    setLatestRepoScan(null);
    setScannerHandoff({ profile: normalized, token: Date.now(), autoStart: true });
    unlockDashboard(nextSession, "scanner");
  }

  function handleLogout() {
    clearSession();
    setSession(null);
    setScannerHandoff(null);
    setLatestRepoScan(null);
    setActiveTab("home");
    window.history.replaceState(null, "", window.location.pathname);
  }

  function handleResetDemo() {
    handleLogout();
    try {
      localStorage.removeItem("startupGrader.lastGrade.v1");
      localStorage.removeItem("startupGrader.latestRecommendations.v1");
      localStorage.removeItem("startupGrader.companyContext.v1");
    } catch {}
    setStartupRecommendations(null);
    setLatestRepoScan(null);
  }

  function handleScanCleared() {
    setLatestRepoScan(null);
  }

  if (!session) {
    return (
      <PublicLanding
        onSignIn={handleSignIn}
        onSignUpComplete={handleSignUpComplete}
      />
    );
  }

  return (
    <div className="min-h-screen">
      <Sidebar
        activeTab={activeTab}
        onTabChange={changeTab}
        profile={session.profile}
        onLogout={handleLogout}
        onResetDemo={handleResetDemo}
        onLogoClick={handleLogout}
      />
      <main className="ml-64 px-10 pb-20 pt-10">
        <ErrorBoundary key={activeTab}>
          <div
            className={`mx-auto animate-fade-in ${activeTab === "issues" ? "max-w-[1420px]" : "max-w-[1080px]"}`}
          >
            {activeTab === "home" && (
              <HomePage
                onTabChange={changeTab}
                profile={session.profile}
                latestRepoScan={latestRepoScan}
                recommendations={startupRecommendations}
              />
            )}
            {activeTab === "scanner" && (
              <RepoScanner
                onScanComplete={setLatestRepoScan}
                onViewIssues={() => changeTab("issues")}
                onScanCleared={handleScanCleared}
                onboardingProfile={scannerHandoff?.profile || session.profile}
                autoStartToken={scannerHandoff?.autoStart ? scannerHandoff.token : null}
                onAutoStartConsumed={() => setScannerHandoff(null)}
                onNavigate={changeTab}
              />
            )}
            {activeTab === "issues" && (
              <IssueCodeReview
                scan={latestRepoScan}
                onGoToScanner={() => changeTab("scanner")}
              />
            )}
            {activeTab === "benchmark" && <Benchmark />}
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
        </ErrorBoundary>
      </main>
    </div>
  );
}
