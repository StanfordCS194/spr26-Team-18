import { Footer } from "./Footer";
import { PageContainer } from "./PageContainer";
import { TopNav } from "./TopNav";

export function PrototypeLayout({ activePage, onNavigate, children }) {
  return (
    <div className="app-shell">
      <TopNav activePage={activePage} onNavigate={onNavigate} />
      <PageContainer>{children}</PageContainer>
      <Footer />
    </div>
  );
}
