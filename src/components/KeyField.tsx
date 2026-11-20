import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { KEY_PAGE_URL } from "../lib/servers";
import type { AppStatus, ConnectionTest } from "../lib/types";
import { ExternalLink } from "./ExternalLink";

interface Props {
  value: string;
  error: string | null;
  /** The key state the server reported for the SAVED key; shown only while the field still holds it. */
  status: AppStatus | null;
  savedKey: string;
  test: ConnectionTest | null;
  testing: boolean;
  onChange: (value: string) => void;
  onTest: () => void;
  onRemove: () => void;
}

function GenerateLink() {
  if (KEY_PAGE_URL === "") return <span className="link-off">Générer ma clé sur mon espace (bientôt disponible)</span>;
  return <ExternalLink href={KEY_PAGE_URL}>Générer ma clé sur mon espace</ExternalLink>;
}

function keyMessage(props: Props): { tone: "err" | "ok" | null; text: string | null } {
  const { status, value, savedKey, error } = props;
  if (error !== null) return { tone: "err", text: error };
  if (status === null || value !== savedKey || value === "") return { tone: null, text: null };
  if (status.key === "expired") return { tone: "err", text: "Clé expirée. Génère-en une nouvelle depuis ton espace." };
  if (status.key === "refused") return { tone: "err", text: "Clé refusée par le serveur. Génère-en une nouvelle." };
  if (status.key === "valid" && status.keyExpiresInDays !== null) {
    return { tone: "ok", text: `Clé valide, expire dans ${status.keyExpiresInDays} jours.` };
  }
  return { tone: null, text: null };
}

export function KeyField(props: Props) {
  const { value, test, testing, onChange, onTest, onRemove } = props;
  const [shown, setShown] = useState(false);
  const message = keyMessage(props);
  const invalid = message.tone === "err";
  return (
    <div className="field">
      <label htmlFor="api-key">
        Clé secrète <span className="note">(ne pas partager)</span>
      </label>
      <div className={`input mono${invalid ? " err" : ""}`}>
        <input
          id="api-key"
          type={shown ? "text" : "password"}
          value={value}
          placeholder="Colle ta clé ici"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={invalid}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" className="icon-btn" aria-label={shown ? "Masquer la clé" : "Afficher la clé"} onClick={() => setShown(!shown)}>
          {shown ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
        </button>
      </div>
      {message.text !== null ? <p className={`help ${message.tone ?? ""}`}>{message.text}</p> : null}
      {value === "" ? <p className="help"><GenerateLink /></p> : null}
      {test !== null ? <p className={`help ${test.ok ? "ok" : "err"}`} role="status">{test.message}</p> : null}
      <div className="row spaced">
        <button type="button" className="btn" disabled={testing || value.trim() === ""} onClick={onTest}>
          {testing ? "Test en cours" : "Tester la connexion"}
        </button>
        {value !== "" ? <button type="button" className="btn danger" onClick={onRemove}>Retirer la clé</button> : null}
        {value !== "" && message.tone === "err" ? <GenerateLink /> : null}
      </div>
    </div>
  );
}
