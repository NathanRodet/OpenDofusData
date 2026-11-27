import { describe, expect, it } from "vitest";
import { changedCount, DEFAULT_SETTINGS, isComplete, sameSettings, validateApiKey, validateServerUrl } from "./settings";

describe("validateServerUrl", () => {
  it("accepts the default host and an https address", () => {
    expect(validateServerUrl(DEFAULT_SETTINGS.serverUrl)).toBeNull();
    expect(validateServerUrl("https://sync.exemple.fr:8443")).toBeNull();
  });

  it("refuses an empty address, a plain http one and garbage", () => {
    expect(validateServerUrl("  ")).not.toBeNull();
    expect(validateServerUrl("http://sync.exemple.fr")).not.toBeNull();
    expect(validateServerUrl("pas une adresse")).not.toBeNull();
  });
});

describe("launch at startup", () => {
  it("is off by default", () => {
    expect(DEFAULT_SETTINGS.launchAtStartup).toBe(false);
  });

  it("counts as a change and breaks equality", () => {
    const draft = { ...DEFAULT_SETTINGS, launchAtStartup: true };
    expect(sameSettings(DEFAULT_SETTINGS, draft)).toBe(false);
    expect(changedCount(DEFAULT_SETTINGS, draft)).toBe(1);
  });
});

describe("dev mode capture", () => {
  it("is off by default", () => {
    expect(DEFAULT_SETTINGS.devCapture).toBe(false);
    expect(DEFAULT_SETTINGS.devCaptureTypes).toBe("");
  });

  it("counts the types to detail as a change", () => {
    expect(changedCount(DEFAULT_SETTINGS, { ...DEFAULT_SETTINGS, devCaptureTypes: "jnj" })).toBe(1);
  });

  it("counts as a change and breaks equality", () => {
    const draft = { ...DEFAULT_SETTINGS, devCapture: true };
    expect(sameSettings(DEFAULT_SETTINGS, draft)).toBe(false);
    expect(changedCount(DEFAULT_SETTINGS, draft)).toBe(1);
  });
});

describe("validateApiKey", () => {
  it("needs a key without spaces", () => {
    expect(validateApiKey("")).not.toBeNull();
    expect(validateApiKey("odk1.abc def")).not.toBeNull();
    expect(validateApiKey("odk1.AAAAAAAAAAA.wWDN")).toBeNull();
  });
});

describe("isComplete", () => {
  it("is false until a key is entered", () => {
    expect(isComplete(DEFAULT_SETTINGS)).toBe(false);
    expect(isComplete({ ...DEFAULT_SETTINGS, apiKey: "odk1.AAAAAAAAAAA.wWDN" })).toBe(true);
  });

  it("is false for a game server that is not in the list (tournaments)", () => {
    expect(isComplete({ ...DEFAULT_SETTINGS, apiKey: "odk1.x.y", gameServer: "Tournois" })).toBe(false);
  });
});

describe("changes", () => {
  it("counts the settings that differ", () => {
    const draft = { ...DEFAULT_SETTINGS, apiKey: "odk1.x.y", logsEnabled: false };
    expect(changedCount(DEFAULT_SETTINGS, draft)).toBe(2);
    expect(sameSettings(DEFAULT_SETTINGS, DEFAULT_SETTINGS)).toBe(true);
  });
});
