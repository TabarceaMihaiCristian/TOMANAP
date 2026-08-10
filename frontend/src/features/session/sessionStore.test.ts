import { describe, expect, it } from "vitest";

import { createSessionStore } from "./sessionStore";

describe("sessionStore", () => {
  it("persists only the active anonymous capability bundle", () => {
    const store = createSessionStore(localStorage);
    const session = {
      roomCode: "ABC123",
      playerId: "player-1",
      sessionToken: "session-secret",
      reconnectToken: "reconnect-secret",
    };

    store.save(session);

    expect(store.load()).toEqual(session);
    expect(window.location.href).not.toContain("session-secret");
    store.clear();
    expect(store.load()).toBeNull();
  });

  it("discards corrupt persisted data", () => {
    localStorage.setItem("tomanap.session.v1", "not-json");
    const store = createSessionStore(localStorage);

    expect(store.load()).toBeNull();
    expect(localStorage.getItem("tomanap.session.v1")).toBeNull();
  });
});
