import { lazy, Suspense } from "react";
import { Outlet, Route, Routes } from "react-router-dom";

import { HomePage } from "@/features/home/HomePage";
import { RoomRealtimeBridge } from "@/features/realtime/RoomRealtimeBridge";
import { SessionGate } from "@/features/session/SessionGate";

import styles from "./App.module.css";
import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";

const GamePage = lazy(() =>
  import("@/features/game/GamePage").then((module) => ({ default: module.GamePage })),
);
const LobbyPage = lazy(() =>
  import("@/features/lobby/LobbyPage").then((module) => ({ default: module.LobbyPage })),
);
const ReviewPage = lazy(() =>
  import("@/features/review/ReviewPage").then((module) => ({
    default: module.ReviewPage,
  })),
);
const LeaderboardPage = lazy(() =>
  import("@/features/review/LeaderboardPage").then((module) => ({
    default: module.LeaderboardPage,
  })),
);

export function App() {
  return (
    <AppShell>
      <RoomRealtimeBridge />
      <Suspense fallback={<div className={styles.routeLoader}>Pregătim jocul…</div>}>
        <Routes>
          <Route element={<HomePage />} path="/" />
          <Route
            element={
              <SessionGate>
                <Outlet />
              </SessionGate>
            }
          >
            <Route element={<LobbyPage />} path="/room/:roomCode" />
            <Route element={<GamePage />} path="/room/:roomCode/play" />
            <Route element={<ReviewPage />} path="/room/:roomCode/review/:roundId" />
            <Route element={<LeaderboardPage />} path="/room/:roomCode/results" />
          </Route>
          <Route element={<NotFoundPage />} path="*" />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
