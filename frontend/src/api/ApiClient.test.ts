import { describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError } from "./ApiClient";

const issuedSession = {
  game: {
    id: "game-1",
    room_code: "ABC123",
    status: "lobby" as const,
    round_count: 5,
    round_duration_seconds: 60,
    players: [],
  },
  player_id: "player-1",
  session_token: "session-secret",
  reconnect_token: "reconnect-secret",
};

describe("ApiClient", () => {
  it("invokes the browser fetch implementation with the global receiver", async () => {
    const receiverAwareFetcher = vi.fn(function (this: unknown) {
      if (this !== globalThis) {
        throw new TypeError("Illegal invocation");
      }
      return Promise.resolve(
        new Response(JSON.stringify(issuedSession), {
          headers: { "Content-Type": "application/json" },
          status: 201,
        }),
      );
    }) as unknown as typeof fetch;
    const api = new ApiClient("https://api.example.test", receiverAwareFetcher);

    await expect(
      api.createGame({
        display_name: "Mihai",
        round_count: 5,
        round_duration_seconds: 60,
      }),
    ).resolves.toEqual(issuedSession);
  });

  it("sends a strict create request without ambient browser credentials", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(issuedSession), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const api = new ApiClient("https://api.example.test", fetcher);

    const result = await api.createGame({
      display_name: "Mihai",
      round_count: 5,
      round_duration_seconds: 60,
    });

    expect(result).toEqual(issuedSession);
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/games",
      expect.objectContaining({
        body: JSON.stringify({
          display_name: "Mihai",
          round_count: 5,
          round_duration_seconds: 60,
        }),
        credentials: "omit",
        method: "POST",
        referrerPolicy: "no-referrer",
      }),
    );
  });

  it("maps the backend envelope to a safe typed error", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "room_not_found", message: "Game not found" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    const api = new ApiClient("https://api.example.test/", fetcher);

    await expect(api.getGame("ABC123")).rejects.toEqual(
      new ApiError(404, "room_not_found", "Game not found"),
    );
  });

  it("does not expose an unexpected response body in errors", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response("database details", { status: 500 }));
    const api = new ApiClient("https://api.example.test", fetcher);

    const error = await api.getGame("ABC123").catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(ApiError);
    expect(String(error)).not.toContain("database details");
  });
});
