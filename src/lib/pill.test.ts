import { describe, expect, it } from "vitest";
import type { AppStatus } from "./types";
import { pillView } from "./pill";

const HOST = "opendofusdata.reseaudesentrepreneurs.fr";

const connected = { npcap: "ok", key: "valid", connection: "connected", latencyMs: 255 } as unknown as AppStatus;
const unreachable = { npcap: "ok", key: "valid", connection: "unreachable", latencyMs: null } as unknown as AppStatus;

describe("pillView", () => {
  it("makes the server host a link to its https address when connected", () => {
    const view = pillView(connected, HOST);
    expect(view.text).toBe("Connecté à");
    expect(view.link).toEqual({ href: `https://${HOST}`, label: HOST });
    expect(view.ping).toBe("255 ms");
  });

  it("has no link when the server cannot be reached", () => {
    expect(pillView(unreachable, HOST).link).toBeNull();
    expect(pillView(null, HOST).link).toBeNull();
  });
});
