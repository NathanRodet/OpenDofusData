import { ChevronRight } from "lucide-react";
import { formatTime, prettyJson } from "../lib/format";
import type { LogCategory, LogEntry, LogOrigin, LogStatus } from "../lib/types";

const ORIGIN_LABEL: Record<LogOrigin, string> = { game: "Jeu", server: "Serveur" };
const CATEGORY_LABEL: Record<LogCategory, string> = { hdv: "HDV", brisage: "Brisage", percepteurs: "Percepteurs", other: "Autre" };
const STATUS_LABEL: Record<LogStatus, string> = { analyzed: "Analysé", ignored: "Ignoré", error: "Erreur" };
const STATUS_TONE: Record<LogStatus, string> = { analyzed: "ok", ignored: "skip", error: "bad" };

interface RowProps {
  entry: LogEntry;
  onOpenChange: (id: number, open: boolean) => void;
}

function LogRow({ entry, onOpenChange }: RowProps) {
  const copy = () => void navigator.clipboard.writeText(prettyJson(entry.payload));
  return (
    <details className="rowd" onToggle={(event) => onOpenChange(entry.id, event.currentTarget.open)}>
      <summary className="trow" role="row">
        <span className="mono cell-time" role="cell">{formatTime(entry.at)}</span>
        <span className="dir cell-origin" role="cell">{ORIGIN_LABEL[entry.origin]}</span>
        <span className="cell-category" role="cell"><span className={`cat ${entry.category}`}>{CATEGORY_LABEL[entry.category]}</span></span>
        <span className="cell-status" role="cell"><span className={`tag ${STATUS_TONE[entry.status]}`}>{STATUS_LABEL[entry.status]}</span></span>
        <span className="cell-summary" role="cell">{entry.summary}</span>
        <ChevronRight className="chev" size={16} aria-hidden="true" />
      </summary>
      <div className="jsonbox">
        <div className="jsonbar">
          <span>{entry.payloadNote}</span>
          <button type="button" className="btn small" onClick={copy}>Copier</button>
        </div>
        <pre>{prettyJson(entry.payload)}</pre>
      </div>
    </details>
  );
}

interface TableProps {
  entries: LogEntry[];
  onOpenChange: (id: number, open: boolean) => void;
}

export function LogTable({ entries, onOpenChange }: TableProps) {
  if (entries.length === 0) {
    return <div className="empty compact"><p>Aucun message pour le moment. Les messages analysés apparaissent ici dès que le jeu en envoie.</p></div>;
  }
  return (
    <div className="tablewrap" role="table" aria-label="Messages analysés">
      <div className="thead" role="row">
        <span role="columnheader">Heure</span>
        <span role="columnheader">Origine</span>
        <span role="columnheader">Catégorie</span>
        <span role="columnheader">Statut</span>
        <span role="columnheader">Résumé</span>
        <span />
      </div>
      {entries.map((entry) => <LogRow key={entry.id} entry={entry} onOpenChange={onOpenChange} />)}
    </div>
  );
}
