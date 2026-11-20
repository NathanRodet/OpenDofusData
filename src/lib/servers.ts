/** The game servers a player can choose (the tournament servers are left out on purpose). */
export const GAME_SERVERS = [
  "Brial", "Dakal", "Draconiros", "Hell Mina", "Imagiro", "Kourial", "Mikhal",
  "Ombre", "Orukam", "Rafal", "Salar", "Shukrute", "Tal Kasha", "Tylezia",
] as const;

export const DEFAULT_GAME_SERVER = "Kourial";
export const DEFAULT_SERVER_URL = "opendofusdata.reseaudesentrepreneurs.fr";

export const REPOSITORY_URL = "https://github.com/NathanRodet/OpenDofusData";
export const NPCAP_URL = "https://npcap.com/#download";
export const DOFUSDB_URL = "https://dofusdb.fr/";
/** Empty until the user space exists: the link is then shown as "coming soon". */
export const KEY_PAGE_URL = "";
