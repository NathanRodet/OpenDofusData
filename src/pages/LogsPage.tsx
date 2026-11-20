import { Download, List, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { RefObject } from "react";
import { ExternalLink } from "../components/ExternalLink";
import { LogTable } from "../components/LogTable";
import { StatCard } from "../components/StatCard";
import { VISIBLE_LOGS } from "../hooks/useLogs";
import { backend } from "../lib/backend";
import { formatNumber, formatTime, percent } from "../lib/format";
import { DOFUSDB_URL } from "../lib/servers";
import type { LogEntry, LogStatus, SyncProgress } from "../lib/types";

type Filter = "all" | LogStatus;

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Tous" },
  { id: "analyzed", label: "Analysés" },
  { id: "ignored", label: "Ignorés" },
  { id: "error", label: "Erreurs" },
];

interface Props {
  logsEnabled: boolean;
  sync: SyncProgress | null;
  entries: LogEntry[];
  allEntries: () => LogEntry[];
  scrollRef: RefObject<HTMLDivElement | null>;
  onEnableLogs: () => void;
  onClear: () => void;
}

function SyncCards({ sync }: { sync: SyncProgress }) {
  const { reference, sent, received } = sync;
  return (
    <div className="stats" id="synchronisation">
      <StatCard
        title="Données de référence" big={formatNumber(reference.done)} unit={`/ ${formatNumber(reference.total)} objets`}
        progress={percent(reference.done, reference.total)} label="Données de référence" tone="ok"
        facts={<><span>Depuis <ExternalLink href={DOFUSDB_URL}>DofusDB</ExternalLink></span><b>{percent(reference.done, reference.total)} %</b></>}
      />
      <StatCard
        title="Envoyées au serveur" big={formatNumber(sent.done)} unit={`/ ${formatNumber(sent.total)} éléments`}
        progress={percent(sent.done, sent.total)} label="Envoi au serveur"
        facts={<><b>{percent(sent.done, sent.total)} %</b><span>{formatNumber(sent.pending)} en attente</span><span>{formatNumber(sent.errors)} erreur{sent.errors > 1 ? "s" : ""}</span></>}
      />
      <StatCard
        title="Reçues du serveur" big={formatNumber(received.count)} unit="éléments"
        progress={100} label="Réception" tone="info"
        facts={<><b>À jour</b><span>Dernière réception {received.lastAt === null ? "aucune" : formatTime(received.lastAt)}</span></>}
      />
    </div>
  );
}

export function LogsPage({ logsEnabled, sync, entries, allEntries, scrollRef, onEnableLogs, onClear }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");

  const [opened, setOpened] = useState<number[]>([]);
  const [frozen, setFrozen] = useState<LogEntry[] | null>(null);

  /** The list stops moving while a line is open, so its JSON stays under the eyes and the cursor. */
  const onOpenChange = (id: number, isOpen: boolean) => {
    const next = isOpen ? [...opened.filter((other) => other !== id), id] : opened.filter((other) => other !== id);
    setOpened(next);
    setFrozen(next.length === 0 ? null : (frozen ?? entries));
  };

  /** Empties the list and the session memory: what was not saved to a file is gone. */
  const clear = () => {
    setOpened([]);
    setFrozen(null);
    onClear();
  };

  const source = frozen ?? entries;
  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return source.filter((entry) => (filter === "all" || entry.status === filter)
      && (needle === "" || entry.summary.toLowerCase().includes(needle)));
  }, [source, filter, search]);

  return (
    <div className="scroll" ref={scrollRef}>
      <span id="connexion" className="anchor" />
      {sync !== null ? <SyncCards sync={sync} /> : null}
      {logsEnabled ? (
        <section id="messages">
          <div className="toolbar">
            <div className="chips" role="group" aria-label="Filtrer par statut">
              {FILTERS.map((item) => (
                <button key={item.id} type="button" className="chip" aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}</button>
              ))}
            </div>
            <div className="input search">
              <Search size={16} aria-hidden="true" />
              <input placeholder="Rechercher" aria-label="Rechercher dans les logs" value={search} onChange={(event) => setSearch(event.target.value)} />
            </div>
            <span className="spacer" />
            <button type="button" className="btn" onClick={() => void backend.saveLogs(allEntries())}>
              <Download size={16} aria-hidden="true" />Enregistrer les logs
            </button>
            <button type="button" className="btn danger" aria-label="Vider les logs" title="Vider les logs" disabled={entries.length === 0 && frozen === null} onClick={clear}>
              <Trash2 size={16} aria-hidden="true" />
              <span className="btn-label">Vider les logs</span>
            </button>
          </div>
          <LogTable entries={shown} onOpenChange={onOpenChange} />
          <div className="foot">
            <span>{frozen === null ? `${VISIBLE_LOGS} dernières lignes affichées` : "Liste en pause pendant la lecture, referme la ligne pour reprendre"}</span>
            <span>Le fichier enregistré contient tout depuis le lancement</span>
          </div>
        </section>
      ) : (
        <section id="messages" className="empty">
          <List size={28} aria-hidden="true" />
          <h3>Le journal est désactivé</h3>
          <p>La collecte et l'envoi continuent. Active les logs pour voir les messages analysés.</p>
          <button type="button" className="btn primary" onClick={onEnableLogs}>Activer les logs</button>
        </section>
      )}
    </div>
  );
}
