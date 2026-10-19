import { useState } from "react";
import { StatusBar } from "./components/StatusBar";
import { LiveBoard } from "./components/LiveBoard";
import { MatchDetailView } from "./components/MatchDetailView";
import { PerformanceView } from "./components/PerformanceView";

type Tab = "live" | "performance";

export default function App() {
  const [tab, setTab] = useState<Tab>("live");
  const [openMatchId, setOpenMatchId] = useState<string | null>(null);

  return (
    <div className="app">
      <StatusBar />

      <nav className="tabs">
        <button className={tab === "live" ? "tab tab--active" : "tab"} onClick={() => { setTab("live"); setOpenMatchId(null); }}>
          Canlı
        </button>
        <button className={tab === "performance" ? "tab tab--active" : "tab"} onClick={() => { setTab("performance"); setOpenMatchId(null); }}>
          Performans
        </button>
      </nav>

      <main className="content">
        {openMatchId ? (
          <MatchDetailView matchId={openMatchId} onBack={() => setOpenMatchId(null)} />
        ) : tab === "live" ? (
          <LiveBoard onOpen={setOpenMatchId} />
        ) : (
          <PerformanceView />
        )}
      </main>

      <footer className="footer">
        Canlı İddaa AI · Gol ve korner olasılık modelleri · Olasılıklar garanti değildir.
      </footer>
    </div>
  );
}
