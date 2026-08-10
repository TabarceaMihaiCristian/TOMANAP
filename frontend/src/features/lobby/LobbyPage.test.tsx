import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/api/ApiClient";
import { sessionStore } from "@/features/session/sessionStore";
import { renderApp } from "@/test/render";

import { LobbyPage } from "./LobbyPage";

const game = {
  id: "game-1",
  room_code: "ABC123",
  status: "lobby" as const,
  round_count: 5,
  round_duration_seconds: 60,
  players: [
    {
      id: "host-1",
      display_name: "Mihai",
      seat_number: 1,
      is_host: true,
      is_ready: false,
      is_connected: true,
    },
    {
      id: "guest-1",
      display_name: "Ana",
      seat_number: 2,
      is_host: false,
      is_ready: false,
      is_connected: true,
    },
  ],
};

function renderLobby(client: ApiClient) {
  return renderApp(
    <Routes>
      <Route element={<LobbyPage />} path="/room/:roomCode" />
    </Routes>,
    { client, route: "/room/ABC123" },
  );
}

describe("LobbyPage", () => {
  it("shows room membership and lets a guest become ready", async () => {
    const user = userEvent.setup();
    sessionStore.save({
      playerId: "guest-1",
      reconnectToken: "reconnect-secret",
      roomCode: "ABC123",
      sessionToken: "session-secret",
    });
    const client = new ApiClient("https://api.example.test");
    vi.spyOn(client, "getGame").mockResolvedValue(game);
    const setReady = vi.spyOn(client, "setReady").mockResolvedValue({
      ...game,
      players: [{ ...game.players[0]! }, { ...game.players[1]!, is_ready: true }],
    });

    renderLobby(client);

    expect(
      await screen.findByRole("heading", { name: /camera abc123/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Mihai")).toBeInTheDocument();
    expect(screen.getByText("Ana")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /sunt gata/i }));

    await waitFor(() => {
      expect(setReady).toHaveBeenCalledWith("ABC123", "session-secret", true);
    });
  });

  it("enables start for the host only when every guest is ready", async () => {
    sessionStore.save({
      playerId: "host-1",
      reconnectToken: "reconnect-secret",
      roomCode: "ABC123",
      sessionToken: "session-secret",
    });
    const client = new ApiClient("https://api.example.test");
    vi.spyOn(client, "getGame").mockResolvedValue({
      ...game,
      players: [game.players[0]!, { ...game.players[1]!, is_ready: true }],
    });

    renderLobby(client);

    expect(await screen.findByRole("button", { name: /pornește jocul/i })).toBeEnabled();
  });
});
