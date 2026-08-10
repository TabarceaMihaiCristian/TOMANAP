import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/api/ApiClient";
import { sessionStore } from "@/features/session/sessionStore";
import { renderApp } from "@/test/render";

import { ReviewPage } from "./ReviewPage";

describe("ReviewPage", () => {
  it("shows auditable answers, points, standings, and the host action", async () => {
    sessionStore.save({
      playerId: "host-1",
      reconnectToken: "reconnect-secret",
      roomCode: "ABC123",
      sessionToken: "session-secret",
    });
    const client = new ApiClient("https://api.example.test");
    vi.spyOn(client, "getReview").mockResolvedValue({
      round_id: "round-1",
      letter: "P",
      status: "review",
      players: [
        {
          player_id: "host-1",
          display_name: "Mihai",
          total_score: 10,
          answers: [
            {
              category: "countries",
              original_answer: "Polonia",
              normalized_answer: "polonia",
              points: 10,
              validation_code: null,
            },
          ],
        },
      ],
    });
    vi.spyOn(client, "getLeaderboard").mockResolvedValue({
      game_id: "game-1",
      entries: [
        {
          rank: 1,
          player_id: "host-1",
          display_name: "Mihai",
          total_score: 10,
        },
      ],
    });
    vi.spyOn(client, "getGame").mockResolvedValue({
      id: "game-1",
      room_code: "ABC123",
      status: "in_progress",
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
      ],
    });

    renderApp(
      <Routes>
        <Route element={<ReviewPage />} path="/room/:roomCode/review/:roundId" />
      </Routes>,
      { client, route: "/room/ABC123/review/round-1" },
    );

    expect(
      await screen.findByRole("heading", { name: /rezultatele rundei/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Polonia")).toBeInTheDocument();
    expect(screen.getByText("+10")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /runda următoare/i })).toBeInTheDocument();
  });

  it("moves a guest to the new active round after the host advances", async () => {
    sessionStore.save({
      playerId: "guest-1",
      reconnectToken: "reconnect-secret",
      roomCode: "ABC123",
      sessionToken: "session-secret",
    });
    const client = new ApiClient("https://api.example.test");
    vi.spyOn(client, "getReview").mockResolvedValue({
      letter: "P",
      players: [],
      round_id: "round-1",
      status: "review",
    });
    vi.spyOn(client, "getLeaderboard").mockResolvedValue({
      entries: [],
      game_id: "game-1",
    });
    vi.spyOn(client, "getGame").mockResolvedValue({
      id: "game-1",
      players: [],
      room_code: "ABC123",
      round_count: 3,
      round_duration_seconds: 45,
      status: "in_progress",
    });
    vi.spyOn(client, "getCurrentRound").mockResolvedValue({
      categories: [
        "countries",
        "cities",
        "brands",
        "activities",
        "names",
        "animals",
        "plants",
      ],
      round: {
        ends_at: "2099-07-12T20:01:00Z",
        id: "round-2",
        is_current: true,
        letter: "A",
        sequence_number: 2,
        starts_at: "2026-07-12T20:00:00Z",
        status: "active",
      },
      submission: null,
    });

    renderApp(
      <Routes>
        <Route element={<ReviewPage />} path="/room/:roomCode/review/:roundId" />
        <Route element={<h1>Next round</h1>} path="/room/:roomCode/play" />
      </Routes>,
      { client, route: "/room/ABC123/review/round-1" },
    );

    expect(await screen.findByRole("heading", { name: "Next round" })).toBeVisible();
  });
});
