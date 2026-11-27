import { ExternalLink as OpenIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import type { ReactNode, RefObject } from "react";
import { Banner } from "../components/Banner";
import { ExternalLink } from "../components/ExternalLink";
import { KeyField } from "../components/KeyField";
import { Switch } from "../components/Switch";
import { UpdateBox } from "../components/UpdateBox";
import { backend } from "../lib/backend";
import { changedCount, DEFAULT_SETTINGS, validateSettings } from "../lib/settings";
import { GAME_SERVERS, KEY_PAGE_URL, NPCAP_URL } from "../lib/servers";
import type { AppStatus, ConnectionTest, Settings } from "../lib/types";

interface Props {
  saved: Settings;
  status: AppStatus | null;
  scrollRef: RefObject<HTMLDivElement | null>;
  onSaved: (settings: Settings) => void;
  onRefreshStatus: () => void;
  onPurged: () => void;
}

function Group({ id, title, hint, children }: { id: string; title: string; hint: string; children: ReactNode }) {
  return (
    <section className="group" id={id} aria-labelledby={`${id}-title`}>
      <div>
        <h2 id={`${id}-title`}>{title}</h2>
        <p className="hint">{hint}</p>
      </div>
      <div className="fields">{children}</div>
    </section>
  );
}

function StatusBanners({ status, onRefresh }: { status: AppStatus; onRefresh: () => void }) {
  return (
    <>
      {status.npcap === "missing" ? (
        <Banner
          tone="warn"
          title="Npcap n'est pas détecté"
          actions={
            <>
              <ExternalLink href={NPCAP_URL} className="btn primary"><OpenIcon size={16} aria-hidden="true" />Ouvrir la page de Npcap</ExternalLink>
              <button type="button" className="btn" onClick={onRefresh}>Vérifier à nouveau</button>
            </>
          }
        >
          La capture ne peut pas démarrer sans lui. Installe-le, puis relance l'application. Aucun droit administrateur n'est requis.
        </Banner>
      ) : null}
      {status.key === "missing" ? (
        <Banner tone="warn" title="Ajoute ta clé d'API pour démarrer">Sans clé, la collecte tourne mais rien n'est envoyé au serveur.</Banner>
      ) : null}
      {status.key === "expired" ? (
        <Banner
          tone="bad"
          title="Ta clé d'API a expiré"
          actions={KEY_PAGE_URL === "" ? undefined : <ExternalLink href={KEY_PAGE_URL} className="btn primary"><OpenIcon size={16} aria-hidden="true" />Mon espace</ExternalLink>}
        >
          Elle vivait un mois. Génère-en une nouvelle depuis ton espace, puis colle-la ici.
        </Banner>
      ) : null}
    </>
  );
}

export function SettingsPage({ saved, status, scrollRef, onSaved, onRefreshStatus, onPurged }: Props) {
  const [draft, setDraft] = useState<Settings>(saved);
  const [submitted, setSubmitted] = useState(false);
  const [test, setTest] = useState<ConnectionTest | null>(null);
  const [testing, setTesting] = useState(false);
  const [checking, setChecking] = useState(false);
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const errors = validateSettings(draft);
  const changes = changedCount(saved, draft);
  const change = (patch: Partial<Settings>) => {
    setDraft({ ...draft, ...patch });
    setTest(null);
  };

  const save = async () => {
    setSubmitted(true);
    if (errors.serverUrl !== null || errors.gameServer !== null || errors.apiKey !== null) return;
    const clean = { ...draft, serverUrl: draft.serverUrl.trim(), apiKey: draft.apiKey.trim() };
    try {
      await backend.saveSettings(clean);
    } catch (error) {
      setSaveError(String(error));
      return;
    }
    setSaveError(null);
    setSubmitted(false);
    onSaved(clean);
    onRefreshStatus();
  };

  const runTest = async () => {
    setTesting(true);
    setTest(await backend.testConnection(draft));
    setTesting(false);
  };

  const check = async () => {
    setChecking(true);
    await backend.checkUpdate();
    setChecking(false);
    onRefreshStatus();
  };

  return (
    <>
      <div className="scroll" ref={scrollRef}>
        {status !== null ? <StatusBanners status={status} onRefresh={onRefreshStatus} /> : null}

        <Group id="serveur" title="Serveur de synchronisation" hint="Où les données collectées sont envoyées.">
          <div className="field">
            <label htmlFor="server-url">Adresse du serveur</label>
            <div className={`input mono${submitted && errors.serverUrl ? " err" : ""}`}>
              <input id="server-url" value={draft.serverUrl} autoComplete="off" spellCheck={false} onChange={(event) => change({ serverUrl: event.target.value })} />
            </div>
            <p className={errors.serverUrl === null ? "help" : "help err"}>
              {errors.serverUrl ?? (draft.serverUrl === DEFAULT_SETTINGS.serverUrl ? "Adresse par défaut." : "Adresse personnalisée.")}
              {draft.serverUrl === DEFAULT_SETTINGS.serverUrl ? null : (
                <>
                  {" "}
                  <button type="button" className="link" onClick={() => change({ serverUrl: DEFAULT_SETTINGS.serverUrl })}>Rétablir l'adresse par défaut</button>
                </>
              )}
            </p>
          </div>
        </Group>

        <Group id="jeu" title="Serveur de jeu" hint="Les prix et brisages sont rangés par serveur de jeu. Le jeu ne l'indique pas, c'est à toi de le choisir.">
          <div className="field">
            <label htmlFor="game-server">Serveur joué</label>
            <div className="input">
              <select id="game-server" value={draft.gameServer} onChange={(event) => change({ gameServer: event.target.value })}>
                {GAME_SERVERS.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
          </div>
        </Group>

        <Group id="cle" title="Clé d'API" hint="Elle identifie ton client auprès du serveur. Tu la génères depuis ton espace utilisateur.">
          <KeyField
            value={draft.apiKey}
            savedKey={saved.apiKey}
            status={status}
            error={submitted || draft.apiKey !== "" ? errors.apiKey : null}
            test={test}
            testing={testing}
            onChange={(apiKey) => change({ apiKey })}
            onTest={() => void runTest()}
            onRemove={() => change({ apiKey: "" })}
          />
        </Group>

        <Group id="journal" title="Journal" hint="Affiche les messages analysés dans l'onglet Logs.">
          <div className="switch">
            <Switch checked={draft.logsEnabled} label="Activer les logs" onChange={(logsEnabled) => change({ logsEnabled })} />
            <div>
              <b>{draft.logsEnabled ? "Logs activés" : "Logs désactivés"}</b>
              <p className="help flush">Désactiver réduit un peu l'activité, la collecte continue.</p>
            </div>
          </div>
        </Group>

        <Group id="demarrage" title="Démarrage" hint="Désactivé par défaut.">
          <div className="switch">
            <Switch checked={draft.launchAtStartup} label="Lancer OpenDofusData au démarrage de Windows" onChange={(launchAtStartup) => change({ launchAtStartup })} />
            <div>
              <b>{draft.launchAtStartup ? "Lancé au démarrage de Windows" : "Lancé à la main"}</b>
              <p className="help flush">Ouvre OpenDofusData à chaque ouverture de session Windows.</p>
            </div>
          </div>
        </Group>

        <Group id="maj" title="Mises à jour et données" hint="Rien n'est gardé sur ce PC sauf si tu enregistres les logs.">
          {status !== null ? (
            <UpdateBox status={status} checking={checking} onCheck={() => void check()} onStart={() => void backend.startUpdate().catch(() => undefined).then(onRefreshStatus)} />
          ) : null}
          <div className="row">
            {confirmPurge ? (
              <>
                <span className="help inline">Supprimer les données locales ?</span>
                <button type="button" className="btn danger" onClick={() => void backend.purgeLocalData().then(() => { setConfirmPurge(false); onPurged(); })}>Oui, purger</button>
                <button type="button" className="btn ghost" onClick={() => setConfirmPurge(false)}>Annuler</button>
              </>
            ) : (
              <button type="button" className="btn danger" onClick={() => setConfirmPurge(true)}>
                <Trash2 size={16} aria-hidden="true" />Purger les données locales
              </button>
            )}
          </div>
        </Group>
      </div>
      <footer className="savebar">
        <span className="msg" role={saveError === null ? undefined : "alert"}>{saveError !== null ? `Enregistrement impossible : ${saveError}` : changes === 0 ? "Aucune modification" : `${changes} modification${changes > 1 ? "s" : ""} non enregistrée${changes > 1 ? "s" : ""}`}</span>
        <button type="button" className="btn ghost" disabled={changes === 0} onClick={() => { setDraft(saved); setSubmitted(false); setTest(null); }}>Annuler</button>
        <button type="button" className="btn primary" disabled={changes === 0} onClick={() => void save()}>Enregistrer</button>
      </footer>
    </>
  );
}
