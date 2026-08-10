import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/api/ApiClient";
import { sessionStore } from "@/features/session/sessionStore";
import { renderApp } from "@/test/render";

import { GamePage } from "./GamePage";

describe("GamePage", () => {
  it("renders every category and saves a complete answer snapshot", async () => {
    const user = userEvent.setup();
    sessionStore.save({
      playerId: "player-1",
      reconnectToken: "reconnect-secret",
      roomCode: "ABC123",
      sessionToken: "session-secret",
    });
    const client = new ApiClient("https://api.example.test");
    vi.spyOn(client, "getCurrentRound").mockResolvedValue({
      round: {
        id: "round-1",
        sequence_number: 1,
        letter: "P",
        status: "active",
        is_current: true,
        starts_at: "2026-07-12T20:00:00Z",
        ends_at: "2099-07-12T20:01:00Z",
      },
      categories: [
        "countries",
        "cities",
        "brands",
        "activities",
        "names",
        "animals",
        "plants",
      ],
      submission: null,
    });
    const saveSubmission = vi.spyOn(client, "saveSubmission").mockResolvedValue({
      id: "submission-1",
      round_id: "round-1",
      player_id: "player-1",
      answers: { countries: "Polonia" },
      normalized_answers: { countries: "polonia" },
      is_finalized: false,
      submitted_at: "2026-07-12T20:00:10Z",
      finalized_at: null,
      revision: 1,
    });

    renderApp(
      <Routes>
        <Route element={<GamePage />} path="/room/:roomCode/play" />
      </Routes>,
      { client, route: "/room/ABC123/play" },
    );

    expect(await screen.findByRole("heading", { name: /litera p/i })).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(7);
    await user.type(screen.getByLabelText("Țări"), "Polonia");
    await user.click(screen.getByRole("button", { name: /salvează ciorna/i }));

    await waitFor(() => {
      expect(saveSubmission).toHaveBeenCalledWith("round-1", "session-secret", {
        activities: "",
        animals: "",
        brands: "",
        cities: "",
        countries: "Polonia",
        names: "",
        plants: "",
      });
    });
  });
});
