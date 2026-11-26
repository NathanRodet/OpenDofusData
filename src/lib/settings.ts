import { DEFAULT_GAME_SERVER, DEFAULT_SERVER_URL, GAME_SERVERS } from "./servers";
import type { Settings } from "./types";

export const DEFAULT_SETTINGS: Settings = {
  serverUrl: DEFAULT_SERVER_URL,
  gameServer: DEFAULT_GAME_SERVER,
  apiKey: "",
  logsEnabled: true,
  launchAtStartup: false,
};

const HOST_PATTERN = /^(https:\/\/)?([a-z0-9]([a-z0-9-]*[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*(:\d{1,5})?(\/.*)?$/i;
const HOST_MAX_LENGTH = 253;

/** An error message for the server address, or null when it is usable. */
export function validateServerUrl(value: string): string | null {
  const text = value.trim();
  if (text === "") return "Indique l'adresse du serveur.";
  if (text.startsWith("http://")) return "L'adresse doit commencer par https:// ou ne pas avoir de préfixe.";
  if (text.length > HOST_MAX_LENGTH || !HOST_PATTERN.test(text)) return "Cette adresse n'est pas valide.";
  return null;
}

/** An error message for the API key, or null when it is usable. */
export function validateApiKey(value: string): string | null {
  const text = value.trim();
  if (text === "") return "Colle ta clé d'API.";
  if (/\s/.test(text)) return "La clé ne doit contenir aucun espace.";
  return null;
}

export function validateGameServer(value: string): string | null {
  return (GAME_SERVERS as readonly string[]).includes(value) ? null : "Choisis un serveur de la liste.";
}

export interface SettingsErrors {
  serverUrl: string | null;
  apiKey: string | null;
  gameServer: string | null;
}

export function validateSettings(settings: Settings): SettingsErrors {
  return {
    serverUrl: validateServerUrl(settings.serverUrl),
    apiKey: validateApiKey(settings.apiKey),
    gameServer: validateGameServer(settings.gameServer),
  };
}

/** The settings are complete when everything is valid: without a key the app opens on Réglages. */
export function isComplete(settings: Settings): boolean {
  const errors = validateSettings(settings);
  return errors.serverUrl === null && errors.apiKey === null && errors.gameServer === null;
}

export function sameSettings(left: Settings, right: Settings): boolean {
  return left.serverUrl === right.serverUrl && left.gameServer === right.gameServer
    && left.apiKey === right.apiKey && left.logsEnabled === right.logsEnabled
    && left.launchAtStartup === right.launchAtStartup;
}

/** How many settings differ from the saved ones (shown in the save bar). */
export function changedCount(saved: Settings, draft: Settings): number {
  return (Object.keys(saved) as (keyof Settings)[]).filter((name) => saved[name] !== draft[name]).length;
}
