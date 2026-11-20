import { useEffect, useRef, useState } from "react";
import { Rail, SubNav, TabBar } from "./components/Navigation";
import { StatusPill } from "./components/StatusPill";
import { useLogs } from "./hooks/useLogs";
import { usePolling } from "./hooks/usePolling";
import { useScrollSpy } from "./hooks/useScrollSpy";
import { backend } from "./lib/backend";
import { PAGE_TITLES, SECTION_IDS } from "./lib/sections";
import { isComplete } from "./lib/settings";
import type { Page, Settings } from "./lib/types";
import { LogsPage } from "./pages/LogsPage";
import { SettingsPage } from "./pages/SettingsPage";

const STATUS_PERIOD_MS = 1500;
const SYNC_PERIOD_MS = 2000;

function hostOf(serverUrl: string): string {
  const withoutScheme = serverUrl.trim().replace(/^https:\/\//, "");
  return withoutScheme.split("/")[0];
}

export default function App() {
  const [saved, setSaved] = useState<Settings | null>(null);
  const [page, setPage] = useState<Page>("logs");
  const [status, refreshStatus] = usePolling(backend.getStatus, STATUS_PERIOD_MS);
  const [sync] = usePolling(backend.getSync, SYNC_PERIOD_MS);
  const logs = useLogs(saved?.logsEnabled ?? false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const spy = useScrollSpy(scrollRef, SECTION_IDS[page], `${page}-${saved?.logsEnabled}-${sync === null}`);

  useEffect(() => {
    void backend.loadSettings().then((loaded) => {
      setSaved(loaded);
      setPage(isComplete(loaded) ? "logs" : "settings");
    });
  }, []);

  if (saved === null) return null;

  const enableLogs = () => {
    const next = { ...saved, logsEnabled: true };
    void backend.saveSettings(next).then(() => setSaved(next));
  };
  const settingsKey = [saved.serverUrl, saved.gameServer, saved.apiKey, saved.logsEnabled].join("|");

  return (
    <div className="app">
      <Rail page={page} activeSection={spy.active} appVersion={status?.appVersion ?? ""} onPage={setPage} onSection={spy.scrollTo} />
      <section className="main">
        <header className="topbar">
          <h1>{PAGE_TITLES[page]}</h1>
          <StatusPill status={status} host={hostOf(saved.serverUrl)} />
        </header>
        <SubNav page={page} activeSection={spy.active} onSection={spy.scrollTo} />
        {page === "logs" ? (
          <LogsPage
            logsEnabled={saved.logsEnabled}
            sync={sync}
            entries={logs.visible}
            allEntries={logs.all}
            scrollRef={scrollRef}
            onEnableLogs={enableLogs}
            onClear={logs.clear}
          />
        ) : (
          <SettingsPage key={settingsKey} saved={saved} status={status} scrollRef={scrollRef} onSaved={setSaved} onRefreshStatus={refreshStatus} onPurged={logs.clear} />
        )}
        <TabBar page={page} onPage={setPage} />
      </section>
    </div>
  );
}
