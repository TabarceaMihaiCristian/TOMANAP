import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/api/ApiClient";
import { sessionStore } from "@/features/session/sessionStore";
import { renderApp } from "@/test/render";

import { HomePage } from "./HomePage";

describe("HomePage", () => {
  it("introduces the game and offers focused create and join modes", async () => {
    const user = userEvent.setup();
    renderApp(<HomePage />);

    expect(screen.getByRole("heading", { name: /șapte categorii/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /creează joc/i })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /intră cu cod/i }));
    expect(screen.getByLabelText(/codul camerei/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /intră în joc/i })).toBeInTheDocument();
  });

  it("creates a room through the API boundary and stores the issued session", async () => {
    const user = userEvent.setup();
    const client = new ApiClient("https://api.example.test");
    const createGame = vi.spyOn(client, "createGame").mockResolvedValue({
      game: {
        id: "game-1",
        room_code: "ABC123",
        status: "lobby",
        round_count: 5,
        round_duration_seconds: 60,
        players: [],
      },
      player_id: "player-1",
      session_token: "session-secret",
      reconnect_token: "reconnect-secret",
    });
    renderApp(<HomePage />, { client });

    await user.type(screen.getByLabelText(/cum te cheamă/i), "  Mihai  ");
    await user.click(screen.getByRole("button", { name: /creează joc/i }));

    await waitFor(() => {
      expect(createGame).toHaveBeenCalledWith({
        display_name: "Mihai",
        round_count: 5,
        round_duration_seconds: 60,
      });
    });
    expect(sessionStore.load()).toEqual({
      roomCode: "ABC123",
      playerId: "player-1",
      sessionToken: "session-secret",
      reconnectToken: "reconnect-secret",
    });
  });
});
