import { useLocation } from "react-router-dom";

import { useSession } from "@/features/session/sessionContext";

import { useRoomRealtime } from "./useRoomRealtime";

export function RoomRealtimeBridge() {
  const location = useLocation();
  const match = /^\/room\/([^/]+)/.exec(location.pathname);
  const roomCode = match?.[1]?.toUpperCase() ?? null;
  const { clearSession, session } = useSession();
  useRoomRealtime({ onSessionRejected: clearSession, roomCode, session });
  return null;
}
