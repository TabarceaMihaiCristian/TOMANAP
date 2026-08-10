import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError } from "@/api/ApiClient";
import { ApiProvider } from "@/api/ApiProvider";

import { useSession } from "./sessionContext";
import { SessionProvider } from "./SessionProvider";
import { sessionStore } from "./sessionStore";

const storedSession = {
  playerId: "player-1",
  reconnectToken: "old-reconnect-token",
  roomCode: "ABC123",
  sessionToken: "old-session-token",
};

const restoredSession = {
  game: {
    id: "game-1",
    players: [],
    room_code: "ABC123",
    round_count: 5,
    round_duration_seconds: 60,
    status: "lobby" as const,
  },
  player_id: "player-1",
  reconnect_token: "new-reconnect-token",
  session_token: "new-session-token",
};

function TestHarness({ children, client }: { children: ReactNode; client: ApiClient }) {
  return (
    <ApiProvider client={client}>
      <SessionProvider>{children}</SessionProvider>
    </ApiProvider>
  );
}

function SessionProbe() {
  const { retryRestore, session, status } = useSession();
  return (
    <>
      <output aria-label="status">{status}</output>
      <output aria-label="token">{session?.sessionToken ?? "none"}</output>
      <button onClick={() => void retryRestore()} type="button">
        Retry
      </button>
    </>
  );
}

afterEach(() => {
  sessionStore.clear();
});

describe("SessionProvider", () => {
  it("rotates persisted credentials before marking the session authenticated", async () => {
    sessionStore.save(storedSession);
    const client = new ApiClient("https://api.example.test");
    const restoreSession = vi
      .spyOn(client, "restoreSession")
      .mockResolvedValue(restoredSession);

    render(
      <TestHarness client={client}>
        <SessionProbe />
      </TestHarness>,
    );

    expect(screen.getByLabelText("status")).toHaveTextContent("restoring");
    await waitFor(() =>
      expect(screen.getByLabelText("status")).toHaveTextContent("authenticated"),
    );
    expect(restoreSession).toHaveBeenCalledOnce();
    expect(restoreSession).toHaveBeenCalledWith("old-reconnect-token");
    expect(screen.getByLabelText("token")).toHaveTextContent("new-session-token");
    expect(sessionStore.load()).toEqual({
      playerId: "player-1",
      reconnectToken: "new-reconnect-token",
      roomCode: "ABC123",
      sessionToken: "new-session-token",
    });
  });

  it("retains the reconnect credential after a transient failure and can retry", async () => {
    sessionStore.save(storedSession);
    const user = userEvent.setup();
    const client = new ApiClient("https://api.example.test");
    const restoreSession = vi
      .spyOn(client, "restoreSession")
      .mockRejectedValueOnce(new ApiError(0, "network_error", "Offline"))
      .mockResolvedValueOnce(restoredSession);

    render(
      <TestHarness client={client}>
        <SessionProbe />
      </TestHarness>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("status")).toHaveTextContent("restore-failed"),
    );
    expect(sessionStore.load()).toEqual(storedSession);

    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByLabelText("status")).toHaveTextContent("authenticated"),
    );
    expect(restoreSession).toHaveBeenCalledTimes(2);
  });

  it("clears credentials rejected by the backend", async () => {
    sessionStore.save(storedSession);
    const client = new ApiClient("https://api.example.test");
    vi.spyOn(client, "restoreSession").mockRejectedValue(
      new ApiError(401, "invalid_session", "Invalid session"),
    );

    render(
      <TestHarness client={client}>
        <SessionProbe />
      </TestHarness>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("status")).toHaveTextContent("anonymous"),
    );
    expect(screen.getByLabelText("token")).toHaveTextContent("none");
    expect(sessionStore.load()).toBeNull();
  });
});
