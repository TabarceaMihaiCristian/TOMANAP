import { describe, expect, it, vi } from "vitest";

import { handleRealtimeMessage } from "./realtimeMessages";

describe("handleRealtimeMessage", () => {
  it("answers heartbeat pings without invalidating server state", () => {
    const send = vi.fn();
    const invalidate = vi.fn();

    handleRealtimeMessage(JSON.stringify({ type: "connection.ping" }), {
      invalidate,
      send,
    });

    expect(send).toHaveBeenCalledWith(JSON.stringify({ type: "pong" }));
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("uses domain events as invalidation signals and ignores malformed data", () => {
    const invalidate = vi.fn();
    const send = vi.fn();

    handleRealtimeMessage("not-json", { invalidate, send });
    handleRealtimeMessage(JSON.stringify({ type: "lobby.updated" }), {
      invalidate,
      send,
    });

    expect(invalidate).toHaveBeenCalledWith("lobby.updated");
    expect(send).not.toHaveBeenCalled();
  });
});
