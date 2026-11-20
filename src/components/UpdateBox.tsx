import type { AppStatus } from "../lib/types";
import { ProgressBar } from "./ProgressBar";

interface Props {
  status: AppStatus;
  checking: boolean;
  onCheck: () => void;
  onStart: () => void;
}

function megabytes(value: number | null): string {
  return value === null ? "?" : value.toFixed(1).replace(".", ",");
}

export function UpdateBox({ status, checking, onCheck, onStart }: Props) {
  const update = status.update;
  if (update === null) {
    return (
      <div className="row">
        <button type="button" className="btn" disabled={checking} onClick={onCheck}>
          {checking ? "Recherche en cours" : "Rechercher une mise à jour"}
        </button>
        <span className="help inline">Version {status.appVersion}, à jour.</span>
      </div>
    );
  }
  const downloading = update.progress !== null;
  return (
    <div className="update-box">
      <div className="row">
        <b>La version {update.version} est disponible</b>
        <span className="help inline">Version actuelle {status.appVersion}</span>
      </div>
      <p className="help">L'installateur se télécharge et se vérifie, puis l'application se relance toute seule.</p>
      {downloading ? (
        <>
          <ProgressBar value={update.progress ?? 0} label="Téléchargement" tone="info" />
          <div className="facts">
            <span>{update.fileName}</span>
            <b>{update.progress} %</b>
            <span>{megabytes(update.downloadedMb)} Mo sur {megabytes(update.totalMb)} Mo</span>
          </div>
        </>
      ) : null}
      <div className="row spaced">
        <button type="button" className="btn primary" disabled={downloading} onClick={onStart}>
          {downloading ? "Téléchargement en cours" : "Télécharger et relancer"}
        </button>
      </div>
    </div>
  );
}
