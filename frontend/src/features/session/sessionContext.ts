import { createContext, useContext } from "react";

import type { SessionIssued } from "@/api/ApiClient";

import type { AnonymousSession } from "./sessionStore";

export type SessionStatus =
  "anonymous" | "authenticated" | "restore-failed" | "restoring";

export interface SessionController {
  acceptIssued: (issued: SessionIssued) => void;
  clearSession: () => void;
  restorationError: string | null;
  retryRestore: () => Promise<void>;
  session: AnonymousSession | null;
  status: SessionStatus;
}

export const SessionContext = createContext<SessionController | null>(null);

export function issuedToSession(issued: SessionIssued): AnonymousSession {
  return {
    playerId: issued.player_id,
    reconnectToken: issued.reconnect_token,
    roomCode: issued.game.room_code,
    sessionToken: issued.session_token,
  };
}

export function useSession(): SessionController {
  const controller = useContext(SessionContext);
  if (controller === null) {
    throw new Error("SessionProvider is missing");
  }
  return controller;
}
