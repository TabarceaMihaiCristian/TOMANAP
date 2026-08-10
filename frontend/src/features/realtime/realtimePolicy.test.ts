import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/ApiClient";

import { invalidationScopesForEvent, isRejectedRealtimeSession } from "./realtimePolicy";

describe("realtime policy", () => {
  it("targets only lobby state for a lobby event", () => {
    expect(invalidationScopesForEvent("lobby.updated")).toEqual(["room"]);
  });

  it("fully resynchronizes authoritative state after reconnect", () => {
    expect(invalidationScopesForEvent("connection.ready")).toEqual([
      "room",
      "round",
      "review",
      "leaderboard",
    ]);
  });

  it("refreshes round results and ranking when a round closes", () => {
    expect(invalidationScopesForEvent("round.closed")).toEqual([
      "room",
      "round",
      "review",
      "leaderboard",
    ]);
  });

  it("distinguishes rejected credentials from temporary failures", () => {
    expect(
      isRejectedRealtimeSession(new ApiError(401, "invalid_session", "Invalid session")),
    ).toBe(true);
    expect(
      isRejectedRealtimeSession(new ApiError(0, "network_error", "Temporarily offline")),
    ).toBe(false);
  });
});
